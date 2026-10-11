"""Mark the chosen outage exclusion policy without deleting observations."""

import csv
from datetime import date, datetime
from pathlib import Path


# One full calendar day on each side of the reported May 21-June 4 outage.
# Use dates in the supplied mapping; incident times have no stated timezone.
EXCLUDE_FIRST = date(2024, 5, 20)
EXCLUDE_LAST = date(2024, 6, 5)
REASON = "reported_probe_outage_with_one_day_buffer"


def main():
    project = Path(__file__).resolve().parent
    source = project / "data/inspection/institution_0_segments.csv"
    if not source.exists():
        raise FileNotFoundError("Run python mark_segments.py before this script")
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames
        rows = list(reader)
    required = {"id_time", "timestamp_supplied", "segment_id"}
    if not columns or not required.issubset(columns) or not rows:
        raise ValueError("Expected nonempty data with timestamp and segment labels")
    if len({row["id_time"] for row in rows}) != len(rows):
        raise ValueError("Duplicate time IDs")
    added_columns = ["excluded_for_outage", "exclusion_reason"]
    if set(columns) & set(added_columns):
        raise ValueError("Exclusion columns already exist in the input")

    annotated = []
    excluded_count = 0
    excluded_dates = set()
    for row in rows:
        stamp = datetime.fromisoformat(row["timestamp_supplied"])
        if stamp.tzinfo is None:
            raise ValueError("Timestamp has no UTC offset")
        excluded = EXCLUDE_FIRST <= stamp.date() <= EXCLUDE_LAST
        annotated.append({
            **row,
            "excluded_for_outage": int(excluded),
            "exclusion_reason": REASON if excluded else "",
        })
        if excluded:
            excluded_count += 1
            excluded_dates.add(stamp.date())

    output = project / "data/inspection/institution_0_review.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns) + added_columns)
        writer.writeheader()
        writer.writerows(annotated)
    print(f"Policy dates: {EXCLUDE_FIRST} through {EXCLUDE_LAST}, inclusive")
    print(f"Rows retained in inspection copy: {len(rows)}")
    print(f"Marked for outage exclusion: {excluded_count} across {len(excluded_dates)} days")
    print(f"Outside this exclusion: {len(rows) - excluded_count} rows (not a quality guarantee)")
    print("Future windows must avoid marked rows and timestamp boundaries.")
    print(f"Saved review copy: {output}")


if __name__ == "__main__":
    main()
