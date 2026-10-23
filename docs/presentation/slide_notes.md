## Slide 1: Internet traffic forecasting

Introduce the original project aim: forecast traffic to support proactive bandwidth planning. The implemented evidence uses one CESNET institution. ISP, cloud and data-center applications require separate validation. This deck reports actual generated results, not the numerical claims in earlier proposal drafts. Sources: README.md; results/comparison/forecast_metrics_10_30_60min.csv; dataset_notes.md.

## Slide 2: Research scope

Explain that forecasting accuracy and capacity allocation are separate evaluation questions. A forecast can reduce RMSE yet need more capacity to reduce shortfalls. All policies consume the same observations. Source: README.md; experiments/evaluate_allocation.py.

## Slide 3: CESNET-TimeSeries24 data

Data provenance: CESNET-TimeSeries24 v1, https://zenodo.org/records/13382427 and https://arxiv.org/abs/2409.18874 . Local raw members: institutions/agg_10_minutes/0.csv and times/times_10_minutes.csv. Institution selection followed a data-quality comparison of all 283 institutions before model fitting. The supplied mapping covers 2023-10-09 to 2024-07-14. Numeric rate means recorded bidirectional bytes per nominal interval. Possible endpoint double counting remains unresolved. Never describe this as measured physical-link utilization. Sources: dataset_notes.md; raw sample files; preparation_config.json.

## Slide 4: Preparation and measurement safeguards

Five timestamp transitions differ from 600 seconds. Keep six continuous blocks and guard the first and last observation of each. The authors reported a monitoring incident approximately May 21 to June 4, 2024, with institution/timezone scope uncertain. The documented project policy conservatively excludes May 20 through June 5 inclusive using supplied calendar dates, including 2,448 rows. Twelve guarded block endpoints are disjoint, leaving 37,838 eligible rows. Missing input values can forward-fill causally only inside allowed blocks; targets never fill. Institution 0 currently has no missing byte cells, so the causal fill does not impute these values. Rolling statistics use only the selected 18-observation history. Sources: data/prepared/preparation_config.json; research_notes.txt; data_processing/build_features.py and prepare_dataset.py.

## Slide 5: Forecasting protocol

The 70/15/15 chronological cut points use the original ordered timeline before exclusions. Windows belong to the split containing target completion time. Validation and test histories may use earlier observed values from preceding splits. The three-hour input contains 18 observations, with eight features per observation. Targets are separate direct predictions at 1, 3 or 6 intervals. Offline availability assumes each interval becomes available at supplied start plus 600 seconds. The horizon is measured from that forecast origin to target interval completion. Actual collection delays remain unverified. Small differences in usable targets mean cross-horizon comparisons are not fully paired. Source: data/prepared/preparation_config.json and window_counts.csv.

## Slide 6: Models and training settings

Persistence repeats the latest observed demand. The moving average uses the latest four observations, representing 40 nominal minutes. LSTM and GRU use two unidirectional layers, 64 hidden units, fresh state per window and a scalar head. Transformer uses two independently initialized encoder layers, dimension 64, four heads, feedforward dimension 128, sinusoidal positions, zero dropout and a scalar head on the last historical position. Full attention spans available history only. Shared optimizer Adam, learning rate 0.001, batch size 64, maximum 30 epochs, patience five and seed 42. The lowest validation MSE selects each checkpoint, before test evaluation. Source: models/; experiments/train_neural.py; results/*/*/run_config.json.

## Slide 7: Test forecasting error across horizons

Each bar reads the corresponding test RMSE from the generated combined metric CSV. Values use nominal Mbps, lower is better. All predictors use identical target cohorts within a horizon. Test counts: 5,554 at 10 minutes, 5,548 at 30 minutes, 5,539 at 60 minutes. Cross-horizon targets differ slightly. Transformer has lowest 10-minute test RMSE, GRU has lowest 30- and 60-minute test RMSE. One seed does not establish statistical superiority. Source: results/comparison/forecast_metrics_10_30_60min.csv.

## Slide 8: 60-minute results

Read every value directly from the test metrics. GRU gives the lowest MAE and RMSE and highest R-squared. LSTM has the lowest MAPE. Transformer improves RMSE over persistence but has slightly worse MAE and substantially worse MAPE. The result supports comparing model families and metrics instead of assuming the most complex architecture wins. MAPE uses positive targets only, with zero exclusions here. Source: results/comparison/forecast_metrics_10_30_60min.csv.

## Slide 9: Historical forecast replay

The chart shows the first 72 chronological 10-minute test predictions, a fixed 12-hour excerpt, not a segment selected for low error. The complete test split contains 5,554 targets and supplies all reported scores. Forecast origin to target completion is 10 minutes. Local saved predictions provide every plotted value and timestamp. Source: results/lstm/10min/predictions.csv.

## Slide 10: Capacity allocation policy

At the 10-minute horizon, each policy provisions one nominal 600-second target interval. Reactive uses latest observed demand, while proactive policies use their saved forecasts. Use identical margins 5%, 10%, 15%, 20%. Capacity is max(0, prediction) times (1+margin). A shortfall occurs when actual demand exceeds capacity. Convert nominal Mbps deficit to decimal MB with the 600-second duration divided by eight. This is simulated unmet demand, not observed packet loss. Source: experiments/evaluate_allocation.py; tests/test_allocation.py.

## Slide 11: Allocation at an equal 20% margin

Every row uses the same 5,554 eligible 10-minute test targets and safety margin. Compare shortfall and spare capacity together. Default margins are selected using validation only. None of the tested margins meets the at-most-1% shortfall criterion, so every policy falls back to 20%. Deficit volume uses 600-second intervals and decimal MB. Served-demand-to-capacity is aggregate served demand divided by aggregate capacity. This slide reports the results of the expanded five-policy evaluation. Source: results/allocation/10min/metrics.csv and default_test_metrics.csv.

## Slide 12: The 1% shortfall target remains unmet

The margin search is a constrained validation decision, not a test-set optimization. For each policy choose the lowest mean validation capacity among margins meeting at most 1% shortfall intervals. None of 5%, 10%, 15%, 20% qualifies, so use the documented 20% fallback and disclose the unmet target. The result does not establish a service guarantee. Greater margins or predictive quantiles are possible future experiments, requiring separate validation. Source: results/allocation/10min/metrics.csv and run_config.json.

## Slide 13: Local dashboard demonstration

Start the dashboard from the repository root with python -m streamlit run dashboard/app.py. Choose Forecasts, select a model, horizon and test split, then move the historical replay position. Show the comparison table and explain MAE versus RMSE. Open Allocation at the 10-minute horizon and compare reactive capacity with each selected proactive model using identical margins. Read the unmet validation target warning explicitly. The dashboard reads saved CSV/JSON artifacts and never retrains. Screenshot source: results/dashboard/dashboard-60min.png, an actual local dashboard capture. See docs/presentation/demo_script.md for a timed demonstration.

## Slide 14: Findings and limits

Main findings: Transformer yields the lowest 10-minute test RMSE, while GRU yields the lowest 30- and 60-minute test RMSE. The four-observation moving average remains a strong baseline. Allocation shortfalls fall as margins rise, with more unused capacity. None of the validation policies satisfies the 1% target within the chosen margin grid. Limitations: one institution, one seed, uncertain collection timing and outage scope, no routing or physical capacity constraint, and an offline simulation without packet loss or latency measurements. Cloud and data-center performance remains untested. Reproduction commands and data-source details are in README.md; run instructions in docs/presentation/README.md and demo_script.md. Sources: generated result CSVs and preparation_config.json.

## Slide 15: Conclusion

The project delivers a reproducible pipeline from audited CESNET institution 0 observations to LSTM, GRU and Transformer forecasts, baseline comparisons, offline allocation and a saved-results dashboard. Transformer has the lowest 10-minute test RMSE. GRU has the lowest 30- and 60-minute test RMSE. At the common 20% margin, LSTM test shortfall frequency is 10.857039971191934%, compared with reactive 23.44256391789701%, while mean capacity increases from 140.21410169993518 to 148.66915228140374 Mbps. None of the tested margins achieves the 1% validation target. One institution and one seed limit generalization. The conclusion supports further capacity-planning research, not a live-service guarantee. Sources: results/comparison/forecast_metrics_10_30_60min.csv; results/allocation/10min/default_test_metrics.csv and run_config.json.
