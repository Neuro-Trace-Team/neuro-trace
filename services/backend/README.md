# NeuroTrace backend

Backend NeuroTrace is a FastAPI application. The current milestone provides
the application foundation, database readiness checks, and authentication.
Examination upload, RustFS uploads, preprocessing, and ML integrations are
intentionally not implemented yet. This milestone additionally makes the
audit trail centrally readable for administrators and provides pseudonymized
patient management.

## Current functionality

- Configuration is read from environment variables with `pydantic-settings`.
- `auth_db`, `medical_db`, and `audit_db` have separate SQLAlchemy engines
  and session factories.
- ORM models mirror the existing SQL schema. They do not create or migrate
  database tables.
- `GET /health/live` confirms that the backend process is running.
- `GET /health/ready` runs `SELECT 1` against each of the three databases;
  it returns `503` when any database is unavailable.
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

The future HTTP resource name is **examinations**. New endpoints will use
`/api/v1/examinations`.

## Patient API

| Method | Endpoint | Access | Purpose |
| --- | --- | --- | --- |
| POST | `/api/v1/patients` | Logged-in user | Create a pseudonymized patient. |
| GET | `/api/v1/patients` | Logged-in user | Paginated list; `search` filters a UUID or UUID fragment. |
| GET | `/api/v1/patients/stats` | Logged-in user | Patient and active-examination counts. |
| GET | `/api/v1/patients/{patient_id}` | Logged-in user | Pseudonymized patient details. |
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
(ISO 8601), plus `page` and `page_size` (maximum 100). A range where
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
Run requests in this order: **Live**, **Ready**, **Login**, **Current user**,
**Refresh token rotation**, **Logout**, then **Refresh after logout is
rejected**. The collection saves access and refresh tokens automatically.
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

