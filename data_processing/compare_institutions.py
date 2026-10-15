"""Compare institution byte-volume series without extracting or training them."""

import csv
import io
import math
import re
import tarfile
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

from data_processing.mark_exclusions import EXCLUDE_FIRST, EXCLUDE_LAST


def summarize(institution_id, rows, times) -> dict[str, Any]:
    ids = [row["id_time"] for row in rows]
    stamps = [times.get(time_id) for time_id in ids]
    values = []
    blank = invalid = negative = zero = 0
    for row in rows:
        text = row["n_bytes"]
        value = None
        if not text.strip():
            blank += 1
        else:
            try:
                candidate = float(text)
            except ValueError:
                invalid += 1
            else:
                if not math.isfinite(candidate):
                    invalid += 1
                elif candidate < 0:
                    negative += 1
                else:
                    value = candidate
                    zero += int(candidate == 0)
        values.append(value)

    gaps = [None]
    for previous, current in zip(stamps, stamps[1:]):
        gaps.append(None if previous is None or current is None else
                    (current.astimezone(timezone.utc) - previous.astimezone(timezone.utc)).total_seconds())
    # Both ends of every continuous run are conservative duration guards.
    boundary = [index == 0 or index == len(rows) - 1 or
                gaps[index] != 600 or
                (index + 1 < len(rows) and gaps[index + 1] != 600)
                for index in range(len(rows))]
    safe_runs = []
    current_run = longest_regular = regular_run = 0
    for index, (stamp, value) in enumerate(zip(stamps, values)):
        regular_run = regular_run + 1 if index and gaps[index] == 600 else 1
        longest_regular = max(longest_regular, regular_run)
        safe = (stamp is not None and value is not None and not boundary[index]
                and not EXCLUDE_FIRST <= stamp.date() <= EXCLUDE_LAST)
        if safe:
            if current_run and gaps[index] != 600:
                safe_runs.append(current_run)
                current_run = 0
            current_run += 1
        elif current_run:
            safe_runs.append(current_run)
            current_run = 0
    if current_run:
        safe_runs.append(current_run)

    observed = [value for value in values if value is not None]
    period_means = []
    for first, last in [(date(2024, 5, 7), date(2024, 5, 20)),
                        (date(2024, 5, 22), date(2024, 6, 3)),
                        (date(2024, 6, 5), date(2024, 6, 18))]:
        period = [value for stamp, value in zip(stamps, values)
                  if stamp is not None and value is not None and first <= stamp.date() <= last]
        period_means.append(mean(period) if period else None)
    before, during, after = period_means
    matched = len(set(ids) & set(times))
    return {
        "institution_id": institution_id,
        "rows": len(rows),
        "mapped_row_coverage_pct": round(100 * matched / len(times), 4),
        "absent_mapping_rows": len(times) - matched,
        "unmapped_time_ids": sum(stamp is None for stamp in stamps),
        "duplicate_ids": len(ids) - len(set(ids)),
        "non_increasing_transitions": sum(gap is not None and gap <= 0 for gap in gaps[1:]),
        "non_600_transitions": sum(gap != 600 for gap in gaps[1:]),
        "blank_n_bytes": blank,
        "invalid_n_bytes": invalid,
        "negative_n_bytes": negative,
        "zero_n_bytes": zero,
        "mean_n_bytes": mean(observed) if observed else "",
        "median_n_bytes": median(observed) if observed else "",
        "max_n_bytes": max(observed) if observed else "",
        "longest_600s_run_rows": longest_regular if rows else 0,
        "longest_safe_run_rows": max(safe_runs, default=0),
        # An 18-record input plus a six-step lead spans 24 records.
        "prospective_60min_windows": sum(max(0, length - 23) for length in safe_runs),
        "before_mean_n_bytes": before if before is not None else "",
        "during_mean_n_bytes": during if during is not None else "",
        "after_mean_n_bytes": after if after is not None else "",
        "during_vs_before_pct_change": 100 * (during / before - 1)
        if before is not None and before > 0 and during is not None else "",
    }


def main():
    project = Path(__file__).resolve().parents[1]
    raw = project / "data/raw/cesnet"
    with (raw / "sample/times_10_minutes.csv").open(newline="", encoding="utf-8-sig") as handle:
        mapping = list(csv.DictReader(handle))
    times = {row["id_time"]: datetime.fromisoformat(row["time"]) for row in mapping}
    if not times or len(times) != len(mapping) or any(stamp.tzinfo is None for stamp in times.values()):
        raise ValueError("Expected unique mapped IDs and timestamps with UTC offsets")

    results = []
    pattern = re.compile(r"institutions/agg_10_minutes/(\d+)\.csv")
    with tarfile.open(raw / "institutions.tar.gz", mode="r:gz") as archive:
        for member in archive:
            match = pattern.fullmatch(member.name)
            if not match or not member.isfile():
                continue
            binary = archive.extractfile(member)
            if binary is None:
                raise ValueError(f"Cannot read {member.name}")
            with io.TextIOWrapper(binary, encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames or not {"id_time", "n_bytes"}.issubset(reader.fieldnames):
                    raise ValueError(f"Unexpected schema: {member.name}")
                rows = list(reader)
            results.append(summarize(int(match.group(1)), rows, times))
            if len(results) % 25 == 0:
                print(f"Compared {len(results)} institutions", flush=True)
    if not results:
        raise ValueError("No institution-level 10-minute CSVs found")
    results.sort(key=lambda result: result["institution_id"])
    output = project / "data/inspection/institution_comparison.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)

    candidates = [result for result in results
                  if not any(result[key] for key in ["unmapped_time_ids", "duplicate_ids",
                      "non_increasing_transitions", "blank_n_bytes", "invalid_n_bytes", "negative_n_bytes"])]
    candidates.sort(key=lambda result: (-result["prospective_60min_windows"], result["institution_id"]))
    lines = [
        "INSTITUTION COMPARISON - NO MODEL TRAINING OR SERIES SELECTION",
        f"Institution files inspected: {len(results)}; timestamp mapping rows: {len(times)}",
        "Quality checks cover n_bytes, IDs, and timestamp ordering; not all 18 measurements.",
        "Coverage describes present mapping IDs, not complete traffic capture.",
        "Absent rows were not filled with zeros; observed zero byte counts remain valid.",
        "Safe runs exclude outage dates and both endpoints of each continuous timestamp run.",
        "Window counts are prospective for an 18-record history and six-step lead, without split assignment.",
        "Ranking uses usable window counts, then numeric ID; no model performance is involved.",
        "Outage-period means use observed rows only and can have unequal coverage/weekday mixes.",
        "A small traffic drop does not demonstrate that an institution escaped the probe failure.",
        "", "TOP TEN BY PROSPECTIVE WINDOW COUNT",
        "ID | mapped coverage % | longest safe run | prospective 60-min windows | mean bytes per record",
    ]
    for result in candidates[:10]:
        lines.append(f"{result['institution_id']} | {result['mapped_row_coverage_pct']} | "
                     f"{result['longest_safe_run_rows']} | {result['prospective_60min_windows']} | "
                     f"{result['mean_n_bytes']:.2f}")
    lines.extend(["", "Details: data/inspection/institution_comparison.csv",
                  "Reproduce: python -m data_processing.compare_institutions"])
    report = output.with_suffix(".txt")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
