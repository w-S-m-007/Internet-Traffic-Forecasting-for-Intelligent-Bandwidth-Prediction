# Internet Traffic Forecasting and Bandwidth Prediction

An academic project investigating traffic forecasting with LSTM, GRU, and a small Transformer, followed by an offline bandwidth-allocation simulation. The planned applications include ISP, cloud, and data-center networks; experiments on one dataset will not establish performance in all three settings.

## Current progress

**Day 2 data preparation is complete.** CESNET-TimeSeries24 institution 0 is the primary experimental series, selected after comparing all 283 institutions. Its archives have been downloaded and checksum verified locally. No forecasting models have been trained.

Implemented:

- Inspect timestamps and numeric values without changing the source data.
- Join traffic observations to the supplied timestamp mapping by `id_time`.
- Label continuous 10-minute blocks in a separate inspection copy.
- Compare recorded traffic around the authors' reported monitoring outage.
- Mark the chosen outage exclusion dates in a separate review copy.
- Build unscaled traffic-rate and calendar features with observation and eligibility flags.
- Generate chronological splits, direct forecasting windows, training-only scalers, and a traffic/quality plot.
- Check full window paths, timestamp alignment, causal features, and scaler leakage.
- Record findings, evidence, and unresolved questions in the research notes.

Model training, forecasting evaluation, bandwidth-allocation simulation, and the dashboard are pending. Numerical claims in earlier research drafts are not results from this implementation.

## Files

| File | Purpose |
| --- | --- |
| `audit_sample.py` | Check the institution sample's values and timestamp intervals. |
| `mark_segments.py` | Preserve original cells and add timestamp and continuous-block labels. |
| `inspect_outage.py` | Compare raw recorded traffic before, during, and after the reported outage dates. |
| `mark_exclusions.py` | Mark May 20–June 5, 2024, inclusive, for outage exclusion while retaining every row. |
| `compare_institutions.py` | Compare institution candidates by byte-value quality, coverage, and prospective window availability. |
| `build_features.py` | Add nominal traffic rate, causal input filling, calendar features, and boundary guards. |
| `prepare_dataset.py` | Regenerate features, splits, windows, scalers, configuration, checks, and the plot from raw inputs. |
| `test_preparation.py` | Check that exclusions and future/holdout values cannot leak into windows or training statistics. |
| `requirements.txt` | NumPy and Matplotlib versions used by the preparation command. |
| `dataset_notes.md` | Dataset checklist, current inspection status, and pending decisions. |
| `research_notes.txt` | Detailed evidence and findings for the eventual research paper. |

Downloaded data, generated inspection outputs, the previous GÉANT archive, and local proposal/paper files are excluded from Git. The original proposal and drafts remain available locally in `CN Project 1.pdf` and `paper/`.

## Requirements

Python **3.12.10** was used. Inspection scripts use the standard library; preparation additionally uses NumPy 2.3.0 and Matplotlib 3.10.0. No GPU is needed.

```powershell
python -m pip install -r requirements.txt
```

## Prepare the local dataset

Obtain `institutions.tar.gz` and `times.tar.gz` from the [CESNET-TimeSeries24 dataset record, version v1](https://zenodo.org/records/13382427). Keep the original archives in `data/raw/cesnet/`.

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

```powershell
python audit_sample.py
python mark_segments.py
python inspect_outage.py
python mark_exclusions.py
```

These commands regenerate:

- `data/inspection/institution_0_audit.txt`
- `data/inspection/institution_0_segments.csv`
- `data/inspection/institution_0_outage_check.txt`
- `data/inspection/institution_0_review.csv`

The sample contains 40,298 rows. Five timestamp transitions differ from 600 seconds, resulting in six continuous blocks. The labeling script preserves the original measurement cells and does not fill gaps, resample timestamps, remove outliers, or convert byte counts into Mbps.

Regular timestamps and populated cells do not establish complete traffic capture. Effects of the documented monitoring outage and measurement durations near timestamp breaks remain unresolved.

## Compare institution candidates

```powershell
python compare_institutions.py
```

This reads the institution archive without extracting all its files and saves `data/inspection/institution_comparison.csv` and `.txt`. Coverage is the fraction of supplied time IDs present, not proof of complete capture. The comparison inspects `n_bytes` and timestamps, preserves observed zeros, and does not fill absent rows.

The prospective window counts use a three-hour history and 60-minute lead. They exclude the chosen outage dates and conservatively guard both endpoints of each continuous timestamp block. These counts have no chronological split assignment yet. They are used for dataset selection, not model performance selection.

## Chosen outage policy

Exclude future forecasting windows that touch May 20–June 5, 2024, inclusive, using calendar dates in the supplied timestamp mapping. This adds one full calendar day on each side of the reported May 21–June 4 outage because its times are approximate and the cited incident passage does not specify a timezone.

The review CSV marks 2,448 rows across 17 days with `excluded_for_outage=1` and an `exclusion_reason`. All 40,298 rows remain present, and their original values and timestamp labels are preserved. The 37,850 unmarked rows are outside this policy's dates; this is not a guarantee of their measurement quality.

Window construction checks that the complete span from the earliest input observation to the forecast target stays within one timestamp segment and contains no excluded rows. Observations are not stitched across exclusions. The saved windows will be shared by all models and baselines; marked targets are excluded from training, validation, testing, and future allocation evaluation.

## Build the unscaled feature table

After generating the review CSV:

```powershell
python build_features.py
```

This saves `data/prepared/institution_0_features.csv`, preserving all original review cells. The nominal traffic rate is `n_bytes * 8 / (600 * 1_000_000)`. It includes both directions and is not physical-link utilization. Calendar features encode hour and weekday with sine and cosine using the supplied clock and UTC offset.

Both ends of each of the six timestamp blocks are guarded because their measurement durations are uncertain. Together with the outage dates, this leaves 37,838 eligible observations. Raw counts and nominal rates remain present for inspection; eligibility flags determine their future use.

If a byte observation is missing, the input value can carry forward a previously observed rate within the allowed block. Targets are never filled. Exclusions reset that history. Institution 0 currently has no missing byte cells, so no input values were imputed.

This table remains unscaled. Rolling statistics and scaling are applied by the complete preparation workflow below.

## Complete Day 2 workflow

With the raw files in place, run:

```powershell
python prepare_dataset.py
python -m unittest -v test_preparation
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

## Next milestone

Day 3: implement persistence and moving-average baselines, then the first LSTM experiment. Continue using the saved split definitions, exclusions, and physical-unit interpretation.

## Dataset references

- [Dataset download and provenance](https://zenodo.org/records/13382427)
- [Dataset methodology](https://arxiv.org/html/2409.18874v1)
- [Published dataset article](https://doi.org/10.1038/s41597-025-04603-x)
