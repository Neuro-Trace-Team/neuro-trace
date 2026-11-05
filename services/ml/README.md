# ML

## Development mode without trained weights

Set `ML_PREDICTOR=mock` to start the service with `MockPredictor`. It returns a
deterministic positive prediction and keeps `/healthz` and `/readyz` available,
so Docker and the message-flow infrastructure can be tested before the trained
`model.joblib` is delivered. Docker Compose defaults to this mode.

Set `ML_PREDICTOR=sklearn` for a real model. In that mode the service fails
fast if `MODEL_PATH` (default: `src/models/weights/model.joblib`) is absent or
invalid. Do not use `mock` to validate clinical predictions.

