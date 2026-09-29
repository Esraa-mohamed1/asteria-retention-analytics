# Source register and contracts

Two providers, five indicators, three lenses. Sources chosen to represent:
**labour supply** (unemployment rate, labour force participation),
**labour demand** (job vacancy rate), **cost-of-living pressure** (HICP),
and **economic cycle** (GDP growth).

---

## Provider 1: Eurostat

| Field | Detail |
|---|---|
| **What it is** | Statistical office of the European Union; publishes harmonised, comparable statistics across EU/EEA member states |
| **URL** | https://ec.europa.eu/eurostat |
| **API endpoint** | `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}` |
| **Authentication** | None required for the datasets used here |
| **Licence / terms** | Free reuse including commercial, with acknowledgement of source. Governed by the European Commission reuse policy. **Verify current terms before any production use:** https://ec.europa.eu/eurostat/about-us/policies/copyright |
| **Coverage** | EU/EEA member states; this pipeline requests only the six Asteria operating countries (BG, GR, IE, IT, PL, RO) |
| **Access date** | Recorded per fetch as ISO timestamp in `data/external_raw/eurostat/` filename |
| **Geo note** | Eurostat uses `EL` for Greece (ISO-2 is `GR`). Translation happens once, in `ingestion/eurostat_client.py`. No other module knows this mapping |
| **Known issue** | Seasonally-adjusted unemployment figures are subject to periodic backward revision. This pipeline does not detect or reconcile revisions to previously-ingested periods |

### Eurostat indicators

| Indicator ID | Dataset code | Label | Lens | Frequency | Unit | Publ. lag (assumed) | Max age | Docs |
|---|---|---|---|---|---|---|---|---|
| `unemployment_rate` | `une_rt_m` | Unemployment rate, seasonally adj. (% active pop.) | Labour supply | Monthly | % of active population | 45 days | 120 days | [link](https://ec.europa.eu/eurostat/databrowser/view/une_rt_m/default/table) |
| `job_vacancy_rate` | `jvs_q_nace2` | Job vacancy rate (% of posts), all activities | Labour demand | Quarterly | % of total posts | 90 days | 200 days | [link](https://ec.europa.eu/eurostat/databrowser/view/jvs_q_nace2/default/table) |
| `hicp_inflation` | `prc_hicp_manr` | HICP inflation, annual rate of change (%), all items | Cost-of-living | Monthly | % year on year | 30 days | 120 days | [link](https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_manr/default/table) |

**Publication-lag note:** Values above are conservative estimates, not verified
against Eurostat's live release calendar in this offline build. The lag is used
to compute `available_from = period_end + lag_days`; a value is only joined to
a retention evaluation date if `available_from ≤ eval_date`. Reconfirm lags
before relying on this join for a real decision — use
`python -m asteria_retention doctor` to check freshness live.

---

## Provider 2: World Bank Open Data

| Field | Detail |
|---|---|
| **What it is** | World Bank Group; publishes development and macroeconomic statistics for ~200 countries |
| **URL** | https://data.worldbank.org |
| **API endpoint** | `https://api.worldbank.org/v2/country/{iso3}/indicator/{code}?format=json&date={start}:{end}&per_page=100` |
| **Authentication** | None required |
| **Licence / terms** | Creative Commons Attribution 4.0 (CC BY 4.0) for most datasets. Verify at https://www.worldbank.org/en/about/legal/terms-of-use-for-datasets |
| **Coverage** | Country codes are ISO-3 in World Bank API; mapped from ISO-2 via `config.COUNTRIES[iso2].iso3` |
| **Cadence** | Annual (calendar year); published with a long lag |
| **Access date** | Recorded in `data/external_raw/worldbank/` with ISO timestamp |

### World Bank indicators

| Indicator ID | WB code | Label | Lens | Frequency | Unit | Publ. lag (assumed) | Max age | Docs |
|---|---|---|---|---|---|---|---|---|
| `gdp_growth` | `NY.GDP.MKTP.KD.ZG` | GDP growth (annual %) | Economic cycle | Annual | % annual | 300 days | 760 days | [link](https://data.worldbank.org/indicator/NY.GDP.MKTP.KD.ZG) |
| `labour_force_participation` | `SL.TLF.CACT.ZS` | Labour force participation rate (% population 15+, ILO modelled) | Labour supply | Annual | % of population 15+ | 365 days | 760 days | [link](https://data.worldbank.org/indicator/SL.TLF.CACT.ZS) |

---

## Canonical country mapping

| HR extract code | Canonical ISO-2 | Notes |
|---|---|---|
| `BG` | `BG` | Direct match |
| `GR` | `GR` | Direct match |
| `EL` | `GR` | Eurostat-style Greece; aliased in `config.COUNTRY_CODE_ALIASES` |
| `IE` | `IE` | Direct match |
| `IT` | `IT` | Direct match |
| `PL` | `PL` | Direct match |
| `RO` | `RO` | Direct match |
| `ROM` | `RO` | Legacy non-ISO Romania code; aliased |
| *(anything else)* | *flagged* | `unknown_country_code` quality flag; row excluded from metrics but visible in quality report |

---

## Frequency integrity

Annual World Bank values are **never** presented as 12 newly-measured monthly
values. Each observation keeps its native period label (`2022`, `2023`) and
`publication_lag_days`. The as-of join (`temporal_alignment.py`) matches each
annual value to the retention evaluation date where it was genuinely available.
The dashboard Trust → Methodology section exposes this rule explicitly.

---

## Indicator selection rationale

| Lens | Why included |
|---|---|
| **Labour supply** (unemployment, LFP) | A tighter labour market (low unemployment, high participation) makes it harder to retain — employees have more outside options |
| **Labour demand** (job vacancies) | A high vacancy rate signals competitor hiring pressure; Senior Leaders are often the most targeted |
| **Cost-of-living** (HICP) | Real-wage erosion increases exit risk independently of nominal pay levels |
| **Economic cycle** (GDP growth) | Macro expansion / contraction affects both hiring demand and retention willingness |

Two lenses (supply + demand) are the minimum required by the brief; this
build implements four.

---

## Known limitations

- Publication-lag values are documented estimates, not re-verified against
  official release calendars in this offline build.
- Only the six Asteria countries are requested; no broader European comparison
  is possible without extending `config.COUNTRIES`.
- Unemployment figures use seasonally-adjusted series (SA); if SA is
  unavailable for a future country, the adapter falls back to non-SA (NSA).
- `gdp_growth` and `labour_force_participation` are annual frequency and carry
  publication lags of 300–365 days, so they lag retention outcomes by
  approximately one year. This reduces their analytical power but is
  represented faithfully in the as-of join.
- The `hicp_inflation` dataset (`prc_hicp_manr`) has been discontinued by
  Eurostat as of May 2026 and replaced by `prc_hicp_minr`. The current code
  uses the old dataset; migration is a one-line change in `config.py`.
