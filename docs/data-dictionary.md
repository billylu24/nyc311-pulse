# Published artifact data dictionary

## Metadata

| Field | Meaning |
| --- | --- |
| `artifact_version` | Immutable release label for the aggregate artifact. |
| `window_start`, `window_end` | Inclusive request-created-date range in New York business time. |
| `extracted_at` | Reproducibility date recorded for the fixed snapshot. |
| `request_count` | Count of official source rows in the full window. |
| `readiness` | `validated` only if evaluation targets pass; otherwise `exploratory`. |
| `data_status`, `model_status` | Aggregate-integrity state and two-gate model release state. |
| `evaluation_protocol_version` | Version of the frozen split, generators, matching, and release gates. |
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
| `episode_start`, `episode_end` | Seven-day-cooldown alert episode boundary. |
| `upper_bound`, `excess_count`, `calibrated_score` | Prediction boundary and inspectable model evidence. |
| `model_version`, `detector` | Exact method responsible for the candidate. |

The public artifact contains no request ID, address, street, coordinate, resolution description, or other request-level record.
