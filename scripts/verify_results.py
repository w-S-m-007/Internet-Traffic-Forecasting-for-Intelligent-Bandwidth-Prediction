"""Verify saved experiment evidence, optionally replaying every neural checkpoint."""
import argparse
import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from dashboard.artifacts import load_allocation, load_forecasts, model_forecasts
from data_processing.prepare_dataset import BASE_FEATURES, fit_scalers, window_features

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    with path.open(newline='', encoding='utf-8-sig') as handle:
        return list(csv.DictReader(handle))


def evidence_manifest(project):
    """Bind verification to raw/prepared/model/allocation evidence, excluding reports."""
    folders = ['data/raw/cesnet/sample', 'data/prepared']
    folders += [f'results/{source}/{horizon}min' for source in ('baselines','lstm','gru','transformer')
                for horizon in (10,30,60)]
    files = {path for folder in folders for path in (project / folder).rglob('*')
             if path.is_file() and path.suffix in ('.csv','.npz','.json','.pt','.txt')}
    files.update(project / 'results/allocation/10min' / name for name in
                 ('metrics.csv','replay.csv','default_test_metrics.csv','run_config.json')
                 if (project / 'results/allocation/10min' / name).is_file())
    return {path.relative_to(project).as_posix(): sha(path) for path in sorted(files)}


def check_verification_manifest(project, report):
    saved = report.get('artifact_sha256')
    if not isinstance(saved, dict) or not saved:
        raise ValueError('Verification has no artifact hash manifest; run verification again')
    current = evidence_manifest(project)
    if current != saved:
        changed = sorted(name for name in set(saved) | set(current) if saved.get(name) != current.get(name))
        raise ValueError('Verified artifacts changed; run verification again: ' + ', '.join(changed[:5]))


def verify_allocation_replay(project, artifacts, configuration):
    """Independently recompute every saved replay value, summary and default CSV."""
    folder = project / 'results/allocation/10min'
    metrics = pd.read_csv(folder / 'metrics.csv')
    replay = pd.read_csv(folder / 'replay.csv', dtype={'target_id': str})
    defaults = pd.read_csv(folder / 'default_test_metrics.csv')
    policies = {'reactive': 'persistence', 'proactive_moving_average_4': 'moving_average_4',
                'proactive_lstm': 'lstm', 'proactive_gru': 'gru', 'proactive_transformer': 'transformer'}
    margins = (.05,.10,.15,.20)
    keys = ['policy','split','margin']
    expected_keys = {(policy, split, margin) for policy in policies for split in ('validation','test') for margin in margins}
    if (len(metrics) != 40 or metrics.duplicated(keys).any()
            or set(map(tuple, metrics[keys].to_numpy())) != expected_keys
            or set(map(tuple, replay[keys].drop_duplicates().to_numpy())) != expected_keys
            or replay.duplicated([*keys, 'target_id']).any()):
        raise ValueError('Allocation replay or metric policy/split/margin keys are invalid')
    checked = 0
    for policy, model in policies.items():
        for split in ('validation','test'):
            forecast = model_forecasts(artifacts, model, split).sort_values('target_id')
            actual = forecast['actual_mbps'].to_numpy()
            predicted = forecast['predicted_mbps'].to_numpy()
            for margin in margins:
                frame = replay[(replay['policy'] == policy) & (replay['split'] == split)
                               & (replay['margin'] == margin)].sort_values('target_id')
                if frame['target_id'].tolist() != forecast['target_id'].tolist():
                    raise ValueError('Allocation replay target IDs differ from saved forecasts')
                for field in ('forecast_origin_utc','target_interval_start_utc','target_completion_utc'):
                    if not np.array_equal(pd.to_datetime(frame[field], utc=True), forecast[field]):
                        raise ValueError('Allocation replay timestamps differ from saved forecasts')
                capacity = np.maximum(predicted, 0) * (1 + margin)
                deficit = np.maximum(actual - capacity, 0)
                excess = np.maximum(capacity - actual, 0)
                served = np.minimum(actual, capacity)
                values = {'actual_mbps':actual, 'forecast_mbps':predicted, 'capacity_mbps':capacity,
                          'deficit_mbps':deficit, 'deficit_mb':deficit * 75,
                          'overprovision_mbps':excess, 'served_mbps':served}
                for field, expected in values.items():
                    if not np.allclose(frame[field], expected, rtol=1e-10, atol=1e-8):
                        raise ValueError(f'Allocation replay {field} differs from direct arithmetic')
                scores = {'n_intervals':len(actual), 'shortfall_intervals':int((deficit > 0).sum()),
                          'shortfall_pct':100 * float((deficit > 0).mean()),
                          'deficit_volume_mb':float(deficit.sum() * 75),
                          'mean_capacity_mbps':float(capacity.mean()),
                          'mean_overprovision_mbps':float(excess.mean()),
                          'overprovision_volume_mb':float(excess.sum() * 75),
                          'served_demand_to_capacity_ratio':float(served.sum() / capacity.sum()) if capacity.sum() else np.nan}
                saved = metrics[(metrics['policy'] == policy) & (metrics['split'] == split)
                                & (metrics['margin'] == margin)].iloc[0]
                for field, expected in scores.items():
                    if not np.isclose(saved[field], expected, rtol=1e-10, atol=1e-8, equal_nan=True):
                        raise ValueError(f'Allocation metric {field} differs from direct arithmetic')
                checked += len(frame)
    if len(defaults) != len(policies) or set(defaults['policy']) != set(policies):
        raise ValueError('Default test CSV has missing or repeated policies')
    for policy in policies:
        validation = metrics[(metrics['policy'] == policy) & (metrics['split'] == 'validation')]
        feasible = validation[validation['shortfall_pct'] <= 1]
        selected = (feasible.sort_values(['mean_capacity_mbps','margin']).iloc[0] if len(feasible)
                    else validation[validation['margin'] == .20].iloc[0])
        chosen = configuration['selected_defaults'][policy]
        if chosen['margin'] != selected['margin'] or chosen['validation_target_met'] != bool(len(feasible)):
            raise ValueError('Allocation default is not selected on validation only')
        expected = metrics[(metrics['policy'] == policy) & (metrics['split'] == 'test')
                           & (metrics['margin'] == selected['margin'])].iloc[0]
        saved = defaults[defaults['policy'] == policy].iloc[0]
        for field in metrics.columns:
            if field in ('policy','split'):
                valid = saved[field] == expected[field]
            else:
                valid = np.isclose(saved[field], expected[field], rtol=1e-10, atol=1e-8, equal_nan=True)
            if not valid:
                raise ValueError(f'Default test CSV {field} differs from selected test metrics')
    return {'metric_rows': len(metrics), 'replay_rows': checked, 'default_test_rows': len(defaults),
            'method': 'Direct NumPy arithmetic on joined saved forecasts; independent of allocation helper'}


def verify(project=ROOT, checkpoints=False, device='auto'):
    prepared = project / 'data/prepared'
    config = json.loads((prepared / 'preparation_config.json').read_text())
    for name, digest in config['source_sha256'].items():
        if sha(project / 'data/raw/cesnet/sample' / name) != digest:
            raise ValueError(f'Raw source changed: {name}')
    features = read(prepared / 'institution_0_features.csv')
    base = np.array([[float(row[k]) if row[k] else np.nan for k in BASE_FEATURES] for row in features])
    rates = np.array([float(row['recorded_traffic_mbps']) if row['recorded_traffic_mbps'] else np.nan for row in features])
    seconds = np.array([datetime.fromisoformat(row['timestamp_utc']).timestamp() for row in features])
    blocked = np.array([row['excluded_for_outage'] == '1' or row['excluded_for_boundary'] == '1' for row in features])
    blocked_prefix = np.r_[0, np.cumsum(blocked)]
    irregular_prefix = np.r_[0, np.cumsum(np.diff(seconds) != 600)]
    report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'horizons': [],
              'checkpoint_replay': checkpoints, 'raw_source_sha256': config['source_sha256']}
    if checkpoints:
        os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
        import torch
        from experiments.train_neural import predict
        from models.lstm_model import TrafficLSTM
        from models.gru_model import TrafficGRU
        from models.transformer_model import TrafficTransformer
        torch.set_num_threads(1)
        torch.use_deterministic_algorithms(True)
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        torch.backends.mha.set_fastpath_enabled(False)
        chosen = 'cuda' if device == 'auto' and torch.cuda.is_available() else 'cpu' if device == 'auto' else device
        torch_device = torch.device(chosen)
        types = {'lstm': TrafficLSTM, 'gru': TrafficGRU, 'transformer': TrafficTransformer}
        report['replay_device'] = chosen
    for horizon in (10, 30, 60):
        artifacts = load_forecasts(project, horizon)
        if len(artifacts.metrics) != 10 or len(artifacts.configs) != 5:
            raise ValueError(f'Incomplete five-model experiment at {horizon} minutes')
        metadata = read(prepared / f'windows_{horizon}min.csv')
        scalers = json.loads((prepared / f'scalers_{horizon}min.json').read_text())
        with np.load(prepared / f'windows_{horizon}min.npz', allow_pickle=False) as data:
            starts, origins, targets, splits = (data[k] for k in ('start_row','origin_row','target_row','split'))
            assert len(metadata) == len(targets)
            assert (origins - starts == 17).all() and (targets - origins == horizon // 10).all()
            assert (seconds[targets] - seconds[origins] == horizon * 60).all()
            assert (blocked_prefix[targets + 1] - blocked_prefix[starts] == 0).all()
            assert (irregular_prefix[targets] - irregular_prefix[starts] == 0).all()
            assert all(features[int(i)]['usable_target'] == '1' and features[int(i)]['target_observed'] == '1' for i in targets)
            completion = seconds[targets] + 600
            vcut = datetime.fromisoformat(config['validation_start_utc']).timestamp()
            tcut = datetime.fromisoformat(config['test_start_utc']).timestamp()
            assert (completion[splits == 0] < vcut).all()
            assert ((completion[splits == 1] >= vcut) & (completion[splits == 1] < tcut)).all()
            assert (completion[splits == 2] >= tcut).all()
            for i, row in enumerate(metadata):
                assert row['target_id'] == features[int(targets[i])]['id_time']
                assert row['input_last_id'] == features[int(origins[i])]['id_time']
                assert row['split'] == ('train', 'validation', 'test')[int(splits[i])]
                assert datetime.fromisoformat(row['forecast_origin_utc']).timestamp() == seconds[origins[i]] + 600
                assert datetime.fromisoformat(row['target_completion_utc']).timestamp() == completion[i]
            raw_x = window_features(base, starts)
            fitted = fit_scalers(raw_x, rates[targets], splits)
            for key in fitted:
                np.testing.assert_allclose(fitted[key], scalers[key], rtol=1e-12, atol=1e-12)
            np.testing.assert_array_equal(data['target_mbps'], rates[targets])
            np.testing.assert_array_equal(data['input_mbps'], raw_x[:, :, 0])
            np.testing.assert_array_equal(data['X'], ((raw_x - scalers['x_mean']) / scalers['x_std']).astype(np.float32))
            np.testing.assert_array_equal(data['y'], ((rates[targets] - scalers['y_mean']) / scalers['y_std']).astype(np.float32))
            for name, saved in artifacts.configs.items():
                for filename, digest in saved['artifact_sha256'].items():
                    if sha(prepared / filename) != digest:
                        raise ValueError(f'Stale {name}/{horizon} provenance: {filename}')
                if name in ('lstm', 'gru', 'transformer'):
                    folder = project / f'results/{name}/{horizon}min'
                    history = read(folder / 'training_history.csv')
                    assert int(min(history, key=lambda row: float(row['validation_scaled_mse']))['epoch']) == saved['best_epoch']
                    assert len(history) == saved['epochs_completed']
                    assert json.loads((folder / 'scalers.json').read_text()) == scalers
                    assert saved['seed'] == 42 and saved['patience'] == 5 and saved['max_epochs'] == 30
                    if checkpoints:
                        model = types[name]().to(torch_device).eval()
                        model.load_state_dict(torch.load(folder / 'best_model.pt', map_location=torch_device, weights_only=True))
                for code, split in ((1, 'validation'), (2, 'test')):
                    indices = np.flatnonzero(splits == code)
                    frame = model_forecasts(artifacts, name, split)
                    assert frame['target_id'].astype(str).tolist() == [metadata[i]['target_id'] for i in indices]
                    np.testing.assert_allclose(frame['actual_mbps'], data['target_mbps'][indices], rtol=1e-12, atol=1e-10)
                    if name == 'persistence':
                        expected = data['input_mbps'][indices, -1]
                    elif name == 'moving_average_4':
                        expected = data['input_mbps'][indices, -4:].mean(axis=1)
                    elif checkpoints:
                        expected = predict(model, torch.from_numpy(data['X'][indices]), torch_device).astype(float)
                        expected = expected * scalers['y_std'] + scalers['y_mean']
                    else:
                        continue
                    try:
                        np.testing.assert_allclose(frame['predicted_mbps'], expected, rtol=1e-5, atol=1e-4)
                    except AssertionError as error:
                        hint = (' Replay on the saved training device; CPU/CUDA arithmetic can differ.'
                                if checkpoints and name in types and saved['training_device'] != chosen else '')
                        raise ValueError(f'{name}/{horizon}min/{split} predictions differ from replay.{hint}') from error
                if checkpoints and name in types:
                    del model
            counts = {name: int((splits == i).sum()) for i, name in enumerate(('train','validation','test'))}
        report['horizons'].append({'minutes': horizon, **counts, 'five_models': 'PASS', 'prepared_data_and_metrics': 'PASS'})
        print(f'{horizon} minutes: data, scalers, provenance, baselines, targets and metrics PASS', flush=True)
    allocation = load_allocation(project, load_forecasts(project, 10))
    if allocation is None or len(allocation['selected_defaults']) != 5:
        raise ValueError('Expected the complete five-policy allocation comparison')
    report['allocation_replay'] = verify_allocation_replay(project, load_forecasts(project, 10), allocation)
    report['allocation'] = 'PASS: 40 margin/split/policy rows and validation-only defaults'
    report['artifact_sha256'] = evidence_manifest(project)
    report['status'] = 'PASS'
    output = project / 'results/comparison'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'final_verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoints', action='store_true')
    parser.add_argument('--device', choices=('auto','cpu','cuda'), default='auto')
    args = parser.parse_args()
    verify(checkpoints=args.checkpoints, device=args.device)


if __name__ == '__main__':
    main()
