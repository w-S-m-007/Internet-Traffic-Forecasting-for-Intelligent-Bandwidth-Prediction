"""Compare recorded traffic around the reported probe outage; do not clean it."""

import csv
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import mean, median


def main():
    project = Path(__file__).resolve().parent
    sample = project / "data/raw/cesnet/sample"
    with (sample / "times_10_minutes.csv").open(newline="", encoding="utf-8-sig") as handle:
        time_rows = list(csv.DictReader(handle))
    times = {row["id_time"]: row["time"] for row in time_rows}
    if len(times) != len(time_rows):
        raise ValueError("Duplicate IDs in the timestamp mapping")
    with (sample / "institution_0.csv").open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or len({row["id_time"] for row in rows}) != len(rows):
        raise ValueError("Expected nonempty institution data with unique time IDs")

    daily = defaultdict(list)
    stamps = []
    for row in rows:
        if row["id_time"] not in times:
            raise ValueError(f"Missing timestamp for ID {row['id_time']}")
        stamp = datetime.fromisoformat(times[row["id_time"]])
        if stamp.tzinfo is None:
            raise ValueError("Timestamp has no UTC offset")
        if date(2024, 5, 7) <= stamp.date() <= date(2024, 6, 18):
            daily[stamp.date()].append(row)
            stamps.append(stamp.astimezone(timezone.utc))
    if not stamps or any(b <= a for a, b in zip(stamps, stamps[1:])):
        raise ValueError("Expected nonempty, chronologically ordered comparison data")

    metrics = ["n_bytes", "n_packets", "n_flows"]
    lines = [
        "INSTITUTION 0: EXPLORATORY OUTAGE COMPARISON",
        "Source: https://arxiv.org/html/2409.18874v1 (section 4.1)",
        "Authors report a probe failure approximately May 21 16:30 to June 4 20:00, 2024.",
        "The cited passage does not specify the timezone or affected institution IDs.",
        "Dates below use the supplied timestamp's calendar date, not an inferred timezone.",
        "May 21 and June 4 are excluded from period averages as partial boundary days.",
        "Periods have different lengths and weekday mixes; this is not a causal estimate.",
        "Means and medians below are raw counts per record, not bandwidth rates.",
        "",
    ]
    periods = [
        ("Before", date(2024, 5, 7), date(2024, 5, 20)),
        ("During", date(2024, 5, 22), date(2024, 6, 3)),
        ("After", date(2024, 6, 5), date(2024, 6, 18)),
    ]
    period_means = {}
    for label, first, last in periods:
        entries = [row for day, values in daily.items() if first <= day <= last
                   for row in values]
        days = sum(first <= day <= last for day in daily)
        lines.append(f"{label}: {first} through {last}; days={days}; rows={len(entries)}")
        for metric in metrics:
            values = [int(row[metric]) for row in entries]
            period_means[label, metric] = mean(values)
            lines.append(f"  {metric}: mean={mean(values):.2f}; median={median(values):.2f}")
    lines.append("")
    for label in ["Before", "After"]:
        reference = period_means[label, "n_bytes"]
        if reference > 0:
            drop = 100 * (1 - period_means["During", "n_bytes"] / reference)
            lines.append(f"During-period mean bytes is {drop:.2f}% below {label.lower()}.")
    lines.extend([
        f"Comparison days: {len(daily)}; rows: {len(stamps)}",
        f"Rows per day: {min(map(len, daily.values()))} to {max(map(len, daily.values()))}",
        f"Non-600-second transitions: {sum((b-a).total_seconds() != 600 for a, b in zip(stamps, stamps[1:]))}",
        "", "DAILY RECORDED TOTALS",
        "date | rows | n_bytes sum | n_packets sum | n_flows sum",
    ])
    summary = "\n".join(lines[:-3])
    for day, entries in sorted(daily.items()):
        totals = [sum(int(row[metric]) for row in entries) for metric in metrics]
        lines.append(" | ".join(map(str, [day, len(entries), *totals])))
    lines.extend([
        "", "INTERPRETATION AND LIMITS",
        "A decrease coinciding with the reported failure is consistent with undercapture.",
        "It does not identify the affected probe or quantify this institution's lost traffic.",
        "Seasonality, holidays, and genuine demand changes have not been controlled for.",
        "Complete timestamps do not prove complete traffic capture.",
        "No rows or values were changed; no filling, exclusion policy, or model was applied.",
        "Reproduce: python inspect_outage.py",
    ])
    output = project / "data/inspection/institution_0_outage_check.txt"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(summary)
    print(f"Saved report: {output}")


if __name__ == "__main__":
    main()
