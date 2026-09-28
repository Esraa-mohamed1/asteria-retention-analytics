# Source register

Two lenses, three indicators, one provider used in this build (Eurostat).
The adapter (`ingestion/eurostat_client.py`) is written generically enough
that a second provider (e.g. the World Bank's API) could be added as a
sibling adapter without touching curation, domain, or dashboard code —
that boundary is deliberate (see README architecture section).

## Provider: Eurostat

- **What it is**: the statistical office of the European Union; publishes
  harmonised, comparable statistics across EU/EEA member states.
- **Access**: public REST/JSON-stat API,
  `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}`.
  No API key required for the datasets used here.
- **Licensing**: Eurostat data is made available for reuse (including
  commercial reuse) free of charge under the European Commission's data
  reuse policy, subject to acknowledging the source. **Verify the current
  terms at `https://ec.europa.eu/eurostat/about-us/policies/copyright`
  before any production or external-facing use** — this document reflects
  a documented understanding at build time, not a live legal check
  (this container has no network access to that page).
- **Cadence**: varies per dataset (see table).
- **Access date recorded**: set programmatically per fetch as
  `retrieved_at` on every `RawObservation` (see `data/curated/external_indicators_raw.csv`
  after a live run).

## Indicators used

| Indicator ID | Eurostat dataset | Lens | Frequency | Unit | Assumed publication lag |
|---|---|---|---|---|---|
| `unemployment_rate` | `une_rt_m` | Labour supply | Monthly | % of active population, seasonally adjusted | 30 days |
| `job_vacancy_rate` | `jvs_q_nace2` | Labour demand | Quarterly | % of total posts | 75 days |
| `hicp_inflation` | `prc_hicp_manr` | Cost-of-living pressure | Monthly | % year-on-year | 20 days |

Publication-lag values are conservative, documented estimates (Eurostat's
own release calendars give exact per-dataset schedules; these figures
were not re-verified against the live calendar in this offline build and
should be reconfirmed — see `config.PUBLICATION_LAG_DAYS` — before the
temporal-join logic is relied on for a real decision).

## Canonical mapping

Eurostat's `geo` dimension uses **"EL"** for Greece, while the supplied
HR data (and this project's canonical schema) uses **"GR"**. This
translation happens in exactly one place: `ingestion/eurostat_client.py`
(`ISO_TO_EUROSTAT_GEO`), so no other module needs to know Eurostat's
naming convention.

## Known limitations

- Only ~3 years of monthly/quarterly history are bundled as replay
  fixtures for offline/test use (`data/fixtures/*.json`); these are
  illustrative-shape fixtures, not full live pulls — a live run against
  the real API (network access required, `--use-fixtures` omitted from
  the CLI flag) would retrieve the full available history.
- Country coverage in this indicator set is limited to the geo codes
  requested (the six Asteria operating countries); no other member
  states are ingested.
- Seasonally-adjusted unemployment figures are subject to periodic
  historical revision by Eurostat; this pipeline does not currently
  detect or reconcile revisions to previously-ingested periods (a
  documented gap, not a silent one — see README "Known limitations").
