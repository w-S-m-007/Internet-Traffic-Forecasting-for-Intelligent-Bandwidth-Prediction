"""Check artifact integrity, gap rendering and real Streamlit interactions."""

import csv
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

from dashboard.artifacts import (MODEL_LABELS, ArtifactError, allocation_snapshot,
                                 available_horizons, load_allocation, load_forecasts)
from dashboard.charts import traffic_chart
from experiments.evaluate_allocation import MARGINS, allocate, select_margin
from experiments.forecast_metrics import forecast_metrics


def save_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def make_results(project):
    """Small saved-results fixture, independent of Git-ignored real data."""
    demand = {"validation": [100, 110, 200, 100, 120, 100, 130, 100],
              "test": [100, 200, 100, 130, 100, 140, 100, 110]}
    predictors = {}
    for model, factor in (("persistence", 0), ("moving_average_4", .1), ("lstm", .2), ("gru", .25), ("transformer", .3)):
        predictors[model] = {split: np.array(values, dtype=float) * factor + 100 * (1 - factor)
                             for split, values in demand.items()}
    for source, models in (("baselines", ["persistence", "moving_average_4"]), ("lstm", ["lstm"]),
                          ("gru", ["gru"]), ("transformer", ["transformer"])):
        folder = project / f"results/{source}/10min"
        forecasts, metrics = [], []
        for model in models:
            for split_index, (split, actual) in enumerate(demand.items()):
                start = datetime(2024, 6, 6 + split_index, tzinfo=timezone.utc)
                values = predictors[model][split]
                metrics.append({"model": model, "horizon_minutes": 10, "split": split,
                                **forecast_metrics(actual, values), "training_time_s": 1., "cpu_inference_ms": .1})
                for index, value in enumerate(actual):
                    timestamp = start + timedelta(minutes=10 * index)
                    forecasts.append({"model": model, "horizon_minutes": 10, "split": split,
                                      "target_id": str(split_index * 100 + index),
                                      "forecast_origin_utc": timestamp.isoformat(),
                                      "target_interval_start_utc": timestamp.isoformat(),
                                      "target_completion_utc": (timestamp + timedelta(minutes=10)).isoformat(),
                                      "actual_mbps": value, "predicted_mbps": values[index]})
        save_csv(folder / "metrics.csv", metrics)
        save_csv(folder / "predictions.csv", forecasts)
        config = {"horizon_minutes": 10, "artifact_sha256": {name: "a" * 64 for name in
                  ("windows_10min.npz", "windows_10min.csv", "preparation_config.json")}}
        (folder / "run_config.json").write_text(json.dumps(config), encoding="utf-8")
    metrics = []
    for policy, model in (("reactive", "persistence"), ("proactive_lstm", "lstm"), ("proactive_moving_average_4", "moving_average_4")):
        for split, actual in demand.items():
            for margin in MARGINS:
                _, scores = allocate(actual, predictors[model][split], margin)
                metrics.append({"policy": policy, "horizon_minutes": 10, "split": split, "margin": margin, **scores})
    folder = project / "results/allocation/10min"
    save_csv(folder / "metrics.csv", metrics)
    sources = {str(path.relative_to(project)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
               for source in ("baselines", "lstm") for path in (project / f"results/{source}/10min").iterdir()
               if path.name in ("predictions.csv", "run_config.json")}
    defaults = {policy: select_margin([row for row in metrics if row["policy"] == policy and row["split"] == "validation"])
                for policy in ("reactive", "proactive_lstm", "proactive_moving_average_4")}
    config = {"horizon_minutes": 10, "interval_seconds": 600, "margins": list(MARGINS),
              "source_sha256": sources, "selected_defaults": defaults}
    (folder / "run_config.json").write_text(json.dumps(config), encoding="utf-8")


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name)
        make_results(self.project)

    def app(self, project=None):
        source = f"from pathlib import Path\nfrom dashboard.app import main\nmain(Path({str(project or self.project)!r}))"
        return AppTest.from_string(source, default_timeout=30).run()

    def test_saved_models_share_targets_and_allocation_scores(self):
        artifacts = load_forecasts(self.project, 10)
        self.assertEqual(set(artifacts.configs), set(MODEL_LABELS))
        self.assertEqual(available_horizons(self.project), [10])
        self.assertIsNotNone(load_allocation(self.project, artifacts))
        _, low = allocation_snapshot(artifacts, "lstm", "test", .05)
        _, high = allocation_snapshot(artifacts, "lstm", "test", .20)
        self.assertGreater(high["proactive"]["mean_capacity_mbps"], low["proactive"]["mean_capacity_mbps"])
        self.assertLessEqual(high["proactive"]["shortfall_pct"], low["proactive"]["shortfall_pct"])

    def test_corrupt_metrics_are_rejected(self):
        path = self.project / "results/gru/10min/metrics.csv"
        frame = pd.read_csv(path)
        frame.loc[0, "mae_mbps"] += 1
        frame.to_csv(path, index=False)
        with self.assertRaisesRegex(ArtifactError, "mae_mbps"):
            load_forecasts(self.project, 10)

    def test_misaligned_forecast_ids_are_rejected(self):
        path = self.project / "results/gru/10min/predictions.csv"
        frame = pd.read_csv(path)
        frame.loc[0, "target_id"] = 999
        frame.to_csv(path, index=False)
        with self.assertRaisesRegex(ArtifactError, "timestamped targets"):
            load_forecasts(self.project, 10)

    def test_stale_allocation_sources_are_rejected(self):
        artifacts = load_forecasts(self.project, 10)
        path = self.project / "results/lstm/10min/predictions.csv"
        path.write_text(path.read_text() + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ArtifactError, "changed"):
            load_allocation(self.project, artifacts)

    def test_chart_does_not_join_an_excluded_gap(self):
        artifacts = load_forecasts(self.project, 10)
        frame, _ = allocation_snapshot(artifacts, "lstm", "test", .2)
        frame.loc[4:, "target_completion_utc"] += pd.Timedelta(hours=1)
        figure = traffic_chart(frame, {"Actual": "actual_mbps"})
        self.assertFalse(figure.data[0].connectgaps)
        self.assertEqual(int(np.isnan(figure.data[0].y).sum()), 1)

    def test_app_switches_model_split_page_and_margin(self):
        app = self.app()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertEqual(app.selectbox(key="model").value, "lstm")
        self.assertEqual(len(app.warning), 1)
        app.selectbox(key="model").set_value("transformer").run()
        self.assertFalse(app.exception)
        artifacts = load_forecasts(self.project, 10)
        expected = artifacts.metrics.query("model == 'transformer' and split == 'test'").iloc[0]
        self.assertEqual(app.metric[0].value, f"{expected['mae_mbps']:,.3f} Mbps")
        app.selectbox(key="split").set_value("validation").run()
        app.radio(key="view").set_value("Allocation").run()
        app.slider(key="margin_lstm").set_value(5).run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertIn("Viewing: 5%", app.warning[0].value)
        self.assertEqual(app.selectbox(key="allocation_model").value, "lstm")
        self.assertEqual(app.selectbox(key="model").value, "transformer")
        app.radio(key="view").set_value("Forecasts").run()
        app.slider(key="replay_10_validation").set_value(4).run()
        self.assertFalse(app.exception)
        self.assertTrue(any("Replay target" in caption.value for caption in app.caption))

    def test_empty_checkout_has_a_useful_message(self):
        empty = self.project / "empty"
        empty.mkdir()
        app = self.app(empty)
        self.assertFalse(app.exception)
        self.assertTrue(any("No saved forecast results" in item.value for item in app.info))


if __name__ == "__main__":
    unittest.main()
