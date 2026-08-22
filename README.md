# NYC311 Pulse

**Evidence-first anomaly triage for New York City service operations.** NYC311 Pulse turns a fixed, reproducible snapshot of official 311 data into a public alert queue, Community District map, and inspectable signal evidence. It is a portfolio case study—not a live operations product and not an agency scorecard.

> [Live demo](https://nyc311-pulse.giaok.chatgpt.site) · [Case study](docs/case-study.md) · [OpenAPI contract](public/openapi.json)

![NYC311 Pulse alert queue](public/screenshots/dashboard.png)

## What a reviewer can verify in 30 seconds

- **Real scope:** 7,498,437 official requests created from 2024-08-01 through 2026-07-31; extracted on 2026-08-21.
- **Complete aggregates:** 436,266 district/problem/day rows span the declared window, paginate across nine Socrata pages, and reconcile to 4,502,830 selected-category requests.
- **Locked evaluation:** the selected 26-week Negative Binomial detector achieved F1 = 0.823, 4.45 false episodes/week, and zero-day median delay on 1,200 independently seeded events.
- **Two release gates:** the synthetic gate passed; all public candidates remain `research_flag` until the 60-case blind real-history review reaches Precision@20 ≥ 0.65.
- **Privacy by design:** no address, street, coordinates, resolution text, or raw complaint endpoint is present.
- **Accessible fallback:** charts have equivalent tables, the map has a 59-district button interface, and the static snapshot remains usable if the API is unavailable.

## Stack

| Layer | Technology |
| --- | --- |
| Product UI | Next.js-compatible vinext, React 19, strict TypeScript, TanStack Query, MapLibre GL, Vega-Lite |
| API | FastAPI, Pydantic, generated OpenAPI TypeScript types |
| Analytics | Python, pandas, NumPy, Kaplan–Meier utilities, deterministic injection tests |
| Warehouse | DuckDB, dbt-duckdb, quarantines and schema tests |
| Delivery | OpenAI Sites/Cloudflare worker frontend, optional Vercel FastAPI project, GitHub Actions |
| Quality | Vitest, Testing Library, Playwright, axe, pytest, Ruff, Pyright, ESLint |

## Local development

Requirements: Node.js 22+ and Python 3.11+ (CI targets Python 3.13).

```bash
npm install
python -m venv .venv
.venv/Scripts/python -m pip install -e . --group dev
npm run dev
```

Useful checks:

```bash
npm run typecheck
npm run lint
npm test
npm run build
.venv/Scripts/python -m pytest
.venv/Scripts/ruff check analytics api scripts tests/python
.venv/Scripts/pyright
.venv/Scripts/dbt build --profiles-dir dbt
```

Generate the fixed artifact and API contract:

```bash
.venv/Scripts/python scripts/build_snapshot.py
npm run openapi:generate
```

The request-level extractor in `analytics/socrata.py` supports an app token, pagination, retries, checkpoints, and Pydantic validation. Raw pages belong under ignored `.cache/` or `data/raw/` paths. The public builder uses Socrata server-side aggregates so the demo can be reproduced without publishing millions of request rows.

## Architecture

```mermaid
flowchart LR
  S[NYC Open Data] --> E[Restricted-field extractor]
  E --> Q[Contracts + quarantine]
  Q --> D[DuckDB + dbt marts]
  D --> A[Deterministic analytics]
  A --> P[Versioned aggregate artifact]
  P --> F[FastAPI read-only API]
  P --> C[Build-time cached snapshot]
  F --> W[Product UI]
  C --> W
```

The API exposes aggregate metadata, dimensions, signals, trends, district values, and quality results only. See [architecture.md](docs/architecture.md) and [data-dictionary.md](docs/data-dictionary.md).

## Product boundaries

This project reports observed patterns. It does not infer resident need, agency efficiency, service quality, or causation. `due_date` is excluded because coverage is insufficient for a defensible citywide SLA measure. Joint Interest Areas and `Unspecified` remain in quality analysis but are excluded from the 59-district map ranking.

The fixed snapshot and volume-surge workflow are implemented end to end. The analytical modules also include right-censored closure estimation and dbt closure/open-age marts, but the public model scope is volume only. Synthetic validation does not promote the product by itself: real-history review is still pending and the UI therefore uses research language throughout.

Sources: [NYC Open Data 311 Service Requests](https://data.cityofnewyork.us/resource/erm2-nwe9) and [Community District boundaries](https://data.cityofnewyork.us/City-Government/Community-Districts/5crt-au7u). NYC311 Pulse is an independent portfolio project and is not affiliated with the City of New York.
