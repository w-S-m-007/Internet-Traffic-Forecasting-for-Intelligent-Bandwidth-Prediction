"""Behavioral checks for exclusions, causal features, and training-only fitting."""

import unittest

import numpy as np

from data_processing.prepare_dataset import FEATURES, HISTORY, fit_scalers, select_windows, window_features


class PreparationTests(unittest.TestCase):
    def test_exclusion_between_origin_and_target_rejects_window(self):
        blocked = np.zeros(100, dtype=bool)
        blocked[20] = True
        usable = np.ones(100, dtype=bool)
        starts, origins, targets = select_windows(blocked, usable, usable, np.ones(100), 6)
        # History 0..17 and target 23 are unmarked, but intervening row 20 is not.
        self.assertNotIn(23, targets.tolist())
        self.assertIn(44, targets.tolist())  # History 21..38 and target 44 avoid it.
        for start, target in zip(starts, targets):
            self.assertFalse(blocked[start:target + 1].any())

    def test_future_values_do_not_change_past_rolling_features(self):
        base = np.ones((60, 6))
        base[:, 0] = np.arange(60)
        original = window_features(base, np.array([1]))
        changed = base.copy()
        changed[10:, 0] += 10000
        revised = window_features(changed, np.array([1]))
        np.testing.assert_array_equal(original[:, :9], revised[:, :9])
        self.assertEqual(original[0, 0, -2], 1)  # Partial warm-up uses one observation.
        self.assertEqual(original[0, 0, -1], 0)

    def test_holdout_values_do_not_change_training_scalers(self):
        inputs = np.arange(4 * HISTORY * len(FEATURES), dtype=float).reshape(4, HISTORY, len(FEATURES))
        targets = np.array([10., 20., 30., 40.])
        splits = np.array([0, 0, 1, 2])
        original = fit_scalers(inputs, targets, splits)
        inputs[2:] += 1000000
        targets[2:] += 1000000
        self.assertEqual(original, fit_scalers(inputs, targets, splits))
        self.assertEqual(original["y_mean"], 15)


if __name__ == "__main__":
    unittest.main()
