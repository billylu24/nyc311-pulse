# Architecture

## Runtime paths

1. The public frontend serves a versioned, privacy-minimized JSON artifact at build time.
2. With `NEXT_PUBLIC_API_BASE_URL`, the client checks FastAPI before using the verified artifact.
3. If the check fails, TanStack Query preserves initial server data and announces cached status.
4. FastAPI reads the same artifact from disk and never opens it for writes.

## Monorepo layout

- `app/`, `components/`, `lib/`: product UI and generated API contract.
- `api/`: FastAPI routes, models, and artifact loader.
- `analytics/`: contracts, extraction, survival analysis, signal logic, and backtesting.
- `dbt/`: staging and analytical marts.
- `scripts/`: aggregate artifact and OpenAPI generation.
- `public/data/`: snapshot, 59-district GeoJSON, and SHA-256 manifest.
- `tests/`: unit, contract, data, accessibility, and browser workflow checks.

## Deployment boundary

The Sites/Cloudflare worker hosts the frontend and static fallback without persistence. `vercel.json` defines an optional independent FastAPI deployment. The API artifact is bundled read-only; a missing artifact produces HTTP 503. V1 requires no identity, mutation, scheduled refresh, or database write.
