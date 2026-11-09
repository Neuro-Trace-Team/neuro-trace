# NeuroTrace backend

The FastAPI backend owns authentication, audit, pseudonymized patient and
examination metadata, and original EEG objects in RustFS. It has separate
connections to `auth_db`, `medical_db`, and `audit_db`.

`medical_db` contains only `patients`, `examinations`, and
`examination_events`, plus the per-doctor navigation tables `recent_patients`
and `recent_examinations`. It deliberately contains no preprocessing jobs, channel
catalogue, pain assessments, analyses, or ML results.

## Examination API

All endpoints below require an access token.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/api/v1/examinations` | Upload an EEG, persist its RustFS coordinates, then request preprocessing. |
| GET | `/api/v1/examinations` | List active examinations. |
| GET | `/api/v1/examinations/statuses` | List backend-owned examination lifecycle values for the frontend. |
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

`examinations.status` is the PostgreSQL enum `examination_status`. New
examinations have `status: PREPROCESSING`; the backend keeps that state while
the preprocessing request and downstream ML work are pending. ML publishes the durable RabbitMQ
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

The frontend obtains the allowed values from `GET /api/v1/examinations/statuses`:

```json
{"statuses":["PREPROCESSING","READY"]}
```

The frontend must not create its own values. To introduce a future state, add it
to `ExaminationStatus` and deliver a migration with `ALTER TYPE
examination_status ADD VALUE ...`; the endpoint will then expose it automatically.

## List filtering, sorting, and pagination

All list endpoints use `page` (starting at `1`), `page_size` (from `1` to
`100`), `sort_by`, and `sort_order` (`asc` or `desc`). Exact field filters are
combined with `AND`; `query` is a case-insensitive partial search.

- `GET /api/v1/examinations`: `query` searches `id` and `patient_id`; filters
  are `id`, `patient_id`, `uploaded_by`, `status`, `examination_date_from`, and
  `examination_date_to`.
- `GET /api/v1/users`: `query` searches `first_name`, `last_name`, and `email`;
  filters are `id`, `email`, `first_name`, `last_name`, `role`, and `is_active`.
- `GET /api/v1/admin/audit-logs`: `query` searches `id`, `user_id`, and
  `ip_address`; filters are `id`, `user_id`, `type_id`, `created_at_from`,
  `created_at_to`, `ip_address`, `request_id`, `resource_type`, and
  `resource_id`. The legacy exact `event_code` filter remains supported.

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
`database/medical/migrations/001_add_examination_status.sql` followed by
`database/medical/migrations/003_replace_examination_status_with_enum.sql` and
`database/medical/migrations/004_rename_finished_status_to_ready.sql`; a
fresh Compose volume receives the enum and column from `database/medical/init.sql`.

## Recently visited resources

For a doctor, `GET /api/v1/patients/{id}` and
`GET /api/v1/examinations/{id}` record a visit. The backend stores at most ten
unique patient entries and ten unique examination entries per doctor. Revisiting
a resource moves it to the beginning. Doctors can read their own history with:

| Method | Endpoint |
| --- | --- |
| GET | `/api/v1/me/recent/patients` |
| GET | `/api/v1/me/recent/examinations` |

These endpoints are restricted to the `DOCTOR` role and return resources in
descending `last_visited_at` order. Existing medical databases require
`database/medical/migrations/002_add_recent_resources.sql`.

## Tests

Run unit and API-contract tests from `services/backend` with:

```powershell
python -m pytest
```

The suite validates the medical SQL contract, the OpenAPI surface, HTTP client
contracts, and the RabbitMQ completion-event consumer. Full tests against
PostgreSQL and RustFS require a fresh Compose volume because the schema
intentionally removed tables from the previous architecture.
