"""Build one month of the dataset.

    python tools/build.py 2026-08

Writes data/monthly/<month>.csv, refreshes data/latest.csv, and appends the
month to data/summary.csv.

The shape of the work: ask OONI which countries were measured enough to say
anything about, then ask it, per country, how each domain fared. One HTTP
call for the country list and one per country — 68 or so in a typical month.
"""
import argparse
import csv
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ooni  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MONTHLY = ROOT / "data" / "monthly"
LATEST = ROOT / "data" / "latest.csv"
SUMMARY = ROOT / "data" / "summary.csv"

#: A country with only a handful of measurements produces percentages that
#: swing wildly on one probe having a bad afternoon.
MIN_COUNTRY_MEASUREMENTS = 1000

#: Same logic one level down. Twenty is low enough to keep genuinely
#: blocked-but-rarely-tested domains, high enough to drop single-probe noise.
MIN_DOMAIN_MEASUREMENTS = 20

FIELDS = [
    "month",
    "country_code",
    "country_name",
    "domain",
    "measurements",
    "confirmed",
    "anomaly",
    "ok",
    "failures",
    "confirmed_rate",
]

SUMMARY_FIELDS = [
    "month",
    "country_code",
    "country_name",
    "domains_listed",
    "domains_with_confirmed_blocking",
    "measurements",
    "confirmed",
]


def month_bounds(month):
    """('2026-08') -> (date(2026,8,1), date(2026,9,1)). The upper bound is
    exclusive, matching OONI."""
    year, mon = (int(part) for part in month.split("-"))
    start = datetime.date(year, mon, 1)
    end = datetime.date(year + (mon == 12), (mon % 12) + 1, 1)
    return start, end


def last_complete_month(today=None):
    today = today or datetime.date.today()
    first_of_this = today.replace(day=1)
    last_month = first_of_this - datetime.timedelta(days=1)
    return "%04d-%02d" % (last_month.year, last_month.month)


def eligible_countries(rows):
    """Countries measured enough to report on, and where something was
    actually confirmed blocked. A country with no confirmed blocking has no
    rows to contribute to a dataset about blocked sites."""
    return sorted(
        row["probe_cc"]
        for row in rows
        if (row.get("measurement_count") or 0) >= MIN_COUNTRY_MEASUREMENTS
        and (row.get("confirmed_count") or 0) > 0
    )


def domain_rows(month, code, name, rows):
    """Turn one country's per-domain counts into dataset rows."""
    out = []
    for row in rows:
        domain = (row.get("domain") or "").strip().lower()
        measurements = row.get("measurement_count") or 0
        if not domain or measurements < MIN_DOMAIN_MEASUREMENTS:
            continue
        confirmed = row.get("confirmed_count") or 0
        out.append({
            "month": month,
            "country_code": code,
            "country_name": name,
            "domain": domain,
            "measurements": measurements,
            "confirmed": confirmed,
            "anomaly": row.get("anomaly_count") or 0,
            "ok": row.get("ok_count") or 0,
            "failures": row.get("failure_count") or 0,
            # Rounded to four places: the input is a count ratio, and more
            # digits would imply a precision the sampling does not have.
            "confirmed_rate": round(confirmed / measurements, 4),
        })
    # Most-blocked first, then alphabetical, so a diff between two months is
    # about the data and not about ordering.
    out.sort(key=lambda r: (-r["confirmed"], r["domain"]))
    return out


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def merge_summary(new_rows):
    """Replace this month's summary rows, keep every other month."""
    months = {row["month"] for row in new_rows}
    kept = []
    if SUMMARY.exists():
        with SUMMARY.open(encoding="utf-8") as handle:
            kept = [r for r in csv.DictReader(handle) if r["month"] not in months]
    combined = kept + new_rows
    combined.sort(key=lambda r: (r["month"], r["country_code"]))
    return combined


def build(month):
    since, until = month_bounds(month)
    print("Building %s (%s to %s, exclusive)" % (month, since, until))

    names = ooni.country_names()
    countries = eligible_countries(ooni.by_country(since, until))
    print("%d countries measured enough to report on" % len(countries))
    if not countries:
        print("No eligible countries — refusing to write an empty month.",
              file=sys.stderr)
        return 1

    all_rows = []
    summary_rows = []
    for index, code in enumerate(countries, 1):
        name = names.get(code, code)
        rows = domain_rows(month, code, name, ooni.by_domain(since, until, code))
        all_rows.extend(rows)
        blocked = sum(1 for r in rows if r["confirmed"] > 0)
        summary_rows.append({
            "month": month,
            "country_code": code,
            "country_name": name,
            "domains_listed": len(rows),
            "domains_with_confirmed_blocking": blocked,
            "measurements": sum(r["measurements"] for r in rows),
            "confirmed": sum(r["confirmed"] for r in rows),
        })
        print("  [%2d/%d] %-4s %5d domains, %4d with confirmed blocking"
              % (index, len(countries), code, len(rows), blocked))

    if not all_rows:
        print("Every country came back empty — refusing to write.", file=sys.stderr)
        return 1

    all_rows.sort(key=lambda r: (r["country_code"], -r["confirmed"], r["domain"]))
    path = MONTHLY / ("%s.csv" % month)
    write_csv(path, FIELDS, all_rows)
    write_csv(LATEST, FIELDS, all_rows)
    write_csv(SUMMARY, SUMMARY_FIELDS, merge_summary(summary_rows))

    print("\n%d rows across %d countries -> %s (%.1f KB)"
          % (len(all_rows), len(countries), path.relative_to(ROOT),
             path.stat().st_size / 1024))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "month", nargs="?", default=None,
        help="YYYY-MM. Defaults to the last complete month.",
    )
    args = parser.parse_args(argv)
    month = args.month or last_complete_month()
    try:
        month_bounds(month)
    except (ValueError, IndexError):
        parser.error("%r is not a YYYY-MM month" % month)
    return build(month)


if __name__ == "__main__":
    raise SystemExit(main())
