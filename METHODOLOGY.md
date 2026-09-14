# How this dataset is built, and what it cannot tell you

## Where the numbers come from

Every row is derived from [OONI](https://ooni.org)'s public aggregation
API, specifically the `web_connectivity` test, which answers one question:
could this probe reach this site? OONI's other tests measure particular
apps or network performance; mixing them in would put two different
questions in one column.

For each month we ask OONI twice:

1. Per country, how many measurements were taken and how many confirmed
   blocks were found.
2. Per domain, within each country that passed the thresholds below, the
   same counts.

Nothing is inferred, modelled, or filled in. If OONI has no measurement,
this dataset has no row.

## The columns, precisely

| Column | Meaning |
|---|---|
| `measurements` | web_connectivity tests of this domain from this country in this month |
| `confirmed` | OONI positively identified blocking — it saw a block page, or another fingerprint that only censorship produces |
| `anomaly` | Something was wrong (DNS inconsistency, TCP reset, TLS mismatch) but nothing positively identified it as blocking |
| `ok` | The site was reached normally |
| `failures` | The measurement itself failed, so it says nothing either way |
| `confirmed_rate` | `confirmed / measurements`, to four places |

### Never add `confirmed` and `anomaly`

This is the single most common way censorship numbers get inflated, and
the reason they are separate columns here rather than one "blocked" total.

`confirmed` is strong evidence: a block page is hard to produce by
accident. `anomaly` is a catch-all for "this did not look right", and the
innocent explanations are numerous — the site was down, a CDN returned an
error, the probe's own network was flaky, a captive portal intervened. In
some countries anomalies outnumber confirmed blocks by an order of
magnitude, and reporting the sum as "blocked" would overstate censorship
by that much.

Use `confirmed` when you need to be able to defend the claim. Treat
`anomaly` as a lead to investigate, not a finding.

## Thresholds

- **Countries** need at least **1,000 measurements** in the month and at
  least one confirmed block. Below that, one probe having a bad afternoon
  moves the percentage several points.
- **Domains** need at least **20 measurements** in that country that
  month. Low enough to keep genuinely blocked but rarely tested sites,
  high enough to drop single-probe noise.

Both live at the top of `tools/build.py`. Rebuilding with different ones
is a two-line change.

## What this dataset cannot tell you

Being explicit about these is more useful than pretending they are not
there.

- **Absence is not evidence of absence.** A domain missing from a
  country's rows usually means nobody tested it there, not that it is
  reachable. The domains tested come largely from the [Citizen Lab test
  lists](https://github.com/citizenlab/test-lists), which are curated, not
  exhaustive.
- **Probes are volunteers, not a random sample.** OONI's coverage reflects
  where people chose to run probes — often a handful of networks in a
  country, sometimes one. A site blocked on one ISP and open on another
  produces a middling `confirmed_rate` that describes neither network.
- **A month is a long time.** Blocks that started or ended mid-month
  appear as partial rates. For anything time-sensitive, read the monthly
  files as a series rather than reading one in isolation.
- **Domain, not URL.** OONI measures URLs; this dataset aggregates them to
  the domain. A site blocked only on one path is flattened.
- **No causation.** A confirmed block says a network interfered. It does
  not say who ordered it, under what law, or whether it was deliberate
  policy rather than an over-broad filter.

## Reproducing it

    python tools/build.py 2026-08

Standard library only, no key, no account. It takes a few minutes: one
call for the country list, one per eligible country. The output is
deterministic for a given month — rows are sorted by country, then by
confirmed count, then alphabetically — so a diff between two runs is a
change in OONI's data, not in ours.
