"""Build unscaled historical features while preserving observations and flags."""

import csv
import math
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from mark_exclusions import EXCLUDE_FIRST, EXCLUDE_LAST


EXTRA_COLUMNS = [
    "recorded_traffic_mbps", "input_traffic_mbps", "target_observed", "input_missing",
    "excluded_for_boundary", "usable_input", "usable_target",
    "hour_sin", "hour_cos", "weekday_sin", "weekday_cos",
]


def add_features(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    stamps = [datetime.fromisoformat(row["timestamp_supplied"]) for row in rows]
    if any(stamp.tzinfo is None for stamp in stamps):
        raise ValueError("Supplied timestamps must contain UTC offsets")
    utc = [stamp.astimezone(timezone.utc) for stamp in stamps]
    for index, row in enumerate(rows):
        if datetime.fromisoformat(row["timestamp_utc"]) != utc[index]:
            raise ValueError("UTC and supplied timestamps disagree")
        if row["excluded_for_outage"] not in {"0", "1"}:
            raise ValueError("Expected binary outage flags")
        expected_flag = int(EXCLUDE_FIRST <= stamps[index].date() <= EXCLUDE_LAST)
        if int(row["excluded_for_outage"]) != expected_flag:
            raise ValueError("Outage flag disagrees with the chosen date policy")
        if index:
            gap = (utc[index] - utc[index - 1]).total_seconds()
            same_segment = row["segment_id"] == rows[index - 1]["segment_id"]
            if gap <= 0 or same_segment != (gap == 600):
                raise ValueError("Timestamp order or segment labels are inconsistent")

    derived = []
    previous_value = None
    for index, (row, stamp) in enumerate(zip(rows, stamps)):
        first = index == 0 or row["segment_id"] != rows[index - 1]["segment_id"]
        last = index == len(rows) - 1 or row["segment_id"] != rows[index + 1]["segment_id"]
        boundary = first or last
        allowed = not boundary and row["excluded_for_outage"] == "0"
        text = row["n_bytes"].strip()
        rate = None
        if text:
            try:
                volume = Decimal(text)
            except InvalidOperation as error:
                raise ValueError(f"Invalid n_bytes at ID {row['id_time']}") from error
            if not volume.is_finite() or volume < 0:
                raise ValueError(f"Nonfinite or negative n_bytes at ID {row['id_time']}")
            rate = float(volume * 8 / (600 * 1_000_000))
        # Carry only previous observations; exclusions reset the input history.
        if not allowed:
            previous_value = None
        elif rate is not None:
            previous_value = rate
        input_value = previous_value if allowed else None
        hour_fraction = (stamp.hour + stamp.minute / 60 + stamp.second / 3600) / 24
        weekday_fraction = stamp.weekday() / 7
        derived.append({
            **row,
            "recorded_traffic_mbps": "" if rate is None else rate,
            "input_traffic_mbps": "" if input_value is None else input_value,
            "target_observed": int(rate is not None),
            "input_missing": int(rate is None),
            "excluded_for_boundary": int(boundary),
            "usable_input": int(input_value is not None),
            "usable_target": int(allowed and rate is not None),
            "hour_sin": math.sin(2 * math.pi * hour_fraction),
            "hour_cos": math.cos(2 * math.pi * hour_fraction),
            "weekday_sin": math.sin(2 * math.pi * weekday_fraction),
            "weekday_cos": math.cos(2 * math.pi * weekday_fraction),
        })
    return derived


def main():
    project = Path(__file__).resolve().parent
    source = project / "data/inspection/institution_0_review.csv"
    if not source.exists():
        raise FileNotFoundError("Run mark_segments.py and mark_exclusions.py first")
    with source.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames
        rows = list(reader)
    required = {"id_time", "n_bytes", "timestamp_supplied", "timestamp_utc",
                "segment_id", "excluded_for_outage"}
    if not columns or not required.issubset(columns) or not rows:
        raise ValueError("Expected a nonempty review CSV with exact, unpadded headers")
    if set(columns) & set(EXTRA_COLUMNS):
        raise ValueError("Feature columns already exist in the source")
    if len({row["id_time"] for row in rows}) != len(rows):
        raise ValueError("Duplicate time IDs")
    derived = add_features(rows)
    output = project / "data/prepared/institution_0_features.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns) + EXTRA_COLUMNS)
        writer.writeheader()
        writer.writerows(derived)
    print(f"Rows preserved: {len(derived)}")
    print(f"Outage-marked rows: {sum(int(row['excluded_for_outage']) for row in derived)}")
    print(f"Boundary guards: {sum(row['excluded_for_boundary'] for row in derived)}")
    print(f"Missing byte observations: {sum(row['input_missing'] for row in derived)}")
    print(f"Usable input observations: {sum(row['usable_input'] for row in derived)}")
    print(f"Usable target observations: {sum(row['usable_target'] for row in derived)}")
    print("No scalers fitted and no forecasting windows or models created.")
    print(f"Saved: {output}")


if __name__ == "__main__":
    main()
