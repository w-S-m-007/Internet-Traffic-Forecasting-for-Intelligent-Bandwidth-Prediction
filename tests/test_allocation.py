"""Hand-check allocation arithmetic, validation selection and forecast joins."""

import unittest

import numpy as np

from experiments.evaluate_allocation import MARGINS, align_forecasts, allocate, select_margin


class AllocationTests(unittest.TestCase):
    def test_flat_traffic(self):
        arrays, metrics = allocate([100, 100], [100, 100], .10)
        np.testing.assert_allclose(arrays["capacity"], [110, 110])
        self.assertEqual(metrics["shortfall_intervals"], 0)
        self.assertEqual(metrics["deficit_volume_mb"], 0)
        self.assertAlmostEqual(metrics["mean_overprovision_mbps"], 10)
        self.assertAlmostEqual(metrics["served_demand_to_capacity_ratio"], 100 / 110)

    def test_sudden_spike_and_decimal_megabytes(self):
        _, reactive = allocate([100, 200], [100, 100], .10)
        _, proactive = allocate([100, 200], [100, 200], .10)
        self.assertEqual(reactive["shortfall_pct"], 50)
        self.assertAlmostEqual(reactive["deficit_volume_mb"], 90 * 600 / 8)
        self.assertAlmostEqual(reactive["mean_overprovision_mbps"], 5)
        self.assertAlmostEqual(reactive["served_demand_to_capacity_ratio"], 210 / 220)
        self.assertEqual(proactive["shortfall_intervals"], 0)

    def test_zero_capacity_and_negative_forecast(self):
        arrays, scores = allocate([0, 10], [-5, 0], .20)
        np.testing.assert_array_equal(arrays["capacity"], [0, 0])
        self.assertEqual(scores["deficit_volume_mb"], 750)
        self.assertIsNone(scores["served_demand_to_capacity_ratio"])

    def test_invalid_demand_is_rejected(self):
        for demand, forecast in (([-1], [0]), ([np.nan], [0]), ([0], [np.inf]), ([], [])):
            with self.assertRaises(ValueError):
                allocate(demand, forecast, .1)

    def test_selection_uses_validation_and_discloses_fallback(self):
        rows = [{"margin": margin, "split": "validation", "shortfall_pct": pct,
                 "mean_capacity_mbps": capacity} for margin, pct, capacity in
                zip(MARGINS, [3, 1, .5, .2], [105, 110, 115, 120])]
        self.assertEqual(select_margin(rows)["margin"], .10)
        for row in rows:
            row["shortfall_pct"] = 2
        fallback = select_margin(rows)
        self.assertEqual(fallback["margin"], .20)
        self.assertFalse(fallback["validation_target_met"])
        rows[0]["split"] = "test"
        with self.assertRaises(ValueError):
            select_margin(rows)

    def test_forecasts_join_by_key_and_reject_inconsistent_records(self):
        metadata = [{"split": "test", "target_id": str(index), "forecast_origin_utc": "origin",
                     "target_interval_start_utc": "start", "target_completion_utc": "end"} for index in (1, 2)]
        rows = [{**row, "model": "lstm", "horizon_minutes": "10", "actual_mbps": "100",
                 "predicted_mbps": str(predicted)} for row, predicted in zip(metadata, (90, 110))]
        aligned = align_forecasts(rows[::-1], metadata, [100, 100], ["lstm"])
        np.testing.assert_array_equal(aligned["lstm"], [90, 110])
        with self.assertRaises(ValueError):
            align_forecasts(rows[:1], metadata, [100, 100], ["lstm"])
        with self.assertRaises(ValueError):
            align_forecasts(rows + rows[:1], metadata, [100, 100], ["lstm"])
        rows[0]["target_completion_utc"] = "different"
        with self.assertRaises(ValueError):
            align_forecasts(rows, metadata, [100, 100], ["lstm"])


if __name__ == "__main__":
    unittest.main()
