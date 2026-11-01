# Preprocessing → ML contract

## RabbitMQ destination

The producer uses these environment variables:

```text
RABBITMQ_EXCHANGE=
RABBITMQ_ROUTING_KEY=preprocessing.combined_features
RABBITMQ_QUEUE=preprocessing.combined_features
```

An empty exchange means RabbitMQ's default exchange (`""`). The routing key
is therefore the queue name, preserving the current behavior. If an explicit
exchange is configured later, the producer declares it as a durable `topic`
exchange and binds the configured queue with the configured routing key.

## Payload

Each message is a UTF-8 JSON object containing exactly one row from
`combined_features.csv`, augmented with `analysis_id`: the backend Analysis
record UUID returned when the preprocessing job is created. The payload stays
flat, with all original CSV fields preserved. The UUID is shared by all rows
of that job and is not a RustFS storage path.

The backend creates the job and its queued Analysis in one transaction and
stores the UUID in the job's `parameters.analysis_id`, also exposed as a
top-level `analysis_id` in job responses. For service-authenticated creation,
the examination uploader is recorded as `requested_by`. Model metadata defaults
to `MockPredictor` / `0.1.0`; job creation accepts `model_name` and
`model_version` overrides. Existing jobs without an analysis UUID are not
backfilled.

ML uses this UUID in `POST /api/v1/internal/analyses/{analysis_id}/result`.
This does not introduce aggregation: multiple CSV rows still generate multiple
messages, while the backend currently accepts only one completed result per
analysis.

The strict versioned JSON Schema is in
`combined-features.v1.schema.json`:

- it declares 208 fields (207 CSV fields plus `analysis_id`);
- all 208 fields are required;
- `analysis_id` is a string with UUID format;
- `additionalProperties` is `false`, so an unknown field is invalid;
- numeric fields are JSON `number` values or `null`;
- identifier fields (`experiment_id`, `subject_id`, `recording_id`) are
  strings;
- index and counter fields are integers or `null`;
- validity/quality flags accept boolean values, numeric `0`/`1` values emitted
  by the current pandas CSV conversion, or `null`.

The schema contains only the three existing processing windows:
`baseline_*`, `early_*` and `sustained_*`. It does not define an additional
window or an envelope around the payload.

The fields are grouped in the schema as follows:

1. recording, event and cluster identifiers;
2. window boundaries, contamination flags and sample counts;
3. baseline spectral power, PAF, entropy and validity fields;
4. early-response spectral features and baseline-relative changes;
5. recording-level spectral features;
6. sustained-response spectral features and baseline-relative changes;
7. microstate metrics for classes `0`–`3`;
8. global and local network efficiency metrics for the alpha, beta, delta and
   theta bands.

`NaN`, positive/negative infinity and missing numeric values are transmitted as
JSON `null`. NumPy scalar values are converted to regular JSON numbers or
booleans.
