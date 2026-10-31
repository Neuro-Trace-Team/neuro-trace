# ML

## Backend result callback

The ML service submits completed predictions to
`POST /api/v1/internal/analyses/{analysis_id}/result` using a bearer service
token. Configure `BACKEND_URL` (defaults to `http://backend:8080`) and
`ML_SERVICE_TOKEN` (or `BACKEND_TOKEN`). The token must be signed with the
backend's `PREPROCESSING_SERVICE_JWT_SECRET` and contain `service: "ml"`,
`token_type: "service"`, and a valid `exp` claim.

Each RabbitMQ prediction event must include `analysis_id`. The currently
documented preprocessing message contract does not include that identifier, so
the producer must provide it before results can be associated with a backend
analysis.

