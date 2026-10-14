"""Forecast errors in original nominal Mbps, shared by future predictors."""

from typing import TypedDict

import numpy as np


class ForecastMetrics(TypedDict):
    n_samples: int
    mae_mbps: float
    rmse_mbps: float
    mape_pct: float | None
    mape_included: int
    mape_excluded: int
    r2: float | None


def forecast_metrics(actual, predicted) -> ForecastMetrics:
    actual, predicted = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    if actual.ndim != 1 or predicted.shape != actual.shape or not actual.size:
        raise ValueError("Expected equal, nonempty one-dimensional forecast arrays")
    if not np.isfinite(actual).all() or not np.isfinite(predicted).all():
        raise ValueError("Forecast metrics require finite observations and predictions")
    error = predicted - actual
    positive = actual > 0
    total_variation = float(np.square(actual - actual.mean()).sum())
    return {
        "n_samples": len(actual),
        "mae_mbps": float(np.abs(error).mean()),
        "rmse_mbps": float(np.sqrt(np.square(error).mean())),
        "mape_pct": float(100 * np.mean(np.abs(error[positive]) / actual[positive]))
        if positive.any() else None,
        "mape_included": int(positive.sum()),
        "mape_excluded": int((~positive).sum()),
        "r2": float(1 - np.square(error).sum() / total_variation)
        if len(actual) > 1 and total_variation > 0 else None,
    }
