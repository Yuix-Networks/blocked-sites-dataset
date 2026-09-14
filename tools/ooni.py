"""The two OONI endpoints this dataset is built from.

OONI (ooni.org) runs volunteer probes worldwide and publishes aggregate
measurement counts under CC BY-SA 4.0. No key, no registration, generous
timeouts, occasionally slow — hence the retries.

Nothing here interprets the numbers. What confirmed and anomaly actually
mean, and why they must never be added together, is in METHODOLOGY.md.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.ooni.io"
USER_AGENT = (
    "blocked-sites-dataset/1.0 "
    "(+https://github.com/Yuix-Networks/blocked-sites-dataset)"
)
TIMEOUT = 300

#: web_connectivity is the test that answers "could this site be reached".
#: The others measure specific apps or performance; mixing them would put
#: two different questions in one column.
TEST_NAME = "web_connectivity"


class OONIError(RuntimeError):
    """OONI could not be reached, or answered with something unexpected."""


def _get(path, params=None, attempts=4):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    last = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            # A 4xx will not fix itself; a 5xx often does.
            if exc.code < 500:
                raise OONIError("%s: HTTP %s" % (url, exc.code)) from exc
            last = exc
        except Exception as exc:  # timeouts, connection resets, bad JSON
            last = exc
        if attempt < attempts - 1:
            time.sleep(5 * (attempt + 1))
    raise OONIError("%s: %s" % (url, last))


def country_names():
    """Two-letter code -> country name."""
    data = _get("/api/_/countries")
    return {c["alpha_2"]: c["name"] for c in data.get("countries", [])}


def _aggregate(since, until, axis, **extra):
    params = {
        "since": since.isoformat(),
        "until": until.isoformat(),
        "test_name": TEST_NAME,
        "axis_x": axis,
    }
    params.update(extra)
    data = _get("/api/v1/aggregation", params)
    rows = data.get("result")
    if not isinstance(rows, list):
        raise OONIError(
            "expected a list of rows for axis_x=%s, got %s — the API shape "
            "may have changed" % (axis, type(rows).__name__)
        )
    return rows


def by_country(since, until):
    """Measurement counts per country. ``until`` is exclusive, OONI's
    convention; an off-by-one here silently shifts a whole month."""
    return _aggregate(since, until, "probe_cc")


def by_domain(since, until, country_code):
    """Measurement counts per domain, within one country."""
    return _aggregate(since, until, "domain", probe_cc=country_code)
