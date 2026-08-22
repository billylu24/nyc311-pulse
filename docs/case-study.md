# NYC311 Pulse — Case study

## Problem

An operations analyst opening millions of 311 rows does not need another generic dashboard. They need a short, defensible queue: where did an observed pattern move outside its own history, what evidence triggered the alert, what is uncertain, and what should be checked next?

NYC311 Pulse implements that workflow as a fixed historical portfolio snapshot. The language is deliberately observational. A high request count can reflect reporting behavior, intake channels, duplicates, seasonality, category changes, real service conditions, or several factors at once.

## Product decision

The primary object is a `Signal`, not a request. A stable ID is derived from type, district, problem, and detection window. Ranking is deterministic: anomaly strength 50%, affected count 30%, persistence 20%. A map click, filter change, and browser navigation all update the same URL state.

## Data and privacy

The source window is 2024-08-01 through 2026-07-31, fixed at the 2026-08-21 extraction. The artifact records 7,498,437 requests. Request-level extraction is restricted to IDs, timestamps, organizational/category fields, status, district, and intake channel. The public artifact contains aggregates only.

Addresses, streets, coordinates, and free-text resolution fields are never extracted. The map uses 59 official Community District polygons. Joint Interest Areas and unspecified districts remain quality limitations but do not enter the mapped ranking.

## Detection method

For each district/problem series, the detector uses the preceding eight same-weekday observations:

`expected = median(history)`

`scale = max(1.4826 × MAD(history), 1)`

A candidate must pass minimum history, baseline volume, absolute delta, relative ratio, and robust-score gates. Median/MAD is less influenced by one historical spike than a mean/standard-deviation rule.

## Evaluation result

The checked-in artifact reports a deterministic injected-anomaly run with 60 labeled event-days across spike, level-shift, and gradual-increase scenarios. It achieved precision 0.036, recall 0.133, F1 0.057, 16.31 false alerts/week, and zero-day median delay for detected days. This misses the targets of F1 ≥ 0.75 and ≤ 10 false alerts/week.

The failure changes the product state: released signals are `watch`, readiness is `exploratory`, and no copy claims operational validation. The next iteration should tune on a separate validation split, broaden injected scenarios, and compare robust, seasonal-naïve, and Negative Binomial detectors on the same locked test labels.

## Engineering decisions

- A resilient Socrata client handles tokens, paging, exponential backoff, checkpoints, and typed validation.
- dbt builds request facts, daily metrics, closure cohorts, open-age inventory, and a quality mart.
- FastAPI serves a read-only artifact and structured 404, 422, and 503 envelopes.
- TypeScript API types are generated from FastAPI OpenAPI and checked in CI.
- The UI keeps a build-time snapshot fallback. An API failure changes status without removing the usable queue.
- MapLibre renders district aggregates only. Vega charts always ship an equivalent HTML table.

## Known limits and next work

The released aggregate snapshot evaluates the twelve highest-volume problem categories for signal generation; the total request count covers the full dataset. Closure-probability and aged-open code paths exist in analytical and dbt layers but are not promoted into public signals until cohort evaluation is complete. Cross-district differences must not be interpreted as agency quality because sample size and case mix differ.
