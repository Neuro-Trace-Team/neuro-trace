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
| GET/PATCH/DELETE | `/api/v1/examinations/{id}` | Read, edit the examination date, or soft-delete. |
| GET/POST | `/api/v1/examinations/{id}/events` | Read or create event segments. |
| PATCH/DELETE | `/api/v1/examinations/{id}/events/{event_id}` | Edit or remove an event. |
| GET | `/api/v1/examinations/{id}/preprocessing-status` | Proxy the status maintained by preprocessing. |
| GET | `/api/v1/examinations/{id}/results` | Proxy the per-event ML results. |

The upload request is `multipart/form-data`: `patient_id`, `file`, and optional
`examination_date`. The backend sends preprocessing:

```json
{"examination_id":"uuid","storage_bucket":"examinations","storage_key":"examinations/..."}
```

It calls `POST {PREPROCESSING_URL}/api/v1/examinations/{examination_id}/preprocessing`.
Status is read from `GET .../{examination_id}/preprocessing-status`.

ML results are read from
`GET {ML_URL}/api/v1/examinations/{examination_id}/results` and must be:

```json
{"examination_id":"uuid","analyses":[{"analysis_id":"uuid","result":6.4,"confidence":0.91}]}
```

No preprocessing or ML response is persisted by the backend. Audit events
include `PREPROCESSING_REQUESTED`, `PREPROCESSING_STARTED`,
`PREPROCESSING_COMPLETED`, and `PREPROCESSING_FAILED`.

## Tests

Run unit and API-contract tests from `services/backend` with:

```powershell
python -m pytest
```

The test suite validates the medical SQL contract, the OpenAPI surface, and
the backend HTTP clients with mocked preprocessing/ML transports. Full tests
against PostgreSQL and RustFS require a fresh Compose volume because the
schema intentionally removed tables from the previous architecture.
