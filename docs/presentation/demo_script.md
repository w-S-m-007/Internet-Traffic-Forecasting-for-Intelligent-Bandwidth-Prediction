# Demonstration and speaking guide

Allow about 8 minutes for the slides and 3 minutes for the dashboard. The slide deck includes detailed speaker notes and source references. Add presenter names and your institution in PowerPoint if your submission requires them.

## Before presenting

From Git Bash at the repository root:

```bash
source VirtEnv/Scripts/activate
python -m streamlit run dashboard/app.py
```

Open `http://127.0.0.1:8501`. Keep the saved artifacts in `results/` available. The interface reads these files without training models. Verify the three horizon choices and the allocation view before the presentation. Keep the slide PDF and backup recording available if the live interface cannot start.

## Slide narration

1. **Project aim.** We forecast recorded network traffic and use the prediction in an offline capacity simulation. The experiment evaluates one CESNET institution.
2. **Research scope.** First compare forecasting errors. Then evaluate what those forecasts imply for capacity and shortfalls.
3. **Dataset.** We use institution 0 from CESNET-TimeSeries24, chosen by data coverage before training. Its 40,298 observations span October 2023 to July 2024. We convert bytes to a nominal bidirectional Mbps rate.
4. **Preparation.** Timestamp irregularities form six blocks. We exclude the documented conservative outage dates and guard block endpoints. A window cannot cross these boundaries. Scalers use training data only.
5. **Evaluation.** Each input has 18 observations covering three hours. Separate models predict 10, 30 and 60 minutes ahead. Target timestamps determine chronological splits.
6. **Models.** Compare persistence and a four-observation mean with compact LSTM, GRU and Transformer models. All neural models use seed 42 and validation early stopping.
7. **Main result.** Transformer gives the lowest test RMSE at 10 minutes. GRU gives the lowest at 30 and 60 minutes. These are single-run comparisons, without significance claims.
8. **Metric differences.** At 60 minutes, GRU has the lowest MAE and RMSE, while LSTM has the lowest MAPE. Model quality depends on the metric as well as the horizon.
9. **Replay.** The plot shows the first 72 chronological LSTM test forecasts. Full-split metrics cover every eligible target, not just this excerpt.
10. **Allocation.** Multiply the nonnegative forecast by one plus the safety margin. A 100 Mbps forecast with a 10% margin gives 110 Mbps capacity. If demand becomes 200 Mbps, the 90 Mbps deficit corresponds to 6,750 MB over ten minutes.
11. **Tradeoff.** At the same 20% margin, neural policies produce fewer shortfalls than reactive capacity, but allocate more capacity. LSTM has the lowest test shortfall frequency and the largest mean capacity of these policies.
12. **Unmet target.** Every tested margin fails the 1% validation shortfall requirement. All policies therefore use the documented 20% fallback. This experiment does not deliver a service guarantee.
13. **Demonstration.** Show the saved-results dashboard using the steps below.
14. **Findings and limits.** Forecasting can support capacity planning, but selecting a model requires multiple error measures and an explicit capacity objective. Further experiments need more institutions, more seeds, uncertainty estimates and operational validation.

15. **Conclusion.** We built a reproducible forecasting-to-capacity prototype. Transformer leads ten-minute test RMSE and GRU leads thirty and sixty minutes. At the same 20% margin, LSTM reduces shortfall frequency while using more capacity. The 1% validation target remains unmet, and live deployment requires further validation.

## Live dashboard sequence

1. Choose **Forecasts**, **Test**, **10 minutes**, and **LSTM**. Explain that MAE and RMSE use the complete eligible split.
2. Move the historical replay control. Show that the visible chart changes while full-split scores remain stable. Explain that this is held-out historical replay.
3. Choose **60 minutes** and **GRU**. Read the generated RMSE of about **34.785 Mbps**. Open **Comparison** to show all five predictors and explain why persistence remains necessary.
4. Return to the **10-minute** horizon and open **Allocation**. Choose **LSTM** and **20%** margin. Compare proactive and reactive shortfall and capacity. Select GRU and Transformer to show their tradeoffs.
5. Lower the margin to **5%**. Capacity falls and shortfalls rise. Return to **20%** and read the warning about the unmet validation target.
6. Explain the downloads and saved artifacts. The dashboard never trains models and does not claim packet-loss or latency measurements.

## Likely questions

**Why does a simple baseline sometimes win a metric?** Traffic has temporal structure and noise. A moving average can smooth noise effectively. A larger model does not guarantee lower error.

**Why one institution?** This is a controlled academic prototype. The institution was selected using data coverage before model fitting. Generalization needs further experiments across institutions.

**Does the project predict latency or packet loss?** No. Neither is a prediction input or measured outcome here. The output is recorded traffic demand and a simulated capacity deficit.

**Why 10 minutes instead of 15?** CESNET samples at nominal 10-minute intervals, so a 10-minute first horizon matches the actual dataset.

**Why exclude the outage dates conservatively?** The incident timing and affected scope remain uncertain. The documented policy adds a calendar-day buffer and retains all raw measurements for inspection.

**Why does the 1% requirement fail?** The candidate margins do not cover enough demand spikes. The code reports this explicitly instead of choosing a margin on the test set or claiming a guarantee.

**Can another machine reproduce the exact numbers?** Source hashes, seeds, settings and checkpoints support verification. Different hardware or library builds can change training or timings. One-seed results do not include uncertainty estimates.
