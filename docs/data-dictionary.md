# Published artifact data dictionary

## Metadata

| Field | Meaning |
| --- | --- |
| `artifact_version` | Immutable release label for the aggregate artifact. |
| `window_start`, `window_end` | Inclusive request-created-date range in New York business time. |
| `extracted_at` | Reproducibility date recorded for the fixed snapshot. |
| `request_count` | Count of official source rows in the full window. |
| `readiness` | `validated` only if evaluation targets pass; otherwise `exploratory`. |
| `content_sha256` | Hash of canonical snapshot content before the self-referential field is added. |

## Signal

| Field | Meaning |
| --- | --- |
| `id` | Stable hash of type, district, problem, and detection window. |
| `type`, `severity`, `as_of` | Signal class, text severity, and detection date. |
| `district`, `borough`, `problem`, `agency` | Aggregate analytical dimensions. |
| `observed`, `expected`, `effect` | Observed metric, baseline estimate, and ratio. |
| `uncertainty`, `trigger`, `evidence` | Human-readable basis for inspection. |
| `data_quality_flags`, `limitation` | Data caveats and interpretation boundary. |
| `recommended_action` | Investigation step, never an automated operational decision. |

The public artifact contains no request ID, address, street, coordinate, resolution description, or other request-level record.
