# NeuroTrace backend

Backend NeuroTrace is a FastAPI application. The current milestone provides
the application foundation, database readiness checks, and authentication.
Patients, examinations, RustFS uploads, preprocessing, and ML integrations
are intentionally not implemented yet.

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

The future HTTP resource name is **examinations**. New endpoints will use
`/api/v1/examinations`.

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

