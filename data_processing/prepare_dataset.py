"""Regenerate the Day 2 data artifacts. This command does not train models."""

import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TypedDict

import numpy as np

from data_processing import build_features
from data_processing import mark_exclusions
from data_processing import mark_segments


HISTORY = 18
HORIZONS = (1, 3, 6)
BASE_FEATURES = ["input_traffic_mbps", "hour_sin", "hour_cos",
                 "weekday_sin", "weekday_cos", "input_missing"]
FEATURES = BASE_FEATURES + ["rolling_mean_6", "rolling_std_6"]


class Scalers(TypedDict):
    x_mean: list[float]
    x_std: list[float]
    y_mean: float
    y_std: float


def select_windows(blocked, usable_input, usable_target, segments, lead):
    targets = np.arange(HISTORY + lead - 1, len(blocked))
    origins = targets - lead
    starts = origins - HISTORY + 1
    prefix = np.r_[0, np.cumsum(blocked)]
    history_indices = starts[:, None] + np.arange(HISTORY)
    allowed = ((prefix[targets + 1] - prefix[starts] == 0)
               & (segments[starts] == segments[targets])
               & usable_input[history_indices].all(axis=1) & usable_target[targets])
    return starts[allowed], origins[allowed], targets[allowed]


def window_features(base, starts):
    inputs = base[starts[:, None] + np.arange(HISTORY)]
    rolling = np.empty((*inputs.shape[:2], 2))
    for position in range(HISTORY):
        past = inputs[:, max(0, position - 5):position + 1, 0]
        rolling[:, position, 0] = past.mean(axis=1)
        rolling[:, position, 1] = past.std(axis=1)
    return np.concatenate([inputs, rolling], axis=2)


def fit_scalers(inputs, targets, splits) -> Scalers:
    training = splits == 0
    if not training.any():
        raise ValueError("No training windows")
    x_train = inputs[training].reshape(-1, len(FEATURES))
    x_mean, x_std = x_train.mean(axis=0), x_train.std(axis=0)
    x_std[x_std == 0] = 1
    y_mean, y_std = float(targets[training].mean()), float(targets[training].std())
    return {"x_mean": x_mean.tolist(), "x_std": x_std.tolist(),
            "y_mean": y_mean, "y_std": y_std if y_std else 1.0}


def save_csv(path, columns, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        writer.writerows(rows)


def main():
    project = Path(__file__).resolve().parents[1]
    raw = project / "data/raw/cesnet/sample"
    source_hashes = {name: hashlib.sha256((raw / name).read_bytes()).hexdigest()
                     for name in ["institution_0.csv", "times_10_minutes.csv"]}
    mark_segments.main()
    mark_exclusions.main()
    build_features.main()
    output = project / "data/prepared"
    with (output / "institution_0_features.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    stamps = [datetime.fromisoformat(row["timestamp_utc"]) for row in rows]
    seconds = np.array([stamp.timestamp() for stamp in stamps])
    segments = np.array([int(row["segment_id"]) for row in rows])
    if not (np.diff(seconds) > 0).all():
        raise ValueError("Timestamps must increase")
    if not (np.diff(seconds)[np.diff(segments) == 0] == 600).all():
        raise ValueError("A segment is not regular at 600 seconds")
    blocked = np.array([row["excluded_for_outage"] == "1" or
                        row["excluded_for_boundary"] == "1" for row in rows])
    usable_input = np.array([row["usable_input"] == "1" for row in rows])
    usable_target = np.array([row["usable_target"] == "1" for row in rows])
    base = np.array([[float(row[key]) if row[key] else np.nan
                      for key in BASE_FEATURES] for row in rows])
    rates = np.array([float(row["recorded_traffic_mbps"])
                      if row["recorded_traffic_mbps"] else np.nan for row in rows])
    # Cut points use the complete ordered timeline before policy exclusions.
    validation_index, test_index = int(len(rows) * .70), int(len(rows) * .85)
    split_by_row = np.where(np.arange(len(rows)) < validation_index, 0,
                           np.where(np.arange(len(rows)) < test_index, 1, 2))
    names = ["train", "validation", "test"]
    completion = [stamp + timedelta(seconds=600) for stamp in stamps]
    config = {
        "institution_id": 0, "interval_seconds": 600, "history_records": HISTORY,
        "horizons_minutes": [lead * 10 for lead in HORIZONS], "features": FEATURES,
        "rolling_window_records": 6, "rolling_min_records": 1, "rolling_std_ddof": 0,
        "rolling_scope": "within each input window, through current historical observation",
        "split_ratios": [0.70, 0.15, 0.15],
        "validation_start_utc": completion[validation_index].isoformat(),
        "test_start_utc": completion[test_index].isoformat(),
        "split_basis": "target nominal interval completion; cuts fixed before exclusions",
        "availability_assumption": "input interval completes at supplied start plus 600 seconds; offline only",
        "outage_first_date": mark_exclusions.EXCLUDE_FIRST.isoformat(),
        "outage_last_date": mark_exclusions.EXCLUDE_LAST.isoformat(),
        "boundary_rule": "exclude first and last observation of each timestamp segment",
        "scaler_fit": "training windows only, separately for each horizon",
        "source_sha256": source_hashes,
    }
    counts = []
    checks = []
    save_csv(output / "timeline_splits.csv",
             ["id_time", "interval_start_utc", "nominal_completion_utc", "split", "usable_target"],
             [(row["id_time"], stamp.isoformat(), end.isoformat(), names[int(split)], row["usable_target"])
              for row, stamp, end, split in zip(rows, stamps, completion, split_by_row)])
    for lead in HORIZONS:
        starts, origins, targets = select_windows(blocked, usable_input, usable_target, segments, lead)
        inputs = window_features(base, starts)
        y = rates[targets]
        splits = split_by_row[targets]
        if not np.isfinite(inputs).all() or not np.isfinite(y).all():
            raise ValueError("A usable window contains a nonfinite value")
        scalers = fit_scalers(inputs, y, splits)
        x_mean, x_std = np.array(scalers["x_mean"]), np.array(scalers["x_std"])
        scaled_x = ((inputs - x_mean) / x_std).astype(np.float32)
        scaled_y = ((y - scalers["y_mean"]) / scalers["y_std"]).astype(np.float32)
        horizon = lead * 10
        np.savez_compressed(output / f"windows_{horizon}min.npz", X=scaled_x, y=scaled_y,
                            target_mbps=y, input_mbps=inputs[:, :, 0], split=splits,
                            start_row=starts, origin_row=origins, target_row=targets)
        (output / f"scalers_{horizon}min.json").write_text(json.dumps(scalers, indent=2) + "\n", encoding="utf-8")
        save_csv(output / f"windows_{horizon}min.csv",
                 ["input_first_id", "input_last_id", "target_id", "forecast_origin_utc",
                  "target_interval_start_utc", "target_completion_utc", "split", "segment_id"],
                 [(rows[int(a)]["id_time"], rows[int(b)]["id_time"], rows[int(c)]["id_time"],
                   completion[int(b)].isoformat(), stamps[int(c)].isoformat(), completion[int(c)].isoformat(),
                   names[int(split)], rows[int(c)]["segment_id"])
                  for a, b, c, split in zip(starts, origins, targets, splits)])
        # Check every complete path, rather than only its input and target endpoints.
        for start, origin, target in zip(starts, origins, targets):
            span = slice(int(start), int(target) + 1)
            assert not blocked[span].any()
            assert (np.diff(seconds[span]) == 600).all()
            assert seconds[target] - seconds[origin] == horizon * 60
        assert (seconds[targets[splits == 0]] < seconds[validation_index]).all()
        assert (seconds[targets[splits == 1]] >= seconds[validation_index]).all()
        assert (seconds[targets[splits == 1]] < seconds[test_index]).all()
        assert (seconds[targets[splits == 2]] >= seconds[test_index]).all()
        restored = scaled_y.astype(float) * scalers["y_std"] + scalers["y_mean"]
        assert np.allclose(restored, y, atol=1e-4, rtol=1e-6)
        split_counts = [int((splits == code).sum()) for code in range(3)]
        if not all(split_counts):
            raise ValueError("Every horizon must have nonempty train, validation, and test sets")
        counts.append([horizon, *split_counts, len(targets)])
        checks.append(f"{horizon} minutes: complete paths, regular timestamps, split assignment, finite features, inverse scaling PASS")
        print(f"{horizon} minutes: train={split_counts[0]}, validation={split_counts[1]}, test={split_counts[2]}")
    save_csv(output / "window_counts.csv", ["horizon_minutes", "train", "validation", "test", "total"], counts)
    (output / "preparation_config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    assert all(hashlib.sha256((raw / name).read_bytes()).hexdigest() == digest
               for name, digest in source_hashes.items())
    checks.append("Raw input SHA256 hashes unchanged PASS")
    (output / "preparation_checks.txt").write_text("\n".join(checks) + "\n", encoding="utf-8")
    plot_quality(output, stamps, rates, blocked, rows, completion[validation_index], completion[test_index])
    print(f"Prepared artifacts saved in {output}; no models trained.")


def plot_quality(output, stamps, rates, blocked, rows, validation_start, test_start):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    figure, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=True, constrained_layout=True)
    axes[0].plot(stamps, rates, linewidth=.4, color="#2563eb")
    axes[0].set(title="Institution 0: recorded traffic and preparation policies", ylabel="Nominal recorded Mbps")
    axes[0].axvline(validation_start, color="#15803d", linestyle="--", label="Validation starts")
    axes[0].axvline(test_start, color="#7e22ce", linestyle="--", label="Test starts")
    axes[0].legend(loc="upper left")
    axes[1].step(stamps, blocked.astype(int), where="post", color="#b91c1c", label="Policy exclusion")
    axes[1].plot(stamps, [int(row["input_missing"]) for row in rows], linestyle="--", color="#2563eb", label="Missing byte cell")
    axes[1].set(ylabel="Flag (0 or 1)", xlabel="Supplied interval starts expressed in UTC", ylim=(-.1, 1.15))
    axes[1].legend(loc="upper left")
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%b %Y", tz=timezone.utc))
    for axis in axes:
        axis.grid(alpha=.2)
    figure.savefig(output / "traffic_quality.png", dpi=160)
    plt.close(figure)


if __name__ == "__main__":
    main()
