# NeuroTrace

NeuroTrace is a microservice project for storing EEG examinations,
preprocessing their data, and presenting AI/ML analysis results.

## Implemented milestone: backend foundation and authentication

The backend currently starts with FastAPI and connects independently to the
three PostgreSQL databases: `auth_db`, `medical_db`, and `audit_db`.

Available technical endpoints:

- `GET /health/live` — backend process is alive.
- `GET /health/ready` — all three PostgreSQL databases accept `SELECT 1`.

Authentication and administrator-only user management are implemented.
Patients, examination upload, RustFS, preprocessing, and ML functionality
remain for separate, small milestones.

The backend uses central RBAC support for `ADMIN` and `DOCTOR`. User
management is restricted to `ADMIN`; users may only edit their own basic
profile.

## Naming convention

The project uses **examination/examinations** consistently in backend code
and all new API routes. The planned resource path is
`/api/v1/examinations`; do not introduce the former naming convention.

## Run the current milestone

```powershell
Copy-Item .env.example .env
docker compose up --build backend
```

Set a strong local `JWT_SECRET` in `.env` before starting. Then verify:

```powershell
Invoke-RestMethod http://localhost:8080/health/live
Invoke-RestMethod http://localhost:8080/health/ready
```

For detailed backend configuration and a local (non-Docker) start, see
[`services/backend/README.md`](services/backend/README.md).
