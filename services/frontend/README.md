# NeuroTrace frontend

The frontend calls the backend API under `/api/v1`. Vite proxies `/api` and
`/health` to `http://localhost:8080` by default, so browser requests do not
need direct cross-origin access to FastAPI. Docker Compose sets
`BACKEND_URL=http://backend:8080` for the same proxy.

Set `BACKEND_URL` for the Vite process to use a different proxy target. For a
direct browser connection, set `VITE_BACKEND_URL` to the backend origin and
configure the backend to allow the frontend's origin via CORS.

The Vite development server listens on port `3000`; start the app at
`http://localhost:3000`.
