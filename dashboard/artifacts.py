"""Read and validate saved results; this module never imports training code."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from experiments.evaluate_allocation import MARGINS, allocate, select_margin
from experiments.forecast_metrics import forecast_metrics


MODEL_LABELS = {"persistence": "Persistence", "moving_average_4": "Moving average",
                "lstm": "LSTM", "gru": "GRU", "transformer": "Transformer"}
SOURCES = {"baselines": {"persistence", "moving_average_4"}, "lstm": {"lstm"},
           "gru": {"gru"}, "transformer": {"transformer"}}
TIME_FIELDS = ["forecast_origin_utc", "target_interval_start_utc", "target_completion_utc"]


class ArtifactError(ValueError):
    """Saved files are incomplete or scientifically inconsistent."""


@dataclass
class ForecastArtifacts:
    horizon: int
    metrics: pd.DataFrame
    predictions: pd.DataFrame
    configs: dict


def fingerprint(project: Path):
    """Include source mtimes/sizes in the UI cache key so replaced runs reload."""
    return tuple(sorted((str(path.relative_to(project)), path.stat().st_mtime_ns, path.stat().st_size)
                        for path in (project / "results").rglob("*")
                        if path.is_file() and path.name in ("metrics.csv", "predictions.csv", "run_config.json")))


def available_horizons(project: Path):
    return [horizon for horizon in (10, 30, 60) if any(
        all((project / f"results/{source}/{horizon}min" / name).is_file()
            for name in ("metrics.csv", "predictions.csv", "run_config.json")) for source in SOURCES)]


def assert_scores(saved, calculated):
    for name, value in calculated.items():
        if value is None:
            valid = pd.isna(saved[name])
        else:
            valid = np.isclose(float(saved[name]), value, rtol=1e-8, atol=1e-8)
        if not valid:
            raise ArtifactError(f"Saved {name} differs from its forecast/replay observations")


def load_forecasts(project: Path, horizon: int):
    all_metrics, all_predictions, configs = [], [], {}
    signatures = {}
    reference = None
    for source, models in SOURCES.items():
        folder = project / f"results/{source}/{horizon}min"
        paths = [folder / name for name in ("metrics.csv", "predictions.csv", "run_config.json")]
        if not any(path.exists() for path in paths):
            continue
        if not all(path.is_file() for path in paths):
            raise ArtifactError(f"Incomplete saved run: results/{source}/{horizon}min")
        metrics = pd.read_csv(paths[0])
        predictions = pd.read_csv(paths[1], dtype={"target_id": "string"})
        config = json.loads(paths[2].read_text(encoding="utf-8"))
        if config["horizon_minutes"] != horizon:
            raise ArtifactError("Run configuration has a different forecast horizon")
        for name in (f"windows_{horizon}min.npz", f"windows_{horizon}min.csv", "preparation_config.json"):
            digest = config["artifact_sha256"][name]
            if name in signatures and signatures[name] != digest:
                raise ArtifactError("Model runs use different prepared data; regenerate matching results")
            signatures[name] = digest
        if set(predictions["model"]) != models or set(metrics["model"]) != models:
            raise ArtifactError(f"Unexpected model identities in {source}")
        if predictions.duplicated(["model", "split", "target_id"]).any() or metrics.duplicated(["model", "split"]).any():
            raise ArtifactError("Duplicate model/target or metric rows")
        if predictions["target_id"].isna().any() or predictions["target_id"].str.len().eq(0).any():
            raise ArtifactError("Missing forecast target IDs")
        for name in TIME_FIELDS:
            predictions[name] = pd.to_datetime(predictions[name], utc=True, errors="raise")
        actual = predictions["actual_mbps"].to_numpy(dtype=float)
        predicted = predictions["predicted_mbps"].to_numpy(dtype=float)
        if not np.isfinite(actual).all() or not np.isfinite(predicted).all() or (actual < 0).any():
            raise ArtifactError("Forecasts contain invalid demand or prediction values")
        if not predictions["horizon_minutes"].eq(horizon).all() or not metrics["horizon_minutes"].eq(horizon).all():
            raise ArtifactError("Mixed horizons in saved CSVs")
        lead = predictions["target_completion_utc"] - predictions["forecast_origin_utc"]
        duration = predictions["target_completion_utc"] - predictions["target_interval_start_utc"]
        if not lead.eq(pd.Timedelta(minutes=horizon)).all() or not duration.eq(pd.Timedelta(seconds=600)).all():
            raise ArtifactError("Forecast lead or interval duration does not match the experiment")
        for model in MODEL_LABELS:
            if model not in models:
                continue
            frame = predictions[predictions["model"] == model].sort_values(["split", "target_completion_utc"])
            if set(frame["split"]) != {"validation", "test"}:
                raise ArtifactError("Only nonempty validation/test results are expected")
            aligned = frame[["split", "target_id", *TIME_FIELDS, "actual_mbps"]].reset_index(drop=True)
            if reference is not None:
                if not reference.drop(columns="actual_mbps").equals(aligned.drop(columns="actual_mbps")):
                    raise ArtifactError("Models do not share the same timestamped targets")
                if not np.allclose(reference["actual_mbps"], aligned["actual_mbps"], rtol=1e-10, atol=1e-9):
                    raise ArtifactError("Models disagree about actual demand")
            else:
                reference = aligned
            for split in ("validation", "test"):
                selected = frame[frame["split"] == split]
                if not selected["target_completion_utc"].is_unique:
                    raise ArtifactError("Repeated target timestamps")
                saved = metrics[(metrics["model"] == model) & (metrics["split"] == split)]
                if len(saved) != 1:
                    raise ArtifactError("Expected one metric row per model and split")
                assert_scores(saved.iloc[0], forecast_metrics(selected["actual_mbps"], selected["predicted_mbps"]))
            configs[model] = config
        all_metrics.append(metrics)
        all_predictions.append(predictions)
    if not all_metrics:
        raise ArtifactError("No saved forecasts are available. Prepare data and run the forecast commands first.")
    return ForecastArtifacts(horizon, pd.concat(all_metrics, ignore_index=True),
                             pd.concat(all_predictions, ignore_index=True), configs)


def model_forecasts(artifacts, model, split):
    return artifacts.predictions[(artifacts.predictions["model"] == model)
                                & (artifacts.predictions["split"] == split)].sort_values("target_completion_utc").reset_index(drop=True)


def allocation_snapshot(artifacts, model, split, margin):
    if artifacts.horizon != 10 or model not in ("lstm", "moving_average_4"):
        raise ArtifactError("Allocation has been evaluated only for 10-minute LSTM and moving-average forecasts")
    proactive = model_forecasts(artifacts, model, split)
    reactive = model_forecasts(artifacts, "persistence", split)
    if proactive.empty or reactive.empty or proactive["target_id"].tolist() != reactive["target_id"].tolist():
        raise ArtifactError("Reactive and proactive allocation targets differ")
    frame = proactive.copy()
    scores = {}
    for name, predictions in (("reactive", reactive["predicted_mbps"]), ("proactive", proactive["predicted_mbps"])):
        arrays, scores[name] = allocate(frame["actual_mbps"], predictions, margin, 600)
        for field, values in arrays.items():
            frame[f"{name}_{field}"] = values
    return frame, scores


def load_allocation(project, artifacts):
    folder = project / "results/allocation/10min"
    if artifacts.horizon != 10 or not folder.exists():
        return None
    metrics = pd.read_csv(folder / "metrics.csv")
    config = json.loads((folder / "run_config.json").read_text(encoding="utf-8"))
    if config["interval_seconds"] != 600 or config["horizon_minutes"] != 10 or config["margins"] != list(MARGINS):
        raise ArtifactError("Allocation configuration differs from the documented experiment")
    for relative, digest in config["source_sha256"].items():
        if not relative.startswith("results/"):
            continue
        path = (project / relative).resolve()
        if not path.is_relative_to(project.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ArtifactError("Allocation forecasts have changed; regenerate allocation before viewing it")
    if len(metrics) != 24 or metrics.duplicated(["policy", "split", "margin"]).any():
        raise ArtifactError("Expected the 24 saved allocation comparisons")
    for model in ("lstm", "moving_average_4"):
        for split in ("validation", "test"):
            for margin in MARGINS:
                _, scores = allocation_snapshot(artifacts, model, split, margin)
                for name, policy in (("reactive", "reactive"), ("proactive", f"proactive_{model}")):
                    selected = metrics[(metrics["policy"] == policy) & (metrics["split"] == split)
                                       & np.isclose(metrics["margin"], margin)]
                    if len(selected) != 1:
                        raise ArtifactError("Missing allocation policy/split/margin result")
                    assert_scores(selected.iloc[0], scores[name])
    if set(config["selected_defaults"]) != {"reactive", "proactive_lstm", "proactive_moving_average_4"}:
        raise ArtifactError("Missing validation-selected allocation defaults")
    for policy, chosen in config["selected_defaults"].items():
        validation = metrics[(metrics["policy"] == policy) & (metrics["split"] == "validation")]
        expected = select_margin(validation.to_dict("records"))
        if chosen["validation_target_met"] != expected["validation_target_met"] or any(
                not np.isclose(chosen[name], expected[name], rtol=1e-10, atol=1e-10)
                for name in ("margin", "validation_shortfall_pct", "validation_mean_capacity_mbps")):
            raise ArtifactError("Allocation defaults differ from validation-only selection")
    return config
