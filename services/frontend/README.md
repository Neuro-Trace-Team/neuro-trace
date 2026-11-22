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

## Frontend tests

Run these commands from `services/frontend` after `npm ci`:

- `npm test` checks test TypeScript types and runs the component and integration tests once.
- `npm run test:typecheck` checks test TypeScript types without running the tests.
- `npm run test:watch` reruns tests during development.
- `npm run test:coverage` creates a coverage report in `coverage/index.html`.

The tests use Vitest, jsdom and React Testing Library. API responses are mocked with axios-mock-adapter, so the suite does not require a running backend. They cover authentication and route guards, API token handling, administrator and doctor workflows, settings, tables and dialogs. These tests do not replace browser end-to-end tests against a running backend; file downloads, browser layout and the full deployment integration require separate verification.
