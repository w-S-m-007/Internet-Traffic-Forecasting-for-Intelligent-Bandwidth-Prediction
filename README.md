# Internet Traffic Forecasting and Bandwidth Prediction

A reproducible academic prototype for direct traffic forecasting with LSTM, GRU and a small Transformer, compared with persistence and a four-observation moving average. Forecasts feed an offline bandwidth-capacity simulation and a local Streamlit dashboard.

The experiment uses **CESNET-TimeSeries24 v1, institution 0**. Cloud, ISP and data-center deployment are proposed applications requiring separate validation. This project does not implement a live controller or measure packet loss and latency.

## Deliverables

- Report: [editable Word](deliverables/report/project_report.docx), [PDF](deliverables/report/project_report.pdf), [Markdown source](docs/project_report.md).
- Presentation: [editable slides](deliverables/presentation/project_presentation.pptx), with [speaking and demonstration guide](docs/presentation/demo_script.md).
- Backup demo: `deliverables/demo/dashboard_demo.webm` (silent recording; local submission bundle).
- Dashboard: `dashboard/app.py`, reading saved results without retraining or importing PyTorch.
- All models, scalers, configurations, forecasts, tables and plots: `results/` and `data/prepared/`.
- Submission package: `deliverables/submission/traffic_forecasting_submission.zip`, with a SHA256 manifest.

Generated datasets, model results, recordings and the ZIP are excluded from Git. The local ZIP includes the sample, prepared inputs and saved results so it can demonstrate the project without training. A source-only Git clone must regenerate them first. See [dataset attribution](DATA_ATTRIBUTION.md).

## Quick start (Git Bash, Python 3.12)

From the project root:

```bash
python -m venv VirtEnv
source VirtEnv/Scripts/activate
python -m pip install -r requirements-training.txt -r requirements-dashboard.txt
```

For the tested NVIDIA setup, install `requirements-cuda.txt` in place of `requirements-training.txt`. Existing environments do not need recreation. The tested stack is recorded in `dependency_audit.txt`; document/presentation build tools are separate from the application dependencies.

With the saved artifacts from the submission package:

```bash
python -m streamlit run dashboard/app.py
```

Open http://127.0.0.1:8501. Select model, 10/30/60-minute horizon and validation/test split. Replay changes the displayed interval history; headline metrics always cover the complete eligible split. Allocation is available at 10 minutes with four proactive models and a reactive comparator, using the same selected margin. CSV downloads use the displayed experiment.

## Reproduce and verify

One command runs preparation, all 15 model/horizon experiments, allocation, combined plots, checkpoint verification and the test suite:

```bash
python -m scripts.reproduce --download --fresh --device auto
```

`--download` fetches/checks the original source archives only when the two sample files are absent. Downloads need internet and disk space; the sample already bundled locally avoids that step. `--fresh` preserves existing prepared data and results under `archive/experiment_<timestamp>/` before regenerating them. Raw sample files remain the inputs. Use `--device cpu` to run without CUDA or `--device cuda` to require it. Runtime varies by hardware.

To finish an interrupted workflow, omit `--fresh`; complete runs are reused and verified. A partial output directory causes an explanatory error rather than being treated as complete.

```bash
python -m scripts.reproduce --device auto
python -m scripts.verify_results --checkpoints --device auto
python -m unittest discover -s tests -v
python -m pip check
```

The verifier reconstructs training-only scalers and windows, checks source hashes, target alignment, baseline definitions, all forecasting metrics, saved checkpoints and allocation artifacts. It writes `results/comparison/final_verification.json`. Strict checkpoint replay should use the saved training backend. CUDA checkpoints can differ slightly when replayed on CPU; on a CPU-only machine, omit `--checkpoints` to verify artifact arithmetic/provenance, or regenerate the experiments with `--device cpu` before replaying them. One fixed seed is not a cross-platform bitwise reproducibility guarantee.

After final documents and the recording exist, regenerate the local submission bundle:

```bash
python -m scripts.package_submission
```

The package contains source, documentation, the attributed sample and generated evidence. It excludes environments, credentials, Git metadata and full raw archives.

## Completed verification

All **41 tests** pass, and `pip check` reports no broken requirements. A separate clean project copy regenerated all 15 predictor/horizon runs from the existing raw sample using the installed environment. All nine checkpoint tensor sets, forecast accuracy values, 40 allocation metric rows and 191,660 replay rows matched the saved experiments exactly. Timing measurements varied and were not used for this equality check. This verifies the workflow on this workstation; it does not claim a new archive download or clean dependency installation. Evidence: `results/comparison/reproduction_acceptance.json`.

The dashboard was checked across allocation models, margins and splits and exercised in a real browser. The 14-page report and 15-slide deck were rendered and visually reviewed. The backup recording is silent; use the speaking guide for narration.

## Experimental method

- Source interval: 600 seconds. Target: `n_bytes * 8 / (600 * 1_000_000)`, nominal recorded Mbps including both directions. Physical-link utilization and unique network-wide demand are not inferred.
- Institution 0 was chosen after comparing 283 institutions by coverage and prospective window availability, before fitting models. Six regular timestamp blocks are retained separately.
- Conservative outage exclusion: May 20 through June 5, 2024 inclusive, plus each block's first and last observation. The authors' outage description has unresolved institution/timezone scope; these are explicit project policies.
- Inputs: 18 ten-minute observations (three hours), hour/weekday sine and cosine, missing-input flag, causal rolling mean and population standard deviation within each history window. No invented latency, packet-rate or active-user features.
- Chronological 70/15/15 timeline cuts precede exclusions. Windows belong to splits by target completion; their entire input-to-target paths must avoid gaps/exclusions. Only training windows fit scalers. Missing inputs can be causally filled within allowed blocks; missing targets are excluded.
- Separate direct forecasts at 10, 30 and 60 minutes predict **one ten-minute interval ending at the stated lead**, not the aggregate over that future horizon. Inputs are assumed available at nominal interval completion for offline replay.
- LSTM/GRU: two layers, 64 hidden units. Transformer: two layers, dimension 64, four attention heads, feed-forward dimension 128 and sinusoidal positions. All use seed 42, Adam 0.001, batch 64, maximum 30 epochs and early stopping patience five on validation MSE.
- MAE, RMSE, positive-target MAPE and R² use original-unit unclipped forecasts. All evaluated targets were positive. CPU inference uses one preloaded window, 25 warm-up and 1,000 timed calls, including inverse scaling for neural models; loading/preprocessing are excluded.

| Horizon | Training windows | Validation windows | Test windows |
| --- | ---: | ---: | ---: |
| 10 minutes | 28,129 | 4,029 | 5,554 |
| 30 minutes | 28,121 | 4,029 | 5,548 |
| 60 minutes | 28,109 | 4,029 | 5,539 |

## Forecasting results

Test RMSE in nominal Mbps (lower is better):

| Predictor | 10-minute RMSE | 30-minute RMSE | 60-minute RMSE |
| --- | ---: | ---: | ---: |
| Persistence | 38.629 | 41.081 | 43.754 |
| Moving average | 32.478 | 35.060 | 38.668 |
| LSTM | 31.175 | 33.611 | 35.091 |
| GRU | 31.006 | 32.290 | 34.785 |
| Transformer | 30.803 | 32.340 | 38.537 |

Transformer has the lowest test MAE/RMSE at 10 minutes; GRU has the lowest at 30 and 60 minutes. Moving average has the lowest 10-minute MAPE, while LSTM has the lowest 60-minute MAPE. Model ranking depends on metric and horizon. These are single-seed observations, and target cohorts differ slightly across horizons.

Exact MAE/RMSE/MAPE/R² and timing values: `results/comparison/forecast_metrics_10_30_60min.csv`. Each model's own folder contains timestamped predictions and metric CSVs, configuration, and for neural models checkpoints, scalers and learning curves. See `results/comparison/forecast_test_10_30_60min.png` for the combined figure.

## Allocation results

Capacity is `max(0, forecast) * (1 + margin)`. Reactive capacity uses the latest observed demand. Each policy is compared at identical 5%, 10%, 15% and 20% margins. Its default is selected from validation by minimum mean capacity subject to at most 1% shortfall intervals; if none qualifies, the 20% fallback is used.

**All five policies fail the 1% validation target and use the 20% fallback.** At that margin, on the 5,554 eligible test intervals:

| Policy | Test shortfall intervals (%) | Mean capacity (Mbps) | Deficit volume (MB) |
| --- | ---: | ---: | ---: |
| Reactive | 23.443 | 140.214 | 2,127,196 |
| Moving average | 18.851 | 140.191 | 1,685,299 |
| LSTM | 10.857 | 148.669 | 1,102,083 |
| GRU | 11.091 | 147.985 | 1,143,210 |
| Transformer | 10.965 | 146.690 | 1,146,184 |

LSTM has the fewest shortfall intervals but allocates more capacity than the other policies. Reducing shortfalls is a capacity tradeoff, not proof of improved overall utilization. Deficit MB is summed shortfall Mbps times 600/8; it represents simulated unserved demand rather than observed packet loss. Excluded gaps are not integrated. No 30/60-minute allocation experiment is claimed.

All 40 policy/split/margin metric rows, validation-selected defaults and the full replay are in `results/allocation/10min/`. The three original policies retained exactly the same metrics after adding GRU and Transformer.

## Project layout

| Directory/file | Purpose |
| --- | --- |
| `data_processing/` | Acquisition, inspection, exclusions, features, windows and scalers |
| `models/` | LSTM, GRU and Transformer definitions |
| `experiments/` | Training, baselines, metrics and allocation |
| `dashboard/` | Validated saved-artifact interface and charts |
| `scripts/` | Reproduction, verification, summary plots, recording and packaging |
| `tests/` | Behavioral preprocessing, model, metric, allocation and dashboard checks |
| `docs/` | Report source, presentation generator and demonstration guidance |
| `deliverables/` | Finished documents, slides, recording and local ZIP |
| `dataset_notes.md` | Source inspection and data decisions |
| `research_notes.txt` | Dated research findings and experiment evidence |
| `dependency_audit.txt` | Tested dependencies and environment history |

## Limitations and extensions

Only one institution and one seed are evaluated. Chronological validation is one split, without repeated seeds, rolling-origin evaluation, uncertainty bounds or measured live collection delays. Institution aggregation may double-count endpoints. The conservative outage and boundary policies affect the evaluated cohort. Cloud/data-center transfer, routing constraints, live control, packet loss and latency, NS-3/Mininet and stronger allocation calibration require separate experiments.

The completed prototype supports reproducible research and historical replay. It does not establish production readiness or a service-level guarantee. Earlier research-draft numbers are not evidence from this implementation.
