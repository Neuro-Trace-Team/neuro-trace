# NeuroTrace backend

The FastAPI backend owns authentication, audit, pseudonymized patient and
examination metadata, and original EEG objects in RustFS. It has separate
connections to `auth_db`, `medical_db`, and `audit_db`.

`medical_db` contains only `patients`, `examinations`, and
`examination_events`. It deliberately contains no preprocessing jobs, channel
catalogue, pain assessments, analyses, or ML results.

## Examination API

All endpoints below require an access token.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/api/v1/examinations` | Upload an EEG, persist its RustFS coordinates, then request preprocessing. |
| GET | `/api/v1/examinations` | List active examinations. |
| GET/PATCH/DELETE | `/api/v1/examinations/{id}` | Read details with ML analyses when ready, edit the examination date, or soft-delete. |
| GET/POST | `/api/v1/examinations/{id}/events` | Read or create event segments. |
| PATCH/DELETE | `/api/v1/examinations/{id}/events/{event_id}` | Edit or remove an event. |
| GET | `/api/v1/examinations/{id}/preprocessing-status` | Proxy the status maintained by preprocessing. |
| GET | `/api/v1/examinations/{id}/results` | Read ML results only after the examination is ready. |

The upload request is one `multipart/form-data` transaction. Send `file` and
exactly one of `patient_id` or `generate_patient=true`; optional `events` is a
JSON array such as
`[{"timestamp":"00:01:05:250000","type":"ARTIFACT"}]`. Timestamp format
is `HH:MM:SS:microseconds`. The backend validates the file and events before it
creates a generated patient, then commits the patient, examination and events
together. The backend sends preprocessing:

```json
{"examination_id":"uuid","storage_bucket":"examinations","storage_key":"examinations/..."}
```

It calls `POST {PREPROCESSING_URL}/api/v1/examinations/{examination_id}/preprocessing`.
Status is read from `GET .../{examination_id}/preprocessing-status`.

New examinations have `status: PROCESSING`. ML publishes the durable RabbitMQ
event below to `RABBITMQ_COMPLETED_ANALYSIS_QUEUE` when all analyses for one
examination have been persisted:

```json
{"event_type":"examination_completed","examination_id":"uuid","total_analyses_count":3}
```

The backend consumer changes the matching non-deleted examination to
`status: READY`. `GET /api/v1/examinations/{id}` always returns the status and
returns an empty `analyses` list while processing. When ready, it reads ML
analyses and includes them in the examination details. The list endpoint does
not call ML. `GET /api/v1/examinations/{id}/results` returns `409` until ready.

For a ready examination, results are read from
`GET {ML_URL}/api/v1/examinations/{examination_id}/analyses` and must be:

```json
{"examination_id":"uuid","analyses":[{"analysis_id":7,"result":6.4,"confidence":0.91}]}
```

The ML contract currently has no timestamp field. The backend therefore does
not invent one; add `timestamp` to every ML analysis before the frontend needs
time-axis rendering.

The backend persists only the examination readiness status, not ML analyses.
For an existing `medical_db`, apply
`database/medical/migrations/001_add_examination_status.sql`; a fresh Compose
volume receives the column from `database/medical/init.sql`.

## Tests

Run unit and API-contract tests from `services/backend` with:

```powershell
python -m pytest
```

The suite validates the medical SQL contract, the OpenAPI surface, HTTP client
contracts, and the RabbitMQ completion-event consumer. Full tests against
PostgreSQL and RustFS require a fresh Compose volume because the schema
intentionally removed tables from the previous architecture.
