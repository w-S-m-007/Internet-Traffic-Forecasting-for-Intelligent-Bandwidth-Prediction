"""Label uninterrupted 10-minute blocks in a separate inspection CSV."""

import csv
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def main():
    project = Path(__file__).resolve().parents[1]
    sample = project / "data/raw/cesnet/sample"
    with (sample / "times_10_minutes.csv").open(newline="", encoding="utf-8-sig") as handle:
        time_rows = list(csv.DictReader(handle))
    times = {row["id_time"]: row["time"] for row in time_rows}
    if len(times) != len(time_rows):
        raise ValueError("Duplicate IDs in the timestamp mapping")

    with (sample / "institution_0.csv").open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames
        rows = list(reader)
    if not columns or "id_time" not in columns or not rows:
        raise ValueError("Expected a nonempty institution CSV with id_time")
    if len({row["id_time"] for row in rows}) != len(rows):
        raise ValueError("Duplicate institution time IDs")

    added_columns = ["timestamp_supplied", "timestamp_utc", "gap_seconds",
                     "segment_id", "boundary_before"]
    if set(columns) & set(added_columns):
        raise ValueError("Inspection column name already exists in the source")

    previous = None
    segment_id = 1
    counts = Counter()
    annotated = []
    for row in rows:
        if row["id_time"] not in times:
            raise ValueError(f"Missing timestamp for ID {row['id_time']}")
        supplied = times[row["id_time"]]
        stamp = datetime.fromisoformat(supplied)
        if stamp.tzinfo is None:
            raise ValueError(f"Timestamp has no UTC offset for ID {row['id_time']}")
        utc_stamp = stamp.astimezone(timezone.utc)
        gap = None if previous is None else (utc_stamp - previous).total_seconds()
        if gap is not None and gap <= 0:
            raise ValueError(f"Non-increasing timestamp at ID {row['id_time']}")
        boundary = gap is not None and gap != 600
        if boundary:
            segment_id += 1
        annotated.append({
            **row,
            "timestamp_supplied": supplied,
            "timestamp_utc": utc_stamp.isoformat(),
            "gap_seconds": "" if gap is None else f"{gap:g}",
            "segment_id": segment_id,
            "boundary_before": int(boundary),
        })
        counts[segment_id] += 1
        previous = utc_stamp

    output = project / "data/inspection/institution_0_segments.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns) + added_columns)
        writer.writeheader()
        writer.writerows(annotated)
    print(f"Rows: {len(annotated)}; segments: {segment_id}; boundaries: {segment_id - 1}")
    for number, count in sorted(counts.items()):
        print(f"Segment {number}: {count} rows")
    print(f"Saved inspection copy: {output}")


if __name__ == "__main__":
    main()
