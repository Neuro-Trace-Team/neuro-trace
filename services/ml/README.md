# ML

## Backend result callback

The ML service submits completed predictions to
`POST /api/v1/internal/analyses/{analysis_id}/result` using a bearer service
token. Configure `BACKEND_URL` (defaults to `http://backend:8080`) and
`ML_SERVICE_TOKEN` (or `BACKEND_TOKEN`). The token must be signed with the
backend's `PREPROCESSING_SERVICE_JWT_SECRET` and contain `service: "ml"`,
`token_type: "service"`, and a valid `exp` claim.

Each RabbitMQ prediction event must include `analysis_id`, the UUID of the
backend analysis created together with the preprocessing job. Preprocessing
adds it to every CSV-row message. ML validates the UUID, excludes it from model
features, and uses it in the callback URL above (not as a RustFS path).

