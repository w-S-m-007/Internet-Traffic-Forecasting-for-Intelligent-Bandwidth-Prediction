"""Replay saved 10-minute forecasts in an abstract capacity-pool simulation."""

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


MARGINS = (.05, .10, .15, .20)
SHORTFALL_LIMIT_PCT = 1.


def allocate(actual, forecast, margin, interval_seconds=600):
    actual = np.asarray(actual, dtype=float)
    forecast = np.asarray(forecast, dtype=float)
    if actual.ndim != 1 or not len(actual) or forecast.shape != actual.shape:
        raise ValueError("Demand and forecasts must be nonempty aligned vectors")
    if not np.isfinite(actual).all() or not np.isfinite(forecast).all() or (actual < 0).any():
        raise ValueError("Demand must be nonnegative; demand and forecasts must be finite")
    if not np.isfinite(margin) or margin < 0 or not np.isfinite(interval_seconds) or interval_seconds <= 0:
        raise ValueError("Margin must be nonnegative and interval duration positive")
    capacity = np.maximum(forecast, 0) * (1 + margin)
    deficit = np.maximum(actual - capacity, 0)
    idle = np.maximum(capacity - actual, 0)
    served = np.minimum(actual, capacity)
    total_capacity = float(capacity.sum())
    metrics = {
        "n_intervals": len(actual),
        "shortfall_intervals": int((deficit > 0).sum()),
        "shortfall_pct": float(100 * np.mean(deficit > 0)),
        "deficit_volume_mb": float(deficit.sum() * interval_seconds / 8),
        "mean_capacity_mbps": float(capacity.mean()),
        "mean_overprovision_mbps": float(idle.mean()),
        "overprovision_volume_mb": float(idle.sum() * interval_seconds / 8),
        "served_demand_to_capacity_ratio": float(served.sum() / total_capacity) if total_capacity else None,
    }
    return {"capacity": capacity, "deficit": deficit, "idle": idle, "served": served}, metrics


def select_margin(validation_rows):
    if len(validation_rows) != len(MARGINS) or {row["margin"] for row in validation_rows} != set(MARGINS):
        raise ValueError("Expected all four validation margin candidates")
    if any(row["split"] != "validation" for row in validation_rows):
        raise ValueError("Only validation results may select the margin")
    qualifying = [row for row in validation_rows if row["shortfall_pct"] <= SHORTFALL_LIMIT_PCT]
    chosen = min(qualifying, key=lambda row: (row["mean_capacity_mbps"], row["margin"])) if qualifying else next(
        row for row in validation_rows if row["margin"] == .20)
    return {"margin": chosen["margin"], "validation_target_met": bool(qualifying),
            "validation_shortfall_pct": chosen["shortfall_pct"],
            "validation_mean_capacity_mbps": chosen["mean_capacity_mbps"]}


def align_forecasts(rows, metadata, actual, models):
    """Join by split and target ID, checking timestamps and observed demand."""
    expected = {(row["split"], row["target_id"]): index for index, row in enumerate(metadata)}
    if len(expected) != len(metadata):
        raise ValueError("Duplicate prepared target keys")
    values = {model: np.full(len(metadata), np.nan) for model in models}
    seen = set()
    for row in rows:
        model = row["model"]
        key = (row["split"], row["target_id"])
        unique = (model, *key)
        if model not in values or key not in expected or unique in seen:
            raise ValueError("Unexpected or duplicate saved forecast")
        seen.add(unique)
        index = expected[key]
        if int(row["horizon_minutes"]) != 10:
            raise ValueError("Allocation requires 10-minute forecasts")
        for field in ("forecast_origin_utc", "target_interval_start_utc", "target_completion_utc"):
            if row[field] != metadata[index][field]:
                raise ValueError("Saved forecast timestamps differ from prepared windows")
        if not np.isclose(float(row["actual_mbps"]), actual[index], rtol=1e-10, atol=1e-9):
            raise ValueError("Saved actual demand differs from prepared targets")
        values[model][index] = float(row["predicted_mbps"])
    if any(not np.isfinite(array).all() for array in values.values()):
        raise ValueError("Missing or nonfinite saved forecasts")
    return values


def read_rows(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_rows(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    project = Path(__file__).resolve().parents[1]
    prepared = project / "data/prepared"
    baseline = project / "results/baselines/10min"
    lstm = project / "results/lstm/10min"
    prepared_paths = [prepared / name for name in ("windows_10min.npz", "windows_10min.csv",
                                                  "scalers_10min.json", "preparation_config.json")]
    result_paths = [folder / name for folder in (baseline, lstm)
                    for name in ("predictions.csv", "run_config.json")]
    if not all(path.is_file() for path in prepared_paths + result_paths):
        raise FileNotFoundError("Prepare data, evaluate 10-minute baselines and train the 10-minute LSTM first")
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in prepared_paths}
    for folder in (baseline, lstm):
        configuration = json.loads((folder / "run_config.json").read_text())
        required = prepared_paths if folder == lstm else [prepared_paths[0], prepared_paths[1], prepared_paths[3]]
        if configuration["horizon_minutes"] != 10 or any(
                configuration["artifact_sha256"].get(path.name) != hashes[path.name] for path in required):
            raise ValueError("Forecast provenance differs from current preparation; regenerate matching forecasts")
    preparation = json.loads(prepared_paths[3].read_text())
    interval_seconds = preparation["interval_seconds"]
    if interval_seconds != 600:
        raise ValueError("This experiment requires the documented 600-second intervals")
    metadata = read_rows(prepared_paths[1])
    with np.load(prepared_paths[0], allow_pickle=False) as arrays:
        actual, splits, history = arrays["target_mbps"], arrays["split"], arrays["input_mbps"]
        if len(metadata) != len(actual) or splits.shape != actual.shape or history.shape != (len(actual), 18):
            raise ValueError("Prepared arrays and metadata do not align")
        names = {0: "train", 1: "validation", 2: "test"}
        if any(int(code) not in names or row["split"] != names[int(code)] for row, code in zip(metadata, splits)):
            raise ValueError("Prepared split assignments disagree")
        selected = np.flatnonzero((splits == 1) | (splits == 2))
        actual = actual[selected].copy()
        history = history[selected].copy()
    metadata = [metadata[index] for index in selected]
    dates = [datetime.fromisoformat(row["target_completion_utc"]) for row in metadata]
    if any(right <= left for left, right in zip(dates, dates[1:])):
        raise ValueError("Target timestamps must increase strictly")
    for row in metadata:
        origin = datetime.fromisoformat(row["forecast_origin_utc"])
        start = datetime.fromisoformat(row["target_interval_start_utc"])
        end = datetime.fromisoformat(row["target_completion_utc"])
        if origin != start or (end - start).total_seconds() != interval_seconds:
            raise ValueError("Expected one-interval forecasts available at target interval start")
    baseline_values = align_forecasts(read_rows(baseline / "predictions.csv"), metadata, actual,
                                     ["persistence", "moving_average_4"])
    lstm_values = align_forecasts(read_rows(lstm / "predictions.csv"), metadata, actual, ["lstm"])
    if not np.allclose(baseline_values["persistence"], history[:, -1], rtol=1e-10, atol=1e-9) or not np.allclose(
            baseline_values["moving_average_4"], history[:, -4:].mean(axis=1), rtol=1e-10, atol=1e-9):
        raise ValueError("Baseline predictions differ from the documented historical inputs")
    policies = {"reactive": history[:, -1], "proactive_moving_average_4": baseline_values["moving_average_4"],
                "proactive_lstm": lstm_values["lstm"]}
    output = project / "results/allocation/10min"
    metrics, replay = [], []
    defaults = {}
    for policy, forecasts in policies.items():
        for split in ("validation", "test"):
            indices = np.array([index for index, row in enumerate(metadata) if row["split"] == split])
            for margin in MARGINS:
                arrays, scores = allocate(actual[indices], forecasts[indices], margin, interval_seconds)
                metrics.append({"policy": policy, "horizon_minutes": 10, "split": split, "margin": margin, **scores})
                for position, index in enumerate(indices):
                    row = metadata[index]
                    replay.append({"policy": policy, "split": split, "margin": margin,
                                   "target_id": row["target_id"], "forecast_origin_utc": row["forecast_origin_utc"],
                                   "target_interval_start_utc": row["target_interval_start_utc"],
                                   "target_completion_utc": row["target_completion_utc"],
                                   "actual_mbps": actual[index], "forecast_mbps": forecasts[index],
                                   "capacity_mbps": arrays["capacity"][position],
                                   "deficit_mbps": arrays["deficit"][position],
                                   "deficit_mb": arrays["deficit"][position] * interval_seconds / 8,
                                   "overprovision_mbps": arrays["idle"][position],
                                   "served_mbps": arrays["served"][position]})
        defaults[policy] = select_margin([row for row in metrics if row["policy"] == policy and row["split"] == "validation"])
    output.mkdir(parents=True, exist_ok=True)
    write_rows(output / "metrics.csv", metrics)
    write_rows(output / "replay.csv", replay)
    write_rows(output / "default_test_metrics.csv", [row for row in metrics if row["split"] == "test"
                                                   and row["margin"] == defaults[row["policy"]]["margin"]])
    configuration = {
        "run_time_utc": datetime.now(timezone.utc).isoformat(), "horizon_minutes": 10,
        "interval_seconds": interval_seconds, "margins": MARGINS,
        "capacity_rule": "max(0, forecast) * (1 + margin)",
        "reactive_rule": "latest available input demand * (1 + margin); equivalent to persistence",
        "default_selection": "per policy: lowest mean capacity with validation shortfall <= 1%; otherwise 20%",
        "shortfall_limit_pct": SHORTFALL_LIMIT_PCT, "selected_defaults": defaults,
        "deficit_volume": "sum(max(actual-capacity, 0)) * 600 / 8; decimal MB",
        "overprovision": "mean(max(capacity-actual, 0)) in Mbps; excess volume also recorded",
        "served_demand_to_capacity_ratio": "sum(min(actual, capacity)) / sum(capacity); blank if capacity sum is zero",
        "evaluation_scope": "eligible validation/test intervals only; excluded gaps are not filled or integrated",
        "limitation": "abstract offline capacity pool; shortfall volume is unserved demand, not measured packet loss; no physical routing, latency or live collector-delay model",
        "source_sha256": {str(path.relative_to(project)).replace('\\', '/'): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in prepared_paths + result_paths},
    }
    (output / "run_config.json").write_text(json.dumps(configuration, indent=2) + "\n", encoding="utf-8")
    for policy, chosen in defaults.items():
        test = next(row for row in metrics if row["policy"] == policy and row["split"] == "test" and row["margin"] == chosen["margin"])
        print(f"{policy}: margin={chosen['margin']:.0%}; validation shortfall={chosen['validation_shortfall_pct']:.2f}%; "
              f"1% target met={chosen['validation_target_met']}; test shortfall={test['shortfall_pct']:.2f}%")
    print(f"Saved {len(metrics)} metric rows and {len(replay)} replay rows in {output}")


if __name__ == "__main__":
    main()
