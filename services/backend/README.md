# NeuroTrace backend

Backend NeuroTrace is a FastAPI application. The current milestone provides
authentication, pseudonymized patient and EEG-examination management, audit,
preprocessing and analysis state management, pain assessments, dashboards,
and bulk operations. Preprocessing and ML integrations themselves are
intentionally not implemented yet.

## Current functionality

- Configuration is read from environment variables with `pydantic-settings`.
- `auth_db`, `medical_db`, and `audit_db` have separate SQLAlchemy engines
  and session factories.
- ORM models mirror the existing SQL schema. They do not create or migrate
  database tables.
- `GET /health/live` confirms that the backend process is running.
- `GET /health/ready` checks all three databases and the configured RustFS
  bucket; it returns `503` when any dependency is unavailable.
- Access tokens are signed JWTs. Refresh tokens and password-reset tokens are
  opaque, cryptographically generated values stored only as SHA-256 hashes.
- Refreshing rotates the token; logout and a password change revoke sessions.
- Login, failed login, logout, password change, and password reset are
  appended to `audit_db` without exposing passwords or tokens.
- Role-based access control is centralised in `require_roles(...)`. The two
  accepted roles are `ADMIN` and `DOCTOR`; denied role checks create an
  `ACCESS_DENIED` audit record.
- Administrators can create, list, inspect, and update users. Any user can
  edit their own basic profile without being able to change their role.
- `audit_service.log(...)` is the central, best-effort audit writer. It
  resolves `type_id` from `audit_log_types` before adding a record.
- Audit metadata is filtered before persistence: passwords, JWTs, refresh and
  reset tokens, raw EEG data, and direct patient identifiers are omitted.
  An audit-database failure is logged by the application but never reverses a
  completed business operation.
- Administrators can inspect paginated audit logs, filtered by event, actor,
  or time range.
- Any authenticated `ADMIN` or `DOCTOR` can create and read pseudonymized
  patients. A patient contains only its generated UUID and timestamps because
  the medical schema contains no personal details.
- EEG upload writes the object to RustFS and its metadata to `medical_db`.
  Upload does not call or wait for preprocessing. A dedicated storage boundary
  keeps a future `PreprocessingService` separate from this transaction.
- The internal preprocessing contract exposes an active examination's RustFS
  object coordinates, metadata, channels, and events. It contains neither EEG
  bytes nor RustFS credentials, and does not perform an outbound request.
- Preprocessing jobs are persisted in `medical_db`. Creating a job changes an
  examination to `PREPROCESSING`; a completed result changes it to `READY`, a
  failure to `FAILED`, and cancellation back to `UPLOADED`. This is backend
  state management only: no preprocessing HTTP request, queue, or worker is
  started in this milestone.
- The analysis domain is persisted in `medical_db`: an analysis belongs to
  one completed preprocessing job, examination, requesting user, and declared
  model/version. It supports queued, running, completed, failed, and cancelled
  states plus one optional `analysis_result`. Public analysis/result endpoints
  and protected internal callback contracts are available; no ML call is made.
- Doctor and administrator dashboards aggregate existing data across the three
  databases. They do not require preprocessing or ML services to be running.
- Administrators can soft-delete up to 100 examinations in one operation or
  export their source EEG files and metadata as a generated ZIP archive.

The future HTTP resource name is **examinations**. New endpoints will use
`/api/v1/examinations`.

## Examination API

All endpoints require a logged-in `ADMIN` or `DOCTOR`. `POST` accepts
`multipart/form-data` with `patient_id`, `sampling_frequency`, and `file`.
Optional metadata fields are `examination_date`, `electrode_positions` (JSON
object encoded as text), `reference`, `power_line_frequency` (50 or 60), and
`duration_seconds`. The MVP accepts `.edf`, `.bdf`, `.set`, `.fif`, `.vhdr`,
and `.eeg` files and calculates their SHA-256 checksum while streaming them
to a temporary file before RustFS upload.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/api/v1/examinations` | Upload EEG to RustFS and persist metadata. |
| GET | `/api/v1/examinations` | Paginated list; filters: patient, uploader, status, creation date, EEG `channel`, and latest pain value from `doctor` or `ai`; safe sorting is available. |
| GET | `/api/v1/examinations/eeg-channels` | EEG channel catalogue. |
| GET | `/api/v1/examinations/{examination_id}` | Examination details. |
| PATCH | `/api/v1/examinations/{examination_id}` | Edit allowed metadata only. |
| DELETE | `/api/v1/examinations/{examination_id}` | Soft delete; the RustFS object is retained. |
| GET/PUT | `/api/v1/examinations/{examination_id}/channels` | Read or replace channel assignments. |
| GET/POST | `/api/v1/examinations/{examination_id}/events` | Read or add examination events. |
| PATCH/DELETE | `/api/v1/examinations/{examination_id}/events/{event_id}` | Edit or remove one event. |

The response deliberately does not expose `storage_bucket` or `storage_key`.
When RustFS cannot accept an upload, the API returns `503` and creates no
examination metadata. If metadata persistence fails after a RustFS upload,
the backend attempts to delete the uploaded object. Upload, metadata updates,
channel/event modifications, and soft delete create the matching examination
audit event without recording the file content.

## Internal preprocessing contract

| Method | Endpoint | Current access | Purpose |
| --- | --- | --- | --- |
| GET | `/api/v1/internal/preprocessing/examinations/{examination_id}` | ADMIN | Source-object coordinates and examination context for future preprocessing. |
| PATCH | `/api/v1/internal/preprocessing/jobs/{job_id}/status` | ADMIN | Mark a queued job as `RUNNING` or cancel an active job. |
| POST | `/api/v1/internal/preprocessing/jobs/{job_id}/result` | ADMIN | Save a `COMPLETED` output location or a `FAILED` error. |

The internal response includes `bucket`, `storage_key`, file information,
examination metadata, channels, and events. It intentionally excludes
`RUSTFS_ACCESS_KEY`, `RUSTFS_SECRET_KEY`, and file bytes. During this stage,
the endpoint is protected by existing administrator RBAC; a future
service-to-service authentication mechanism can replace this boundary without
changing the response contract. `DeferredPreprocessingClient` is only a
non-network integration placeholder and is not called by uploads.

## Preprocessing jobs API

All endpoints require a logged-in user. Creating a job stores a declared,
non-empty `pipeline_version` and optional JSON `parameters`; it does not send
anything to a preprocessing service. A terminal job cannot be transitioned
again. Completion requires both `output_bucket` and `output_storage_key`;
failure requires an `error_message`.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/api/v1/examinations/{examination_id}/preprocessing-jobs` | Queue a preprocessing job. |
| GET | `/api/v1/examinations/{examination_id}/preprocessing-jobs` | Paginated job history for an examination. |
| GET | `/api/v1/preprocessing-jobs/{job_id}` | Read one preprocessing job. |

## Analysis domain preparation

The backend service layer now persists and reads `analyses` and
`analysis_results`. An analysis can only be created for an active examination
and a `COMPLETED` preprocessing job belonging to that examination. It starts
as `QUEUED`; the service layer also protects the later `RUNNING`, `COMPLETED`,
`FAILED`, and `CANCELLED` transitions. Completion atomically stores one
optional result record with flexible JSON result and explanation fields.

`DeferredMLClient` is an explicit non-network integration placeholder; the
public result API and future ML callback contracts are documented below.

## Analysis and result API

All endpoints require a logged-in user. Requesting an analysis validates that
the examination exists and that the selected preprocessing job belongs to it
and is `COMPLETED`. The request only persists a `QUEUED` analysis; it does not
call ML. Completed results are returned only after the internal ML result
callback has saved them.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/api/v1/examinations/{examination_id}/results` | Queue analysis for a completed preprocessing job. |
| GET | `/api/v1/examinations/{examination_id}/results` | Paginated completed analysis results for an examination. |
| GET | `/api/v1/analyses` | Paginated analyses; filters: `examination_id`, `requested_by`, `analysis_status`. |
| GET | `/api/v1/analyses/{analysis_id}` | Analysis status and declared model/version. |

## Pain assessments API

Pain assessments are entered by a logged-in user and stored separately from
AI/ML `analysis_results`. The database permits any non-negative `pain_level`;
the API deliberately adds no arbitrary upper bound because the project has not
defined a universal pain scale. When `assessed_at` is omitted, the backend
uses the current UTC time.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/api/v1/examinations/{examination_id}/pain-assessments` | Record a clinician pain assessment. |
| GET | `/api/v1/examinations/{examination_id}/pain-assessments` | Paginated assessment history, newest first. |

## Internal ML contracts

The existing preprocessing internal contract remains unchanged. The following
temporary `ADMIN`-protected contracts are prepared for a future ML service;
they persist data in the backend but do not contact ML or a queue themselves.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| PATCH | `/api/v1/internal/analyses/{analysis_id}/status` | Mark a queued analysis `RUNNING` or cancel an active analysis. |
| POST | `/api/v1/internal/analyses/{analysis_id}/result` | Atomically store a completed analysis and its optional result fields. |
| POST | `/api/v1/internal/analyses/{analysis_id}/error` | Store a bounded failure message and set the analysis to `FAILED`. |

The result contract keeps `pain_level`, `confidence`, `result`, and
`explanation` optional and structurally flexible. No final ML output, feature,
tensor, or XAI schema is imposed. Completion and failure create the matching
central audit event; callback payloads never include source EEG data or
storage credentials.

## Dashboards and administrator statistics

`GET /api/v1/dashboard/stats` is available to every logged-in `ADMIN` or
`DOCTOR`. It returns global patient and active-examination totals, examination
counts by processing status, total/completed/failed analyses, and up to 10
most recently created active examinations. The current schema has no
facility/assignment boundary, so these values are global within the local
backend.

All administrator endpoints below accept `period=7d`, `30d`, or `90d` where
applicable. They combine `auth_db`, `medical_db`, and `audit_db` only in the
application layer; database sessions remain separate.

| Method | Endpoint | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/api/v1/dashboard/stats` | Logged-in user | Doctor-facing summary and recent examinations. |
| GET | `/api/v1/admin/dashboard?period=7d` | ADMIN | Users, logins, examinations, analyses, failures, and exports. |
| GET | `/api/v1/admin/stats/active-users?period=7d` | ADMIN | Unique users with a `LOGIN` audit event in the period. |
| GET | `/api/v1/admin/stats/login-attempts?period=7d` | ADMIN | Successful and failed login events in the period. |
| GET | `/api/v1/admin/stats/examinations?period=30d` | ADMIN | Active examinations created in the period. |
| GET | `/api/v1/admin/stats/exports?period=30d` | ADMIN | `DATA_EXPORTED` audit-event count in the period. |

## Bulk examination operations

Both operations accept JSON in the form
`{"examination_ids": ["uuid", "..."]}`. The list must contain 1–100 unique
UUIDs. The backend validates every requested examination before changing data.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/api/v1/examinations/bulk-delete` | ADMIN: soft-delete all selected active examinations; source files remain in RustFS. |
| POST | `/api/v1/examinations/bulk-export` | ADMIN or DOCTOR: download a ZIP containing each source EEG file and its `metadata.json`. |

The ZIP is generated in memory for the current MVP. An unavailable RustFS
object produces `503`; successful export writes one `DATA_EXPORTED` audit
event with only the exported examination count, never file bytes or storage
credentials.

## Patient API

| Method | Endpoint | Access | Purpose |
| --- | --- | --- | --- |
| POST | `/api/v1/patients` | Logged-in user | Create a pseudonymized patient. |
| GET | `/api/v1/patients` | Logged-in user | Paginated list; UUID search, creation date range, and safe sorting. |
| GET | `/api/v1/patients/stats` | Logged-in user | Patient and active-examination counts. |
| GET | `/api/v1/patients/{patient_id}` | Logged-in user | Pseudonymized patient details. |
| GET | `/api/v1/patients/{patient_id}/stats` | Logged-in user | Active examination count and first/last examination timestamps. |
| GET | `/api/v1/patients/{patient_id}/examinations` | Logged-in user | Active examinations for that patient. |

No name, surname, PESEL, address, e-mail, or any other personal identifier is
accepted, stored, or returned by this API. The patient responses deliberately
contain only `id`, `created_at`, and `updated_at`. Patient reads and creation
produce `PATIENT_ACCESSED` and `PATIENT_CREATED` audit events respectively.

## Authentication API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/api/v1/auth/login` | Sign in and receive access/refresh tokens. |
| POST | `/api/v1/auth/refresh` | Rotate a valid refresh token. |
| POST | `/api/v1/auth/logout` | Revoke the submitted refresh token. |
| GET | `/api/v1/auth/me` | Return the current authenticated user. |
| POST | `/api/v1/auth/change-password` | Change password and revoke active refresh tokens. |
| POST | `/api/v1/auth/forgot-password` | Create a reset request without exposing account existence. |
| POST | `/api/v1/auth/reset-password` | Consume a one-time reset token. |

Use `Authorization: Bearer <access_token>` for protected endpoints.

## User-management API

| Method | Endpoint | Access |
| --- | --- | --- |
| GET | `/api/v1/users` | ADMIN |
| POST | `/api/v1/users` | ADMIN |
| GET | `/api/v1/users/{user_id}` | ADMIN |
| PATCH | `/api/v1/users/{user_id}` | ADMIN |
| GET | `/api/v1/users/me` | Logged-in user |
| PATCH | `/api/v1/users/me` | Logged-in user |

An administrator cannot deactivate their own account or remove their own
administrator role through the API. Role changes and account deactivation
are recorded in the audit database.

## Audit API

| Method | Endpoint | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/api/v1/admin/audit-logs` | ADMIN | Paginated audit log list. |
| GET | `/api/v1/admin/audit-logs/{log_id}` | ADMIN | One audit record. |

Optional list filters are `event_code`, `user_id`, `date_from`, and `date_to`
(ISO 8601), plus `page`, `page_size` (maximum 100), `sort_by`, and
`sort_order`. A range where
`date_from` is after `date_to` returns `400`; no token returns `401`; a
non-administrator gets `403` and the denial is itself audited.

The event catalogue in `audit_log_types` includes: `LOGIN`,
`FAILED_LOGIN_ATTEMPT`, `LOGOUT`, `PASSWORD_CHANGED`, `PASSWORD_RESET`,
`ACCOUNT_CREATED`, `ACCOUNT_DEACTIVATED`, `ROLE_CHANGED`, `PATIENT_CREATED`,
`PATIENT_ACCESSED`, `EXAMINATION_UPLOADED`, `EXAMINATION_UPDATED`,
`EXAMINATION_DELETED`, `ANALYSIS_REQUESTED`, `ANALYSIS_COMPLETED`,
`ANALYSIS_FAILED`, `DATA_EXPORTED`, and `ACCESS_DENIED`. Events for future
patient, examination, and analysis operations will be emitted when those
operations are implemented.

Future protected endpoints use the central dependency, for example:

```python
@router.get("/admin-only")
def endpoint(user: Annotated[User, Depends(require_roles(Role.ADMIN))]):
    return {"user_id": user.id}
```

Password reset cannot yet be completed end-to-end: the project has no mail or
notification service to deliver the raw reset token. The token is generated
and stored securely, but a future notification adapter must send it to the
user; it must never be returned by the public API.

## Run with Docker Compose

From the repository root, create local environment settings once:

```powershell
Copy-Item .env.example .env
```

Set a long, locally unique `JWT_SECRET` in `.env`, then run:

```powershell
docker compose up --build backend
```

Compose starts `auth-db`, `medical-db`, `audit-db`, and `backend`. The
backend waits until all three databases pass their PostgreSQL health checks.

After the databases start, create the first administrator once. The command
refuses to run if `auth_db` already contains any user and reads the password
interactively instead of receiving it as a command-line argument:

```powershell
docker compose run --rm backend python -m src.scripts.bootstrap_admin `
  --email admin@example.local --first-name Admin --last-name Local
```

Verify it in a second terminal:

```powershell
Invoke-RestMethod http://localhost:8080/health/live
Invoke-RestMethod http://localhost:8080/health/ready
```

Stop the current stack with `docker compose down`.

## Run backend locally

Start only the databases:

```powershell
docker compose up -d auth-db medical-db audit-db
```

Then, from `services/backend`, provide the required settings and start
Uvicorn:

```powershell
$env:DB_AUTH_URL = "postgresql://postgres:postgres@localhost:5432/auth_db"
$env:DB_MEDICAL_URL = "postgresql://postgres:postgres@localhost:5433/medical_db"
$env:DB_AUDIT_URL = "postgresql://postgres:postgres@localhost:5434/audit_db"
$env:RUSTFS_ENDPOINT = "http://localhost:9000"
$env:RUSTFS_ACCESS_KEY = "local-placeholder"
$env:RUSTFS_SECRET_KEY = "local-placeholder"
$env:PREPROCESSING_URL = "http://localhost:8001"
$env:JWT_SECRET = "replace-this-with-a-long-local-development-secret"
..\..\.venv\Scripts\python -m uvicorn src.main:app --host 0.0.0.0 --port 8080
```

RustFS and preprocessing settings are required configuration now, but no
connection is made to either service during this milestone.

## Manual API checks with Postman

Import both files from the repository's `postman/` directory into Postman:

- `NeuroTrace Auth.postman_collection.json`
- `NeuroTrace Local.postman_environment.json`

Select **NeuroTrace Local** as the active environment and set
`admin_password` to the password entered for the bootstrap administrator.
Set `admin_password` to the bootstrap administrator password, then run the
**whole collection** with Collection Runner in its displayed order. Do not run
folders in parallel. Each business folder signs in again before it needs an
administrator token and creates its own patient/examination data, so a logout,
soft delete, or deactivated test doctor from an earlier folder cannot break a
later folder. Generated UUIDs and tokens are saved automatically.
The **User management (ADMIN)** folder then creates a distinct doctor account,
checks the administrator-only endpoints, and verifies that the doctor gets
`403` when attempting to list users. It deactivates the generated doctor at
the end and verifies that the account can no longer log in.

The **Audit (ADMIN)** folder signs in as the administrator, lists logs,
checks the `LOGIN` filter, opens one selected record, and checks the `401`
response for a request without a token. Run its requests in displayed order:
the list request saves `audit_log_id` for the detail request.

The **Patients** folder signs in as an administrator, creates a pseudonymized
patient, lists and searches by UUID, reads details and statistics, requests
the empty examination list, and verifies `404` for an unknown UUID and `401`
without authentication. It saves the new UUID as `patient_id`.

The **Examinations** folder signs in, creates its own pseudonymized patient,
uploads `postman/fixtures/sample.eeg`, checks filtering and details, updates
metadata, reads the channel catalogue, assigns channels, adds an event, and
finishes with a soft delete. In Postman, select that local fixture for the
`file` form field if the imported collection cannot resolve its relative path.

The **Preprocessing jobs** folder creates a separate patient and examination,
queues a job, verifies its history and detail endpoint, marks it `RUNNING`,
checks invalid completion input, then saves a `COMPLETED` result and verifies
that the examination becomes `READY`. It does not contact a preprocessing
service; internal job endpoints use the current temporary `ADMIN` boundary.

The **Analyses and results** folder creates a completed preprocessing job,
queues an analysis, simulates its internal result callback, and reads the
stored result. The **Pain assessments** folder creates an independent
clinician assessment, reads its history, and checks validation of a negative
value. The internal ML folder contains contract-level authentication and
unknown-analysis checks.

The final **Full API coverage additions** folder tests password-recovery/error
contracts, dashboards, statistics, newly added list filters and sorting, and
bulk export/delete. It intentionally runs last because bulk delete removes
the examination created by the pain-assessment scenario.

`forgot-password` has a successful automated check. A successful password
reset cannot be automated from Postman yet: the raw token is deliberately not
returned by the API and no mail adapter exists. The collection therefore tests
the invalid-token response for `reset-password` and the invalid-current-
password response for `change-password`, without changing the administrator
password.

