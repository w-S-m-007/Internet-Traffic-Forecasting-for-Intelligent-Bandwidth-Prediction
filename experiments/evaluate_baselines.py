"""Evaluate persistence and four-observation averages on saved forecast windows."""

import argparse
import csv
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import numpy as np

from experiments.forecast_metrics import forecast_metrics


def persistence(history):
    return float(history[-1])


def moving_average_4(history):
    return float(np.mean(history[-4:]))


PREDICTORS = {"persistence": persistence, "moving_average_4": moving_average_4}
WARMUP = 25
REPEATS = 1000


def inference_ms(predictor, histories):
    for index in range(WARMUP):
        predictor(histories[index % len(histories)])
    start = perf_counter()
    for index in range(REPEATS):
        predictor(histories[index % len(histories)])
    return 1000 * (perf_counter() - start) / REPEATS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--horizon", type=int, choices=[10, 30, 60], default=10)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    prepared = project / "data/prepared"
    array_path = prepared / f"windows_{args.horizon}min.npz"
    metadata_path = prepared / f"windows_{args.horizon}min.csv"
    if not array_path.exists() or not metadata_path.exists():
        raise FileNotFoundError("Run python -m data_processing.prepare_dataset first")
    with np.load(array_path, allow_pickle=False) as artifact:
        histories = artifact["input_mbps"].copy()
        actual = artifact["target_mbps"].copy()
        splits = artifact["split"].copy()
    with metadata_path.open(newline="", encoding="utf-8-sig") as handle:
        metadata = list(csv.DictReader(handle))
    if histories.ndim != 2 or histories.shape[1] < 4 or len(histories) != len(actual):
        raise ValueError("Expected aligned history arrays with at least four observations")
    if len(metadata) != len(actual) or splits.shape != actual.shape:
        raise ValueError("Metadata, split codes, and targets do not align")
    if not np.isfinite(histories).all() or not np.isfinite(actual).all():
        raise ValueError("Baseline data contains nonfinite values")
    names = {0: "train", 1: "validation", 2: "test"}
    if any(int(code) not in names or row["split"] != names[int(code)]
           for row, code in zip(metadata, splits)):
        raise ValueError("CSV and NPZ split assignments disagree")
    output = project / "results/baselines" / f"{args.horizon}min"
    output.mkdir(parents=True, exist_ok=True)
    metric_rows, prediction_rows = [], []
    predictions_by_model = {}
    for model, predictor in PREDICTORS.items():
        predictions = np.array([predictor(history) for history in histories])
        predictions_by_model[model] = predictions
        for code in [1, 2]:
            indices = np.flatnonzero(splits == code)
            if not len(indices):
                raise ValueError(f"Empty {names[code]} set")
            metrics = forecast_metrics(actual[indices], predictions[indices])
            metric_rows.append({"model": model, "horizon_minutes": args.horizon,
                                "split": names[code], **metrics,
                                "training_time_s": 0.0,
                                "cpu_inference_ms": inference_ms(predictor, histories[indices])})
            for index in indices:
                prediction_rows.append({
                    "model": model, "horizon_minutes": args.horizon,
                    "split": names[code], "target_id": metadata[index]["target_id"],
                    "forecast_origin_utc": metadata[index]["forecast_origin_utc"],
                    "target_interval_start_utc": metadata[index]["target_interval_start_utc"],
                    "target_completion_utc": metadata[index]["target_completion_utc"],
                    "actual_mbps": actual[index], "predicted_mbps": predictions[index],
                })
            print(f"{model}, {names[code]}: MAE={metrics['mae_mbps']:.3f} Mbps; "
                  f"RMSE={metrics['rmse_mbps']:.3f} Mbps; MAPE={metrics['mape_pct']}; R2={metrics['r2']}")
    for name, rows in [("metrics.csv", metric_rows), ("predictions.csv", prediction_rows)]:
        with (output / name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    configuration = {
        "run_time_utc": datetime.now(timezone.utc).isoformat(),
        "horizon_minutes": args.horizon, "models": list(PREDICTORS),
        "moving_average_records": 4, "moving_average_minutes": 40,
        "metric_units": "nominal recorded Mbps; MAPE percent",
        "mape_rule": "positive targets only, exclusions counted",
        "undefined_metrics": "blank CSV cell for undefined MAPE or R2",
        "training_time_note": "zero because these predictors have no fitting step",
        "cpu_timing": {"unit": "milliseconds per single-window prediction",
                       "warmup_calls": WARMUP, "timed_calls": REPEATS,
                       "method": "preloaded NumPy histories, cyclic chronological windows; includes loop/call overhead; excludes file I/O and preprocessing"},
        "python": platform.python_version(), "numpy": np.__version__,
        "platform": platform.platform(), "processor": platform.processor(),
        "artifact_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                            for path in [array_path, metadata_path, prepared / "preparation_config.json"]},
        "selection_rule": "baseline definitions fixed before evaluation; do not tune models using test scores",
    }
    (output / "run_config.json").write_text(json.dumps(configuration, indent=2) + "\n", encoding="utf-8")
    plot_prefix(output, metadata, actual, predictions_by_model, splits, args.horizon)
    print(f"Saved predictions, metrics, configuration, and plot in {output}")


def plot_prefix(output, metadata, actual, predictions, splits, horizon):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    indices = np.flatnonzero(splits == 2)[:144]
    dates = [datetime.fromisoformat(metadata[index]["target_completion_utc"]) for index in indices]
    figure, axis = plt.subplots(figsize=(12, 4), constrained_layout=True)
    axis.plot(dates, actual[indices], color="#111827", linewidth=1.5, label="Actual")
    for model, values in predictions.items():
        axis.plot(dates, values[indices], linewidth=1, alpha=.85, label=model)
    axis.set(title=f"{horizon}-minute forecast comparison: first {len(indices)} test intervals",
             ylabel="Nominal recorded Mbps",
             xlabel=f"Target interval completion (UTC), starting {dates[0].date()}")
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%d %H:%M", tz=timezone.utc))
    axis.legend()
    axis.grid(alpha=.2)
    figure.savefig(output / "test_prefix.png", dpi=160)
    plt.close(figure)


if __name__ == "__main__":
    main()
