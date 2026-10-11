# Internet Traffic Forecasting and Bandwidth Prediction

An academic project investigating traffic forecasting with LSTM, GRU, and a small Transformer, followed by an offline bandwidth-allocation simulation. The planned applications include ISP, cloud, and data-center networks; experiments on one dataset will not establish performance in all three settings.

## Current progress

The project is at the **dataset inspection stage**. CESNET-TimeSeries24 is the current dataset candidate. Its institution and timestamp archives have been downloaded and checksum verified locally, and one institution sample has been audited.

Implemented:

- Inspect timestamps and numeric values without changing the source data.
- Join traffic observations to the supplied timestamp mapping by `id_time`.
- Label continuous 10-minute blocks in a separate inspection copy.
- Record findings, evidence, and unresolved questions in the research notes.

Model training, preprocessing decisions, forecasting evaluation, bandwidth-allocation simulation, and the dashboard are pending. Numerical claims in earlier research drafts are not results from this implementation.

## Files

| File | Purpose |
| --- | --- |
| `audit_sample.py` | Check the institution sample's values and timestamp intervals. |
| `mark_segments.py` | Preserve original cells and add timestamp and continuous-block labels. |
| `dataset_notes.md` | Dataset checklist, current inspection status, and pending decisions. |
| `research_notes.txt` | Detailed evidence and findings for the eventual research paper. |

Downloaded data, generated inspection outputs, the previous GÉANT archive, and local proposal/paper files are excluded from Git. The original proposal and drafts remain available locally in `CN Project 1.pdf` and `paper/`.

## Requirements

The two inspection scripts use only the Python standard library. They have been run with **Python 3.12.10**. No package installation or GPU is needed for this stage.

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

Institution 0 is an inspection sample, not a finalized training-series choice. The data is downloaded separately rather than distributed in this repository.

## Run the inspection

From the repository root:

```powershell
python audit_sample.py
python mark_segments.py
```

These commands regenerate:

- `data/inspection/institution_0_audit.txt`
- `data/inspection/institution_0_segments.csv`

The sample contains 40,298 rows. Five timestamp transitions differ from 600 seconds, resulting in six continuous blocks. The labeling script preserves the original measurement cells and does not fill gaps, resample timestamps, remove outliers, or convert byte counts into Mbps.

Regular timestamps and populated cells do not establish complete traffic capture. Effects of the documented monitoring outage and measurement durations near timestamp breaks remain unresolved.

## Next milestone

Investigate the known collection outage and settle the traffic measurement definition before choosing preprocessing rules or generating forecasting windows. Subsequent work will add baselines, neural models, chronological evaluation, and allocation simulation in incremental steps.

## Dataset references

- [Dataset download and provenance](https://zenodo.org/records/13382427)
- [Dataset methodology](https://arxiv.org/html/2409.18874v1)
- [Published dataset article](https://doi.org/10.1038/s41597-025-04603-x)
