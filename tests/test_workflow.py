"""Reject corrupted replay evidence and packages with stale verification."""

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from dashboard.artifacts import load_forecasts
from experiments.evaluate_allocation import MARGINS, allocate
from scripts.verify_results import (check_verification_manifest, evidence_manifest,
                                    verify_allocation_replay)
from tests.test_dashboard import make_results, save_csv


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        make_results(self.project, expanded=True)
        self.artifacts = load_forecasts(self.project, 10)
        self.folder = self.project / 'results/allocation/10min'
        self.configuration = json.loads((self.folder / 'run_config.json').read_text())
        metrics = pd.read_csv(self.folder / 'metrics.csv')
        rows = []
        for policy, choice in self.configuration['selected_defaults'].items():
            model = 'persistence' if policy == 'reactive' else policy.removeprefix('proactive_')
            for split in ('validation','test'):
                frame = self.artifacts.predictions[(self.artifacts.predictions['model'] == model)
                                                  & (self.artifacts.predictions['split'] == split)]
                for margin in MARGINS:
                    arrays, _ = allocate(frame['actual_mbps'], frame['predicted_mbps'], margin)
                    for i, (_, row) in enumerate(frame.iterrows()):
                        rows.append({'policy':policy, 'split':split, 'margin':margin,
                                     'target_id':row['target_id'],
                                     **{field: row[field].isoformat() for field in
                                        ('forecast_origin_utc','target_interval_start_utc','target_completion_utc')},
                                     'actual_mbps':row['actual_mbps'], 'forecast_mbps':row['predicted_mbps'],
                                     'capacity_mbps':arrays['capacity'][i], 'deficit_mbps':arrays['deficit'][i],
                                     'deficit_mb':arrays['deficit'][i] * 75,
                                     'overprovision_mbps':arrays['idle'][i], 'served_mbps':arrays['served'][i]})
        save_csv(self.folder / 'replay.csv', rows)
        selected = [row for row in metrics.to_dict('records') if row['split'] == 'test'
                    and row['margin'] == self.configuration['selected_defaults'][row['policy']]['margin']]
        save_csv(self.folder / 'default_test_metrics.csv', selected)

    def test_valid_replay_and_defaults_pass(self):
        result = verify_allocation_replay(self.project, self.artifacts, self.configuration)
        self.assertEqual(result['metric_rows'], 40)
        self.assertEqual(result['replay_rows'], 320)
        self.assertEqual(result['default_test_rows'], 5)

    def test_corrupted_replay_volume_is_rejected(self):
        path = self.folder / 'replay.csv'
        frame = pd.read_csv(path)
        frame.loc[0, 'deficit_mb'] += 1
        frame.to_csv(path, index=False)
        with self.assertRaisesRegex(ValueError, 'replay deficit_mb'):
            verify_allocation_replay(self.project, self.artifacts, self.configuration)

    def test_wrong_replay_timestamp_is_rejected(self):
        path = self.folder / 'replay.csv'
        frame = pd.read_csv(path)
        frame.loc[0, 'target_completion_utc'] = '2025-01-01T00:00:00+00:00'
        frame.to_csv(path, index=False)
        with self.assertRaisesRegex(ValueError, 'timestamps'):
            verify_allocation_replay(self.project, self.artifacts, self.configuration)

    def test_corrupted_default_table_is_rejected(self):
        path = self.folder / 'default_test_metrics.csv'
        frame = pd.read_csv(path)
        frame.loc[0, 'mean_capacity_mbps'] += 1
        frame.to_csv(path, index=False)
        with self.assertRaisesRegex(ValueError, 'Default test CSV mean_capacity_mbps'):
            verify_allocation_replay(self.project, self.artifacts, self.configuration)

    def test_manifest_rejects_changed_missing_or_added_evidence(self):
        path = self.project / 'results/lstm/10min/best_model.pt'
        path.write_bytes(b'original checkpoint fixture')
        report = {'artifact_sha256': evidence_manifest(self.project)}
        check_verification_manifest(self.project, report)
        path.write_bytes(b'modified checkpoint fixture')
        with self.assertRaisesRegex(ValueError, 'Verified artifacts changed'):
            check_verification_manifest(self.project, report)
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'Verified artifacts changed'):
            check_verification_manifest(self.project, report)
        path.write_bytes(b'original checkpoint fixture')
        extra = path.with_name('extra.csv')
        extra.write_text('unexpected evidence')
        with self.assertRaisesRegex(ValueError, 'Verified artifacts changed'):
            check_verification_manifest(self.project, report)

    def test_manifest_ignores_docs_archives_and_its_own_report(self):
        report = {'artifact_sha256': evidence_manifest(self.project)}
        for relative in ('docs/readme.md','results/allocation_archive/old/metrics.csv',
                         'results/comparison/final_verification.json'):
            path = self.project / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('outside experimental evidence')
        check_verification_manifest(self.project, report)

    def test_missing_verification_manifest_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'no artifact hash manifest'):
            check_verification_manifest(self.project, {'status':'PASS'})


if __name__ == '__main__':
    unittest.main()
