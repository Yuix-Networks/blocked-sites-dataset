# blocked-sites-dataset

Which websites are measurably blocked, in which country, month by month —
as CSV you can open in anything.

> **The data is OONI's, not ours.** Every number here comes from
> [OONI](https://ooni.org)'s public measurements and carries their licence:
> [**CC BY-NC-SA 4.0**](https://creativecommons.org/licenses/by-nc-sa/4.0/)
> — attribution, **non-commercial**, share-alike. What this repository adds
> is the aggregation and the documentation. If your use is commercial, that
> is a conversation to have with OONI. Full terms and the attribution to
> carry: [LICENSE](LICENSE).

Every row comes from [OONI](https://ooni.org)'s public measurements. OONI
publishes the raw data, but answering "what is blocked in Turkey right
now" from it means learning an API, understanding four different counters
and knowing which two must never be added together. This repository does
that once a month and commits the result.

```
month,country_code,country_name,domain,measurements,confirmed,anomaly,ok,failures,confirmed_rate
2026-08,IR,Iran,www.facebook.com,5092,3804,786,296,206,0.7471
2026-08,IR,Iran,www.instagram.com,4842,3634,759,218,231,0.7505
2026-08,IR,Iran,twitter.com,4510,3205,870,183,252,0.7107
```

## The files

| Path | What it is |
|---|---|
| `data/latest.csv` | The most recent complete month. Stable URL, use this one. |
| `data/monthly/YYYY-MM.csv` | One file per month, never rewritten once complete. |
| `data/summary.csv` | One row per country per month: totals, no domains. |

Raw links work directly in pandas, R, or `curl`:

```python
import pandas as pd
df = pd.read_csv(
    "https://raw.githubusercontent.com/Yuix-Networks/"
    "blocked-sites-dataset/main/data/latest.csv"
)
turkey = df[(df.country_code == "TR") & (df.confirmed > 0)]
print(turkey.nlargest(20, "confirmed_rate")[["domain", "confirmed_rate"]])
```

## Read this before quoting a number

**`confirmed` and `anomaly` are different things and must never be added.**
`confirmed` means OONI positively identified blocking — it saw a block
page. `anomaly` means something looked wrong, which is often censorship
and often a site being down, a flaky network, or a CDN error. Summing them
is how censorship statistics get inflated, and in some countries it would
inflate them several-fold.

**A domain missing from a country is usually untested, not unblocked.**
The tested domains come largely from the [Citizen Lab test
lists](https://github.com/citizenlab/test-lists), which are curated.

**Probes are volunteers, not a sample.** A country's numbers reflect the
networks where people happened to run OONI Probe — sometimes only one ISP.

[METHODOLOGY.md](METHODOLOGY.md) has the rest: the exact column
definitions, the thresholds and why they are where they are, and what the
dataset structurally cannot tell you.

## Rebuilding it

Standard library only. No key, no account.

```
python tools/build.py 2026-08     # a specific month
python tools/build.py             # the last complete month
```

A GitHub Action runs it on the 4th of each month and commits the result.
Output is deterministic for a given month, so a diff is a change in OONI's
data rather than in ours.

## Citing it

Each month's file is also published as a GitHub release, so a citation can
point at a fixed snapshot rather than at a moving `main`. If you need a
persistent identifier, cite the DOI on the release; `CITATION.cff` in this
repository carries the machine-readable version, and GitHub renders it as
a **Cite this repository** button in the sidebar.

Whatever you cite, cite OONI too — the measurements are theirs:

```
OONI (https://ooni.org), CC BY-NC-SA 4.0, aggregated by Unblock Master,
blocked-sites-dataset, https://github.com/Yuix-Networks/blocked-sites-dataset
```

## Licence

The **data** in `data/` is derived from OONI's measurements and carries
their licence:
[**CC BY-NC-SA 4.0**](https://creativecommons.org/licenses/by-nc-sa/4.0/)
— attribution, non-commercial, share-alike. Note the **NC**: OONI licenses
its website content under BY-SA but its *data* under BY-NC-SA, and this is
a derivative of the data. If you need it for a commercial purpose, ask
OONI, not us.

Attribution to carry with any reuse:

```
Data: OONI (https://ooni.org), CC BY-NC-SA 4.0, aggregated by
Unblock Master — https://www.unblockmaster.com/internet-censorship-tracker/
```

The **code** in `tools/` is [MIT](LICENSE-CODE).

## Related

- [Internet Censorship Tracker](https://www.unblockmaster.com/internet-censorship-tracker/)
  — the same measurements per country, with a chart and a live SVG badge.
- [iporigin](https://github.com/Yuix-Networks/iporigin) — offline lookup of
  which provider, VPN or crawler an IP address belongs to.
