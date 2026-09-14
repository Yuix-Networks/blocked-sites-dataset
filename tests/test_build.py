"""Tests for the parts of the build that are not the network.

The HTTP calls are OONI's business; what is ours is the filtering, the
arithmetic and the ordering — and those are what would go wrong quietly.
"""
import csv
import datetime
import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))


def _build_module():
    spec = importlib.util.spec_from_file_location(
        "build", ROOT / "tools" / "build.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = _build_module()


# --- month arithmetic ------------------------------------------------------


def test_month_bounds_are_half_open():
    """OONI's `until` is exclusive. An off-by-one here shifts a whole month
    of measurements into the wrong file."""
    assert build.month_bounds("2026-08") == (
        datetime.date(2026, 8, 1), datetime.date(2026, 9, 1)
    )


def test_month_bounds_across_a_year_boundary():
    assert build.month_bounds("2026-12") == (
        datetime.date(2026, 12, 1), datetime.date(2027, 1, 1)
    )


def test_month_bounds_rejects_nonsense():
    for bad in ("2026", "August", "2026-13-01", ""):
        with pytest.raises((ValueError, IndexError)):
            build.month_bounds(bad)


def test_last_complete_month_is_the_previous_one():
    assert build.last_complete_month(datetime.date(2026, 9, 15)) == "2026-08"
    assert build.last_complete_month(datetime.date(2026, 1, 1)) == "2025-12"


# --- which countries make the cut ------------------------------------------


def _country(cc, measurements, confirmed):
    return {"probe_cc": cc, "measurement_count": measurements,
            "confirmed_count": confirmed}


def test_a_thinly_measured_country_is_excluded():
    """Below the floor one probe having a bad afternoon moves the rate by
    several points."""
    rows = [_country("XX", 999, 500), _country("YY", 1000, 1)]
    assert build.eligible_countries(rows) == ["YY"]


def test_a_country_with_no_confirmed_blocking_is_excluded():
    """It has nothing to contribute to a dataset about blocked sites."""
    assert build.eligible_countries([_country("SE", 500000, 0)]) == []


def test_eligible_countries_are_sorted():
    rows = [_country(cc, 5000, 5) for cc in ("TR", "IR", "RU")]
    assert build.eligible_countries(rows) == ["IR", "RU", "TR"]


def test_missing_counters_are_treated_as_zero():
    """OONI omits a key rather than sending null when a count is zero."""
    assert build.eligible_countries([{"probe_cc": "ZZ"}]) == []


# --- turning counts into rows ----------------------------------------------


def _domain(name, measurements, confirmed=0, anomaly=0, ok=0, failure=0):
    return {"domain": name, "measurement_count": measurements,
            "confirmed_count": confirmed, "anomaly_count": anomaly,
            "ok_count": ok, "failure_count": failure}


def test_a_rarely_tested_domain_is_dropped():
    rows = build.domain_rows("2026-08", "TR", "Turkey", [
        _domain("rare.example", 19, confirmed=19),
        _domain("common.example", 20, confirmed=1),
    ])
    assert [r["domain"] for r in rows] == ["common.example"]


def test_confirmed_rate_is_confirmed_over_measurements():
    row, = build.domain_rows("2026-08", "IR", "Iran",
                             [_domain("x.example", 1000, confirmed=747)])
    assert row["confirmed_rate"] == 0.747


def test_confirmed_rate_is_not_over_rounded():
    """Four places: the input is a count ratio, and more digits would imply
    precision the sampling does not have."""
    row, = build.domain_rows("2026-08", "IR", "Iran",
                             [_domain("x.example", 30, confirmed=10)])
    assert row["confirmed_rate"] == 0.3333


def test_anomaly_is_never_folded_into_confirmed():
    """The whole point of keeping them apart."""
    row, = build.domain_rows("2026-08", "TR", "Turkey",
                             [_domain("x.example", 100, confirmed=2, anomaly=40)])
    assert row["confirmed"] == 2
    assert row["anomaly"] == 40
    assert row["confirmed_rate"] == 0.02


def test_rows_are_ordered_most_blocked_first():
    rows = build.domain_rows("2026-08", "TR", "Turkey", [
        _domain("b.example", 100, confirmed=5),
        _domain("a.example", 100, confirmed=50),
    ])
    assert [r["domain"] for r in rows] == ["a.example", "b.example"]


def test_ties_break_alphabetically():
    """So a diff between two months is about the data, not the ordering."""
    rows = build.domain_rows("2026-08", "TR", "Turkey", [
        _domain("z.example", 100, confirmed=5),
        _domain("a.example", 100, confirmed=5),
    ])
    assert [r["domain"] for r in rows] == ["a.example", "z.example"]


def test_domains_are_normalised():
    row, = build.domain_rows("2026-08", "TR", "Turkey",
                             [_domain("  WWW.Example.COM ", 50)])
    assert row["domain"] == "www.example.com"


def test_a_blank_domain_is_dropped():
    assert build.domain_rows("2026-08", "TR", "Turkey", [_domain("", 500)]) == []


def test_every_declared_field_is_present():
    row, = build.domain_rows("2026-08", "TR", "Turkey", [_domain("x.example", 50)])
    assert sorted(row) == sorted(build.FIELDS)


# --- the summary accumulates ----------------------------------------------


def test_summary_replaces_the_month_being_rebuilt(tmp_path, monkeypatch):
    summary = tmp_path / "summary.csv"
    with summary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=build.SUMMARY_FIELDS,
                                lineterminator="\n")
        writer.writeheader()
        writer.writerow({f: "" for f in build.SUMMARY_FIELDS}
                        | {"month": "2026-07", "country_code": "TR",
                           "confirmed": "1"})
        writer.writerow({f: "" for f in build.SUMMARY_FIELDS}
                        | {"month": "2026-08", "country_code": "TR",
                           "confirmed": "999"})
    monkeypatch.setattr(build, "SUMMARY", summary)

    merged = build.merge_summary([
        {f: "" for f in build.SUMMARY_FIELDS}
        | {"month": "2026-08", "country_code": "TR", "confirmed": "2"}
    ])

    assert [(r["month"], r["confirmed"]) for r in merged] == [
        ("2026-07", "1"), ("2026-08", "2")
    ]


def test_summary_is_sorted_by_month_then_country(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "SUMMARY", tmp_path / "absent.csv")
    merged = build.merge_summary([
        {f: "" for f in build.SUMMARY_FIELDS} | {"month": "2026-08", "country_code": "TR"},
        {f: "" for f in build.SUMMARY_FIELDS} | {"month": "2026-08", "country_code": "IR"},
    ])
    assert [r["country_code"] for r in merged] == ["IR", "TR"]
