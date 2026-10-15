# CESNET Dataset Starting Checklist

The project has restarted with **CESNET-TimeSeries24**, with institution 0 selected as the primary experimental series after comparison of all 283 institutions. Its institution and timestamp archives are downloaded and checksum verified. GÉANT-specific code has been removed from the active project; previous data, results, and notes are archived separately.

## Sources to review

- Dataset and download files: https://zenodo.org/records/13382427
- Dataset methods: https://arxiv.org/html/2409.18874v1
- Published article: https://doi.org/10.1038/s41597-025-04603-x

## First milestone

Verify the dataset documentation and inspect one institution-level CSV alongside its timestamp mapping. Do this before writing a parser or deciding preprocessing rules.

The documentation review, institution comparison, and Day 2 preparation are complete. Findings and source links are in `research_notes.txt`. The selected outage/boundary policy preserves raw observations and excludes unsafe modeling paths.

## Local inspection files

- Original archives: `data/raw/cesnet/institutions.tar.gz` and `data/raw/cesnet/times.tar.gz`.
- Institution sample: `data/raw/cesnet/sample/institution_0.csv`.
- Timestamp mapping: `data/raw/cesnet/sample/times_10_minutes.csv`.

The sample has 40,298 rows and 19 columns. No duplicate `id_time` values were found, and all IDs matched the timestamp mapping. Actual column names are recorded in the research notes; some differ from documentation labels. Institution 0 was initially the first archive sample and was later selected for the experiment after the institution comparison.

## Raw sample audit

Run `python -m data_processing.audit_sample` to regenerate `data/inspection/institution_0_audit.txt`. All 18 measurement columns have no blank, nonnumeric, nonfinite, negative, or zero values in this sample. This does not prove complete traffic capture.

There are **five timestamp transitions that are not exactly 600 seconds apart**, despite complete time IDs. The mapping carries +01:00 and +02:00 offsets; elapsed time was checked in UTC. Exact discontinuities and unresolved questions are recorded in `research_notes.txt`. No data has been cleaned or resampled. We must resolve timestamp handling before generating forecast windows.

## Separate inspection copy with block labels

Run `python -m data_processing.mark_segments` to regenerate `data/inspection/institution_0_segments.csv`. It retains all 40,298 rows and original cell values, with five added inspection columns:

- `timestamp_supplied`: exact timestamp text from the mapping.
- `timestamp_utc`: the same instant expressed in UTC.
- `gap_seconds`: elapsed time since the preceding row; blank for the first row.
- `segment_id`: a new block starts whenever that gap differs from 600 seconds.
- `boundary_before`: 1 when a timestamp break precedes this row, otherwise 0.

The six blocks contain 2,880, 767, 10,967, 25,449, 38, and 197 rows. All original cells and both raw file hashes were checked after generation. These labels do not explain or repair the breaks. Forecast-window checks remain pending; the selected outage policy is documented below.

## Exploratory monitoring-outage comparison

Run `python -m data_processing.inspect_outage` to regenerate `data/inspection/institution_0_outage_check.txt`. It compares full calendar days before (May 7–20), during (May 22–June 3), and after (June 5–18) the reported outage in 2024. Dates follow the supplied timestamp mapping; the paper does not specify the outage's timezone. May 21 and June 4 are omitted from these period averages because they are partial boundary days, not removed from the source data.

All 43 inspected days have 144 records and all adjacent timestamps are 600 seconds apart in UTC. Mean recorded bytes per row are 53.65% lower during the comparison period than before, and 34.86% lower than after. This is consistent with partial capture but does not establish this institution's exact outage effects. Weekday mix, holidays, and demand changes have not been controlled for. The comparison itself does not correct or exclude any observations.

## Selected outage exclusion policy

The chosen treatment is to exclude the suspect dates from future modeling and evaluation, while retaining the raw data. Mark May 20–June 5, 2024, inclusive, in the supplied mapping's calendar dates: the reported outage days plus one full day on either side.

Run `python -m data_processing.mark_segments` followed by `python -m data_processing.mark_exclusions`. The resulting `data/inspection/institution_0_review.csv` retains every row and adds `excluded_for_outage` and `exclusion_reason`. It marks 2,448 observations across 17 days; 37,850 observations are outside this exclusion. Original cells and input hashes were verified unchanged.

The buffer is a conservative project decision, not an author-provided incident label or an estimate of the true failure duration. Implemented window checks require no marked row anywhere from the earliest input through the target and require one timestamp segment. Observations are not stitched across exclusions. Unmarked observations are not certified free of capture problems.

## Institution comparison before selection

Run `python -m data_processing.compare_institutions` to regenerate the comparison CSV and text report in `data/inspection/`. All 283 institution-level 10-minute files were read directly from the archive. Of these, 56 have all 40,298 supplied time IDs present and 229 have at least 95% mapped-row coverage. Median coverage is 99.9231%. This describes record availability, not complete traffic capture.

Across these institution files, the comparison found no duplicate or unmapped IDs, non-increasing timestamps, or blank, invalid, negative, or zero `n_bytes` values. Other measurement columns were not audited across all institutions. Absent rows were not interpreted as zeros.

Institutions 0, 1, 2, and 3 each have 37,677 prospective 60-minute windows under an 18-record history, the outage policy, and guards on both endpoints of each uninterrupted timestamp block. Split assignment and actual feature construction are not included in these counts.

The user selected institution 0 for the first experiment after this comparison. It ties on prospective availability and has already received the full measurement-column audit. Selection is based on data availability and documented inspection, before any forecasting accuracy is known. This does not establish that it is the best forecasting series.

## Questions to settle first

1. What does one institution series measure? How are incoming and outgoing traffic counted?
2. What are the exact columns, units, and aggregation interval?
3. How does `id_time` map to a timestamp? What timezone and interval boundaries are used?
4. What do absent rows, zero values, and explicit missing values mean?
5. What filtering, aggregation, or imputation have the dataset authors already performed?
6. Are there known collection outages or documented anomalies?
7. Which series will we use, and what coverage and gaps does it have?

## Working traffic target and units

Use one institution's recorded `n_bytes` as the volume target. Express it as `recorded_traffic_mbps = n_bytes * 8 / (600 * 1_000_000)` when building the modeling table. The denominator is the documented nominal 10-minute aggregation period; Mbps uses decimal megabits. Do not divide by an irregular gap between timestamps.

The authors' collector adds forward and reverse bytes. This target represents recorded traffic involving the institution's IPs, not a directional download rate or a measured physical link's utilization. The collector can also update both internal endpoints of a flow; the reviewed repository does not establish deduplication in the institution export. Do not sum institutions into a supposedly unique network-wide demand total.

This definition is used for the offline experiment. It does not repair undercapture, infer packet-level timing, or establish live measurement availability. Boundary-adjacent rows are conservatively guarded in the feature table below. Institution 0 is the selected primary experimental series.

## Unscaled feature table

Run `python -m data_processing.build_features` after generating the review CSV. Output: `data/prepared/institution_0_features.csv`. All 40,298 rows and existing cells are retained. Added columns hold nominal recorded Mbps, a separately filled input rate, observation/missing flags, boundary guards, eligibility flags, and hour/weekday sine-cosine features.

Both the first and last observation in each of the six uninterrupted blocks are guarded: 12 observations. These guards and the 2,448 outage observations do not overlap, leaving 37,838 eligible input and target observations. This guard is a project precaution, not a finding that those measurements are invalid.

Missing inputs can be forward-filled using earlier observed values only within an allowed block. Missing targets remain missing and are not eligible. Filling resets at exclusions; future observations are never used. No byte observations are missing in this series, so no filling occurred. Calendar encoding uses the supplied timestamp clock, with seconds retained and without assuming a named timezone.

The table is unscaled. The complete preparation command constructs rolling statistics inside input windows, creates splits and forecasts' input/target windows, and fits training-only scalers.

## Day 2 checkpoint complete

Run `python -m data_processing.prepare_dataset`, then `python -m unittest -v tests.test_preparation`. Use 18 observations per input and separate direct 10-, 30-, and 60-minute targets. Rolling mean and population standard deviation use the latest up to six values inside each input window. No hidden history or future values contribute.

Chronological cuts use 70%/85% of the full ordered observation timeline before exclusions. Target nominal completion timestamps assign windows to splits. Validation starts at `2024-04-21T22:40:52+00:00`; test starts at `2024-06-02T22:10:52+00:00`. The outage removes early test windows: the first usable target completion is June 6 at 01:10:52 UTC for the 10-minute horizon. Remaining counts and timestamps are saved in `data/prepared/`.

The origin is the last input interval's nominal completion (supplied start +600 seconds). This is an offline availability assumption, not verified live export timing. Every full input-to-target path is regular at 600 seconds, avoids policy exclusions, and stays within one timestamp block. Missing targets are ineligible.

Scalers are fitted separately per horizon using training windows only. The saved configuration and source hashes make the preparation reproducible. The traffic/quality plot and path checks were generated, and all three causal/exclusion/scaler tests passed. Model training and allocation experiments remain Day 3 onward.

Anomalies may be real traffic events or measurement problems. We will not remove them solely because they look unusual, and we cannot guarantee an anomaly-free dataset.
