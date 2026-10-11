"""Inspect CESNET institution 0 without cleaning or changing its data."""

import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path


def main():
    project = Path(__file__).resolve().parent
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
    if any(row["id_time"] not in times for row in rows):
        raise ValueError("Institution IDs absent from timestamp mapping")

    # Use absolute elapsed time so UTC-offset changes do not distort the gaps.
    dates = []
    for row in rows:
        stamp = datetime.fromisoformat(times[row["id_time"]])
        if stamp.tzinfo is None:
            raise ValueError("Timestamp has no UTC offset")
        dates.append(stamp.astimezone(timezone.utc))
    deviations = []
    for index in range(1, len(rows)):
        seconds = (dates[index] - dates[index - 1]).total_seconds()
        if seconds != 600:
            deviations.append(
                f"IDs {rows[index-1]['id_time']} -> {rows[index]['id_time']}: "
                f"{times[rows[index-1]['id_time']]} -> {times[rows[index]['id_time']]} "
                f"(elapsed {seconds:g} seconds)"
            )
    offsets = sorted({datetime.fromisoformat(value).strftime("%z")
                      for value in times.values()})

    lines = [
        "CESNET INSTITUTION 0: RAW SAMPLE AUDIT",
        "Source: data/raw/cesnet/sample/institution_0.csv",
        "Mapping: data/raw/cesnet/sample/times_10_minutes.csv",
        f"Rows: {len(rows)}; mapping IDs absent from sample: {len(set(times)-{r['id_time'] for r in rows})}",
        f"First mapped time: {times[rows[0]['id_time']]}",
        f"Last mapped time: {times[rows[-1]['id_time']]}",
        f"Mapping UTC offsets: {', '.join(offsets)}",
        f"Duplicate absolute timestamps in sample: {len(dates)-len(set(dates))}",
        f"Non-increasing time transitions: {sum(b <= a for a, b in zip(dates, dates[1:]))}",
        f"Transitions not exactly 600 seconds: {len(deviations)} of {len(rows)-1}",
        "", "PER-COLUMN RAW VALUE CHECKS",
        "blank = empty cell; nonnumeric = unparsable; nonfinite = NaN/infinity.",
        "Zero counts apply only to finite numeric values; no zeros are imputed.",
    ]
    ratios = {"tcp_udp_ratio_packets", "tcp_udp_ratio_bytes", "dir_ratio_packets", "dir_ratio_bytes"}
    total_problems = 0
    for column in columns:
        if column == "id_time":
            continue
        counts = {"blank": 0, "nonnumeric": 0, "nonfinite": 0, "negative": 0, "zero": 0}
        minimum, maximum = None, None
        outside_ratio_range = 0
        for row in rows:
            text = row[column]
            if text is None or not text.strip():
                counts["blank"] += 1
                continue
            try:
                value = Decimal(text)
            except InvalidOperation:
                counts["nonnumeric"] += 1
                continue
            if not value.is_finite():
                counts["nonfinite"] += 1
                continue
            counts["negative"] += int(value < 0)
            counts["zero"] += int(value == 0)
            minimum = value if minimum is None else min(minimum, value)
            maximum = value if maximum is None else max(maximum, value)
            if column in ratios and not 0 <= value <= 1:
                outside_ratio_range += 1
        total_problems += counts["blank"] + counts["nonnumeric"] + counts["nonfinite"]
        line = f"{column}: " + "; ".join(f"{key}={value}" for key, value in counts.items())
        line += f"; min={minimum}; max={maximum}"
        if column in ratios:
            line += f"; outside_[0,1]={outside_ratio_range}"
        lines.append(line)
    lines.extend(["", f"Total blank/nonnumeric/nonfinite cells: {total_problems}",
                  "", "ALL NON-600-SECOND TRANSITIONS"])
    lines.extend(deviations or ["None"])
    lines.extend(["", "LIMITS",
        "Complete rows and finite values do not prove complete traffic capture.",
        "This audit does not determine whether a probe outage affects this institution.",
        "No anomaly thresholds, cleaning, filling, resampling, or Mbps conversion applied.",
        "Do not infer missing-interval counts from irregular gaps without examining them.",
        "Reproduce: python audit_sample.py"])
    output = project / "data/inspection/institution_0_audit.txt"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:13]))
    print(f"Blank/nonnumeric/nonfinite cells: {total_problems}")
    print(f"Saved detailed report: {output}")


if __name__ == "__main__":
    main()
