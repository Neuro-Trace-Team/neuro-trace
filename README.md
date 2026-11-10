# NeuroTrace

NeuroTrace stores pseudonymized EEG examinations in RustFS and coordinates
preprocessing and ML services. `medical_db` owns only patients, examinations,
and examination events. Preprocessing status and ML results remain owned by
their respective services.

Run locally:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

See [backend documentation](services/backend/README.md) for the API and
service contracts.
