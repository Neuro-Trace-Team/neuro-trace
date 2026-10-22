# NeuroTrace backend

Backend NeuroTrace is a FastAPI application. The current milestone provides
the application foundation and database readiness checks; authentication,
patients, examinations, RustFS uploads, preprocessing, and ML integrations
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

The future HTTP resource name is **examinations**. New endpoints will use
`/api/v1/examinations`, never `/api/v1/studies`.

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

