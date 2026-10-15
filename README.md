# Internet Traffic Forecasting and Bandwidth Prediction

An academic project investigating traffic forecasting with LSTM, GRU, and a small Transformer, followed by an offline bandwidth-allocation simulation. The planned applications include ISP, cloud, and data-center networks; experiments on one dataset will not establish performance in all three settings.

## Current progress

**Days 2–4 are complete.** CESNET-TimeSeries24 institution 0 is the primary experimental series, selected after comparing all 283 institutions. All five predictors have 10-minute results, an initial allocation experiment is saved, and the local dashboard reads those artifacts without retraining.

Implemented:

- Inspect timestamps and numeric values without changing the source data.
- Join traffic observations to the supplied timestamp mapping by `id_time`.
- Label continuous 10-minute blocks in a separate inspection copy.
- Compare recorded traffic around the authors' reported monitoring outage.
- Mark the chosen outage exclusion dates in a separate review copy.
- Build unscaled traffic-rate and calendar features with observation and eligibility flags.
- Generate chronological splits, direct forecasting windows, training-only scalers, and a traffic/quality plot.
- Check full window paths, timestamp alignment, causal features, and scaler leakage.
- Evaluate persistence, moving-average, LSTM, GRU and Transformer forecasts at 10 minutes.
- Compare reactive and forecast-based allocation at identical safety margins.
- Browse saved forecasts, model comparisons and allocation with a local Streamlit dashboard.
- Record findings, evidence, and unresolved questions in the research notes.

All five predictors have completed the 10-minute experiment. The 30/60-minute comparisons and expanded allocation review remain pending. Numerical claims in earlier research drafts are not results from this implementation.

## Files

| File | Purpose |
| --- | --- |
| `data_processing/audit_sample.py` | Check the institution sample's values and timestamp intervals. |
| `data_processing/mark_segments.py` | Preserve original cells and add timestamp and continuous-block labels. |
| `data_processing/inspect_outage.py` | Compare raw recorded traffic before, during, and after the reported outage dates. |
| `data_processing/mark_exclusions.py` | Mark May 20–June 5, 2024, inclusive, for outage exclusion while retaining every row. |
| `data_processing/compare_institutions.py` | Compare institution candidates by byte-value quality, coverage, and prospective window availability. |
| `data_processing/build_features.py` | Add nominal traffic rate, causal input filling, calendar features, and boundary guards. |
| `data_processing/prepare_dataset.py` | Regenerate features, splits, windows, scalers, configuration, checks, and the plot from raw inputs. |
| `tests/test_preparation.py` | Check that exclusions and future/holdout values cannot leak into windows or training statistics. |
| `requirements.txt` | NumPy and Matplotlib versions used by the preparation command. |
| `data_processing/download_data.py` | Download checksum-verified archives and extract the documented sample. |
| `experiments/evaluate_baselines.py` | Evaluate persistence and four-observation moving averages. |
| `experiments/forecast_metrics.py` | Shared original-unit MAE, RMSE, positive-target MAPE, and R². |
| `models/lstm_model.py` | Compact two-layer LSTM with a scalar forecast head. |
| `experiments/train_lstm.py` | Validation early stopping, saved checkpoints, forecasts, and baseline comparison. |
| `experiments/train_neural.py` | Common data loading, training, checkpoint selection and evaluation for all three neural models. |
| `models/gru_model.py`, `models/transformer_model.py` | GRU and small Transformer definitions. |
| `experiments/train_gru.py`, `experiments/train_transformer.py` | GRU and Transformer training commands. |
| `tests/test_baselines.py`, `tests/test_lstm.py` | Metric, model-state, checkpoint, and gradient checks. |
| `experiments/evaluate_allocation.py` | Replay saved 10-minute forecasts at equal margins and choose defaults on validation. |
| `tests/test_allocation.py` | Hand-check capacity arithmetic, validation selection, and forecast alignment. |
| `requirements-training.txt` | Training dependencies, including the PyTorch version. |
| `requirements-cuda.txt` | Exact CUDA-enabled PyTorch build used by the first experiment. |
| `requirements-dashboard.txt` | Streamlit, pandas and Plotly for the saved-results interface. |
| `dashboard/app.py` | Local dashboard, model/split controls, replay, comparisons and allocation. |
| `dashboard/artifacts.py`, `dashboard/charts.py` | Validate saved results and plot real UTC timestamps with excluded gaps preserved. |
| `dashboard/styles.css`, `.streamlit/config.toml` | Local dashboard appearance and loopback-only server settings. |
| `tests/test_dashboard.py` | Artifact integrity and Streamlit interaction checks using independent fixtures. |
| `dependency_audit.txt` | Package, source-module, and generated-file dependencies checked locally. |
| `dataset_notes.md` | Dataset checklist, current inspection status, and pending decisions. |
| `research_notes.txt` | Detailed evidence and findings for the eventual research paper. |

Downloaded data, generated inspection outputs, the previous GÉANT archive, and local proposal/paper files are excluded from Git. Proposal and draft documents are optional reference material and are not required to execute this checkout.

## Requirements

Python **3.12.10**, NumPy 2.3.0, and Matplotlib 3.10.0 were used. Inspection scripts use the standard library. Preparation and baselines do not require a GPU. LSTM training used PyTorch `2.14.1+cu130` and the RTX 4050 Laptop GPU.

The current project environment is `VirtEnv`. In Git Bash, activate it before the documented `python` commands:

```bash
source VirtEnv/Scripts/activate
python -m pip install -r requirements.txt
```

For a new checkout, create the environment first with `python -m venv VirtEnv`. To install the tested Windows GPU dependencies, run:

```bash
python -m pip install -r requirements-cuda.txt
python -m pip check
python -c "import numpy, torch; print(torch.__version__); print(torch.cuda.is_available())"
```

For the general training installation, use `python -m pip install -r requirements-training.txt` and run training with `--device cpu`. Choose one training installation. The current `VirtEnv` already contains the tested GPU dependencies. `VirtEnv` is excluded from Git.

Preparation/baselines use NumPy and Matplotlib; neural training adds PyTorch. The dashboard adds Streamlit 1.66.0, pandas 3.0.6 and Plotly 7.1.0 through `requirements-dashboard.txt`. Supporting packages install automatically. TensorFlow, torchvision, torchaudio and scikit-learn are not required. Viewing saved results does not require PyTorch or a GPU.

## Prepare the local dataset

Obtain `institutions.tar.gz` and `times.tar.gz` from the [CESNET-TimeSeries24 dataset record, version v1](https://zenodo.org/records/13382427). Keep the original archives in `data/raw/cesnet/`.

For a fresh checkout, the standard-library download helper obtains and verifies both archives and extracts the two sample CSVs:

```bash
python -m data_processing.download_data
```

The helper restarts incomplete `.part` downloads from the beginning. Existing complete archives are checked and reused. If the two sample CSVs are already available, preparation and training can run without downloading the full archives. Repeating the institution-wide comparison requires the complete `institutions.tar.gz` archive; a `.part` file cannot serve as that input.

Published MD5 checksums, also matched against the local downloads:

| Archive | MD5 |
| --- | --- |
| `institutions.tar.gz` | `ab3e15fb8dc9b7120ddb2318795b6812` |
| `times.tar.gz` | `a03813763e07646ca38f17ffd53e549e` |

Extract these two members and place them at the following paths. Rename the institution file from `0.csv` to `institution_0.csv`; preserve its contents.

| Archive member | Local path |
| --- | --- |
| `institutions/agg_10_minutes/0.csv` | `data/raw/cesnet/sample/institution_0.csv` |
| `times/times_10_minutes.csv` | `data/raw/cesnet/sample/times_10_minutes.csv` |

Institution 0 is the selected primary experimental series. Its selection followed the archive-wide data comparison, before any model training. The data is downloaded separately rather than distributed in this repository.

## Run the inspection

From the repository root:

```bash
python -m data_processing.audit_sample
python -m data_processing.mark_segments
python -m data_processing.inspect_outage
python -m data_processing.mark_exclusions
```

These commands regenerate:

- `data/inspection/institution_0_audit.txt`
- `data/inspection/institution_0_segments.csv`
- `data/inspection/institution_0_outage_check.txt`
- `data/inspection/institution_0_review.csv`

The sample contains 40,298 rows. Five timestamp transitions differ from 600 seconds, resulting in six continuous blocks. The labeling script preserves the original measurement cells and does not fill gaps, resample timestamps, remove outliers, or convert byte counts into Mbps.

Regular timestamps and populated cells do not establish complete traffic capture. Effects of the documented monitoring outage and measurement durations near timestamp breaks remain unresolved.

## Compare institution candidates

```bash
python -m data_processing.compare_institutions
```

This reads the institution archive without extracting all its files and saves `data/inspection/institution_comparison.csv` and `.txt`. Coverage is the fraction of supplied time IDs present, not proof of complete capture. The comparison inspects `n_bytes` and timestamps, preserves observed zeros, and does not fill absent rows.

The prospective window counts use a three-hour history and 60-minute lead. They exclude the chosen outage dates and conservatively guard both endpoints of each continuous timestamp block. These counts have no chronological split assignment yet. They are used for dataset selection, not model performance selection.

## Chosen outage policy

Exclude future forecasting windows that touch May 20–June 5, 2024, inclusive, using calendar dates in the supplied timestamp mapping. This adds one full calendar day on each side of the reported May 21–June 4 outage because its times are approximate and the cited incident passage does not specify a timezone.

The review CSV marks 2,448 rows across 17 days with `excluded_for_outage=1` and an `exclusion_reason`. All 40,298 rows remain present, and their original values and timestamp labels are preserved. The 37,850 unmarked rows are outside this policy's dates; this is not a guarantee of their measurement quality.

Window construction checks that the complete span from the earliest input observation to the forecast target stays within one timestamp segment and contains no excluded rows. Observations are not stitched across exclusions. The saved windows will be shared by all models and baselines; marked targets are excluded from training, validation, testing, and future allocation evaluation.

## Build the unscaled feature table

After generating the review CSV:

```bash
python -m data_processing.build_features
```

This saves `data/prepared/institution_0_features.csv`, preserving all original review cells. The nominal traffic rate is `n_bytes * 8 / (600 * 1_000_000)`. It includes both directions and is not physical-link utilization. Calendar features encode hour and weekday with sine and cosine using the supplied clock and UTC offset.

Both ends of each of the six timestamp blocks are guarded because their measurement durations are uncertain. Together with the outage dates, this leaves 37,838 eligible observations. Raw counts and nominal rates remain present for inspection; eligibility flags determine their future use.

If a byte observation is missing, the input value can carry forward a previously observed rate within the allowed block. Targets are never filled. Exclusions reset that history. Institution 0 currently has no missing byte cells, so no input values were imputed.

This table remains unscaled. Rolling statistics and scaling are applied by the complete preparation workflow below.

## Complete Day 2 workflow

With the raw files in place, run:

```bash
python -m data_processing.prepare_dataset
python -m unittest -v tests.test_preparation
```

The preparation command regenerates block labels, exclusions, and base features, then saves all remaining artifacts in `data/prepared/`:

- `timeline_splits.csv` and `preparation_config.json`: fixed chronological cut points and definitions.
- `windows_10min`, `windows_30min`, and `windows_60min`: timestamp/index CSVs and model-ready NPZ arrays.
- `scalers_10min.json`, `scalers_30min.json`, and `scalers_60min.json`: training-only means and standard deviations.
- `window_counts.csv`, `preparation_checks.txt`, and `traffic_quality.png`: counts, checks, and the plot.

Each input has 18 observations covering three nominal hours. The eight features are historical traffic rate, hour and weekday sine/cosine, a missing-input flag, and trailing mean/standard deviation over up to six observations inside the input window. The first five positions use shorter histories; standard deviation uses `ddof=0`. Nothing outside the chosen input history contributes to rolling features.

Separate direct targets are one, three, and six intervals ahead: 10, 30, and 60 minutes. For this offline replay, an input interval is assumed available at its supplied start plus 600 seconds. The forecast origin is that nominal completion time, and the lead is measured to the target interval's nominal completion. Exact live collector delays have not been validated.

The complete ordered timeline is split by observation count at 70% and 85%, before exclusions. A window belongs to the split containing its target completion timestamp. Validation/test histories may use earlier observed data from preceding splits. Scalers use training windows only and are fitted separately per horizon; constant features use a scale of one. NPZ `split` codes are 0=train, 1=validation, 2=test. `X` and `y` are scaled float32 arrays; `target_mbps` and `input_mbps` preserve nominal rates for evaluation and baselines.

| Horizon | Training windows | Validation windows | Test windows |
| --- | ---: | ---: | ---: |
| 10 minutes | 28,129 | 4,029 | 5,554 |
| 30 minutes | 28,121 | 4,029 | 5,548 |
| 60 minutes | 28,109 | 4,029 | 5,539 |

The usable counts are not exactly 70/15/15 because exclusions and required histories are applied after fixing the cut points. The outage removes part of validation and the beginning of test; exact timestamps are saved in the CSVs. Both the automated path checks and the three behavioral tests passed locally. Raw input hashes remained unchanged.

## Day 3: baselines and the first LSTM

With the training dependencies installed, the environment active, and raw samples prepared:

```bash
python -m data_processing.prepare_dataset
python -m unittest -v tests.test_preparation tests.test_baselines tests.test_lstm
python -m experiments.evaluate_baselines --horizon 10
python -m experiments.train_lstm --horizon 10 --device cuda
```

Use `--device cpu` for CPU execution, or `--device auto` to let PyTorch select an available device. Preparation regenerates inputs from the raw samples; all three predictors share the same windows and exclusions. The baseline definitions are fixed: latest observation, and mean of the latest four observations (40 nominal minutes).

The LSTM has two unidirectional layers of 64 hidden units and a linear forecast head: 52,289 parameters. Each window starts with a fresh hidden state. Settings: seed 42, dropout zero, Adam at learning rate 0.001, batch size 64, scaled-target MSE, at most 30 epochs, and early-stopping patience five. Training windows shuffle with a seeded generator. The best validation MSE selects the checkpoint; test evaluation follows checkpoint restoration.

The first GPU run stopped at epoch 20 and selected epoch 15. Training took 90.35 seconds, including validation and checkpoint saves. No settings were changed in response to test scores.

| Predictor | Test MAE (nominal Mbps) | Test RMSE (nominal Mbps) | Test MAPE (%) | Test R² |
| --- | ---: | ---: | ---: | ---: |
| Persistence | 24.287 | 38.629 | 22.933 | 0.570 |
| Moving average (4 observations) | 21.025 | 32.478 | 20.608 | 0.696 |
| LSTM | 21.148 | 31.175 | 21.191 | 0.720 |

The LSTM improves MAE and RMSE over persistence. Compared with the moving average, it has lower RMSE but slightly higher MAE and MAPE. This single-seed result does not establish that LSTM is consistently superior.

Each predictor has 4,029 validation and 5,554 test predictions. MAPE uses positive targets and reports exclusions; there were none. Undefined MAPE or R² is saved as a blank cell. Predictions are not clipped for accuracy evaluation. CPU inference timing uses 25 warm-up and 1,000 timed single-window calls on preloaded data, including call/loop overhead and excluding loading and preprocessing; LSTM also includes inverse output scaling and uses one CPU thread. Timing varies with machine and system load.

Generated baseline artifacts are in `results/baselines/10min/`. LSTM artifacts are in `results/lstm/10min/`: `best_model.pt`, `training_history.csv`, timestamped `predictions.csv`, `metrics.csv`, scaler/run/preparation JSON files, `comparison.csv`, `test_prefix.png`, and `learning_curve.png`. Result folders remain excluded from Git. The plot uses the first 144 chronological test forecasts; scores cover the full eligible splits.

All ten unit checks passed. The saved checkpoint reproduced all validation and test predictions, saved metrics agreed with recomputation, and source/preparation hashes were verified. Only one fixed seed was used; identical results across platforms or PyTorch versions are not guaranteed.

## Next milestone

Day 4's models and dashboard are complete. Next is Day 5: run all five predictors at 30 and 60 minutes. The full Day 6 allocation review remains ahead.

## Day 3: initial allocation replay

With the saved 10-minute baseline and LSTM forecasts available:

```bash
python -m unittest -v tests.test_preparation tests.test_baselines tests.test_lstm tests.test_allocation
python -m experiments.evaluate_allocation
```

This command reads saved artifacts without retraining. It checks prepared-file hashes, forecast target IDs, split assignments, timestamps, and actual targets before replay. Reactive capacity uses the last available input demand; proactive capacity uses either the four-observation moving average or LSTM forecast. All use `max(0, forecast) * (1 + margin)` at margins of 5%, 10%, 15%, and 20%.

Each policy's default margin is selected using validation data only: the lowest mean capacity meeting at most 1% shortfall intervals. **None qualifies in this experiment**, so every policy uses the specified 20% fallback. Validation shortfall at that margin is 19.68% reactive, 16.31% moving average, and 13.45% LSTM. The target remains unmet; the fallback is not a claim of adequate service.

| Policy at 20% margin | Test shortfall intervals (%) | Mean capacity (Mbps) | Deficit volume (MB) | Mean excess capacity (Mbps) | Served demand / capacity |
| --- | ---: | ---: | ---: | ---: | ---: |
| Reactive | 23.44 | 140.21 | 2,127,196 | 28.48 | 0.797 |
| Moving average | 18.85 | 140.19 | 1,685,299 | 27.39 | 0.805 |
| LSTM | 10.86 | 148.67 | 1,102,083 | 34.47 | 0.768 |

The LSTM policy reduces shortfalls but allocates more average capacity and has more unused capacity than the reactive policy. This tradeoff should be reported alongside forecasting accuracy.

Deficit volume sums `max(actual-capacity, 0) * 600 / 8` in decimal MB, using CESNET's 10-minute intervals. Excess capacity is `max(capacity-actual, 0)`; served demand is `min(actual, capacity)`. The reported ratio divides total served demand by total allocated capacity, and is undefined if capacity sums to zero. Evaluation covers 4,029 eligible validation and 5,554 eligible test intervals; excluded gaps are not integrated.

Outputs in `results/allocation/10min/` are `metrics.csv` (24 policy/split/margin rows), `replay.csv` (114,996 timestamped rows), `default_test_metrics.csv`, and `run_config.json` with validation selection evidence and source hashes. These are generated locally and excluded from Git. Six new behavioral checks passed, including flat traffic, a sudden spike, zero capacity, and inconsistent forecast records.

This is an abstract offline capacity pool based on nominal recorded traffic. A deficit represents simulated unserved demand, not measured packet loss. Physical routing, link constraints, latency, controller delays, and live deployment are outside this experiment.

## Dataset references

- [Dataset download and provenance](https://zenodo.org/records/13382427)
- [Dataset methodology](https://arxiv.org/html/2409.18874v1)
- [Published dataset article](https://doi.org/10.1038/s41597-025-04603-x)

## Source directories and Day 4 commands

Run commands from the repository root with `VirtEnv` active. Python files are grouped by role:

| Directory | Contents |
| --- | --- |
| `data_processing/` | Acquisition, inspection, exclusions, features and window preparation. |
| `models/` | LSTM, GRU and Transformer neural-network definitions. |
| `experiments/` | Forecast metrics, baseline evaluation, training and allocation replay. |
| `tests/` | Preparation, forecast, model and allocation checks. |
| `dashboard/` | Saved-result loaders, interactive charts, app and styles. |

```bash
python -m unittest discover -s tests -v
python -m experiments.train_gru --horizon 10 --device cuda
python -m experiments.train_transformer --horizon 10 --device cuda
```

The GRU uses the LSTM procedure: two layers, 64 hidden units, dropout zero, seed 42, Adam at 0.001, batch size 64, at most 30 epochs and validation early stopping with patience five. Its parameter count is 39,233. The shared trainer in `experiments/train_neural.py` saves GRU artifacts in `results/gru/10min/`, with comparisons to matching saved baselines and LSTM. Each training command trains only its named model. Source directory changes preserve the root-level `data/` and `results/` locations. No new dependencies are needed.

The Transformer has two independently initialized encoder layers, model dimension 64, four attention heads, feed-forward width 128, GELU activation, post-norm LayerNorm, and dropout zero. A linear projection maps the eight input features to dimension 64; fixed sinusoidal positional encoding represents historical order. The output head reads the final historical position. Total parameters: 67,585. All 18 positions contain available history, so attention can use the full input window without a target token. The experiment uses mathematical scaled dot-product attention and disables the MHA evaluation fastpath. Training and evaluation settings otherwise match the other neural models. These architecture choices were recorded before training.

Implementation references: [PyTorch encoder-layer API](https://docs.pytorch.org/docs/2.14/generated/torch.nn.TransformerEncoderLayer.html) and [attention-backend API](https://docs.pytorch.org/docs/2.14/generated/torch.nn.attention.sdpa_kernel.html).

Transformer artifacts are saved in `results/transformer/10min/`; its comparison CSV and plot include matching saved persistence, moving-average, LSTM and GRU results when available. The CPU inference protocol is unchanged; timings are machine-dependent and include each model's chosen attention implementation.

## Day 4: first GRU result

The 10-minute GRU completed 18 epochs and selected epoch 13 using validation. Training took 72.26 seconds. Test MAE is 20.910 Mbps, RMSE 31.006 Mbps, MAPE 20.921% and R² 0.723. Evidence is in `results/gru/10min/metrics.csv`, `comparison.csv`, `predictions.csv`, `best_model.pt` and `run_config.json`.

All 19 tests passed after the directory reorganization. The checkpoint reproduced all 9,583 validation/test forecasts within floating-point tolerance; metrics agreed with recomputation, and existing preparation/LSTM/baseline/allocation file hashes were unchanged. A single seed is still the limitation.

## Day 4: first Transformer result and five-predictor comparison

The Transformer stopped after epoch 13 and restored epoch 8, selected by lowest validation MSE. Training took 145.14 seconds; test CPU inference measured 2.068 milliseconds per forecast under the shared timing protocol.

All predictors use the same 5,554 test targets:

| Predictor | Test MAE (Mbps) | Test RMSE (Mbps) | Test MAPE (%) | Test R² |
| --- | ---: | ---: | ---: | ---: |
| Persistence | 24.287 | 38.629 | 22.933 | 0.570 |
| Moving average | 21.025 | 32.478 | 20.608 | 0.696 |
| LSTM | 21.148 | 31.175 | 21.191 | 0.720 |
| GRU | 20.910 | 31.006 | 20.921 | 0.723 |
| Transformer | 20.746 | 30.803 | 21.864 | 0.726 |

The Transformer has the lowest test MAE and RMSE in this run, while its MAPE is higher than the moving average, LSTM and GRU. Moving average retains the lowest MAPE. Validation RMSE is 34.842 Mbps for Transformer, 34.606 for LSTM and 34.557 for GRU, so test rankings should not be used retrospectively to select checkpoints or change settings. One seed and one institution do not establish consistent superiority.

Evidence: `results/transformer/10min/comparison.csv` contains all ten model/split metric rows; the same folder holds the model's metrics, forecasts, checkpoint, configuration, learning curve and first-144-test-interval comparison plot. All test targets were positive, so MAPE omitted none. No negative predictions were produced. All forecasts are evaluated without clipping.

All 24 tests passed before training. The saved checkpoint reproduced all 9,583 validation/test forecasts within `rtol=1e-5, atol=1e-4` Mbps. Recomputed metrics matched CSVs, all five predictors matched the same timestamped targets, and all 43 previous preparation/result file hashes remained unchanged. Raw sample hashes also matched the preparation manifest. Both new figures were visually checked.

The 30/60-minute comparisons and the expanded allocation review follow later; allocation currently still uses reactive, moving-average and LSTM policies.

## Day 4: run the local dashboard

From the repository root in Git Bash:

```bash
source VirtEnv/Scripts/activate
python -m pip install -r requirements-dashboard.txt
python -m streamlit run dashboard/app.py
```

Open **http://127.0.0.1:8501**. Stop the server with `Ctrl+C` in its terminal. The app binds to the local machine and uses saved files; it does not train models, load checkpoints, require CUDA, or contact the dataset service. A fresh clone must first obtain/regenerate result artifacts because `results/` is Git-ignored.

Overview follows the reviewed mockup: model metrics, actual-versus-predicted traffic, a model comparison table and allocation summary. Sidebar views provide a larger forecasting or allocation area. Select validation/test, a model, an available horizon, chart history and replay position. A replay interval changes the displayed chart and interval readout; the main scores remain the full eligible split. Dates are real UTC targets. Lines break across excluded intervals rather than joining through gaps.

Only 10-minute results are currently available. Future 30/60-minute results are discovered from complete saved runs. Allocation has its own clearly labeled model control for LSTM or moving average, because GRU/Transformer allocation has not yet been evaluated. Both policies use the selected 5/10/15/20% margin. Validation-selected defaults and the unmet 1% target remain visible; sliders do not rewrite those defaults or result files. Comparison, forecasts and allocation replay can be downloaded as CSVs.

The loader verifies common prepared-data signatures, model/target identities, UTC leads, observed demand and saved forecasting metrics. Allocation checks its forecast-source hashes, all saved margin/split scores and validation defaults. Replaced result files invalidate the in-memory cache. Corrupt/incomplete runs produce an explanatory message. An empty checkout shows regeneration commands.

Dashboard-only checks:

```bash
python -m unittest -v tests.test_dashboard
```

All checks (requires training and dashboard dependencies):

```bash
python -m unittest discover -s tests -v
python -m pip check
```

All **31 tests** pass, including seven dashboard checks. These cover UI model/split/page/margin changes, independent result fixtures, corrupt metrics, misaligned targets, stale allocation sources, excluded chart gaps and the empty-results state. Local browser QA images are saved under `results/dashboard/` and excluded from Git.
