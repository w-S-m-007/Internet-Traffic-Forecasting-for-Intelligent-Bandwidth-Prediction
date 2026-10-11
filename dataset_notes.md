# CESNET Dataset Starting Checklist

The project is restarting with **CESNET-TimeSeries24 as the dataset candidate**. Its institution and timestamp archives are downloaded and checksum verified. One institution sample has been inspected. GÉANT-specific code has been removed from the active project; previous data, results, and notes are archived separately.

## Sources to review

- Dataset and download files: https://zenodo.org/records/13382427
- Dataset methods: https://arxiv.org/html/2409.18874v1
- Published article: https://doi.org/10.1038/s41597-025-04603-x

## First milestone

Verify the dataset documentation and inspect one institution-level CSV alongside its timestamp mapping. Do this before writing a parser or deciding preprocessing rules.

The documentation review and initial local sample inspection are complete. Findings and source links are in `research_notes.txt`, including a documented probe outage and the authors' example filling policy. No cleaning policy has been selected.

## Local inspection files

- Original archives: `data/raw/cesnet/institutions.tar.gz` and `data/raw/cesnet/times.tar.gz`.
- Institution sample: `data/raw/cesnet/sample/institution_0.csv`.
- Timestamp mapping: `data/raw/cesnet/sample/times_10_minutes.csv`.

The sample has 40,298 rows and 19 columns. No duplicate `id_time` values were found, and all IDs matched the timestamp mapping. Actual column names are recorded in the research notes; some differ from documentation labels. Institution 0 was chosen only as the first archive sample, not as the final training series.

## Raw sample audit

Run `python audit_sample.py` to regenerate `data/inspection/institution_0_audit.txt`. All 18 measurement columns have no blank, nonnumeric, nonfinite, negative, or zero values in this sample. This does not prove complete traffic capture.

There are **five timestamp transitions that are not exactly 600 seconds apart**, despite complete time IDs. The mapping carries +01:00 and +02:00 offsets; elapsed time was checked in UTC. Exact discontinuities and unresolved questions are recorded in `research_notes.txt`. No data has been cleaned or resampled. We must resolve timestamp handling before generating forecast windows.

## Separate inspection copy with block labels

Run `python mark_segments.py` to regenerate `data/inspection/institution_0_segments.csv`. It retains all 40,298 rows and original cell values, with five added inspection columns:

- `timestamp_supplied`: exact timestamp text from the mapping.
- `timestamp_utc`: the same instant expressed in UTC.
- `gap_seconds`: elapsed time since the preceding row; blank for the first row.
- `segment_id`: a new block starts whenever that gap differs from 600 seconds.
- `boundary_before`: 1 when a timestamp break precedes this row, otherwise 0.

The six blocks contain 2,880, 767, 10,967, 25,449, 38, and 197 rows. All original cells and both raw file hashes were checked after generation. These labels do not explain or repair the breaks. Forecast-window checks and treatment of the documented probe outage remain pending.

## Questions to settle first

1. What does one institution series measure? How are incoming and outgoing traffic counted?
2. What are the exact columns, units, and aggregation interval?
3. How does `id_time` map to a timestamp? What timezone and interval boundaries are used?
4. What do absent rows, zero values, and explicit missing values mean?
5. What filtering, aggregation, or imputation have the dataset authors already performed?
6. Are there known collection outages or documented anomalies?
7. Which series will we use, and what coverage and gaps does it have?

## Decisions still pending

The target definition, feature set, forecast horizons, lookback window, anomaly handling, and split dates will be chosen after the above checks. Values from the GÉANT setup are not carried forward as defaults.

Anomalies may be real traffic events or measurement problems. We will not remove them solely because they look unusual, and we cannot guarantee an anomaly-free dataset.
