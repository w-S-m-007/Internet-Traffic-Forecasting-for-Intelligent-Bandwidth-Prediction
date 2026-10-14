"""Check baseline definitions and forecasting metric edge cases."""

import unittest

import numpy as np

from evaluate_baselines import moving_average_4, persistence
from forecast_metrics import forecast_metrics


class BaselineTests(unittest.TestCase):
    def test_baselines_on_flat_and_changing_history(self):
        history = np.full(18, 10.)
        self.assertEqual(persistence(history), 10)
        self.assertEqual(moving_average_4(history), 10)
        history[-1] = 50
        self.assertEqual(persistence(history), 50)
        self.assertEqual(moving_average_4(history), 20)

    def test_metric_arithmetic(self):
        metrics = forecast_metrics([10, 20], [8, 25])
        self.assertEqual(metrics["mae_mbps"], 3.5)
        self.assertAlmostEqual(metrics["rmse_mbps"], np.sqrt(14.5))
        self.assertAlmostEqual(metrics["mape_pct"], 22.5)
        self.assertAlmostEqual(metrics["r2"], .42)

    def test_zero_targets_excluded_only_from_mape(self):
        metrics = forecast_metrics([0, 10], [5, 8])
        self.assertEqual(metrics["n_samples"], 2)
        self.assertEqual(metrics["mape_excluded"], 1)
        self.assertEqual(metrics["mape_included"], 1)
        self.assertEqual(metrics["mape_pct"], 20)
        self.assertEqual(metrics["mae_mbps"], 3.5)

    def test_undefined_scores_remain_undefined(self):
        self.assertIsNone(forecast_metrics([10, 10], [10, 10])["r2"])
        self.assertIsNone(forecast_metrics([0, 0], [0, 0])["mape_pct"])


if __name__ == "__main__":
    unittest.main()
