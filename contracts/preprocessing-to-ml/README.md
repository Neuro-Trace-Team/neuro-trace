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

Each message is a flat UTF-8 JSON object containing one row from
`combined_features.csv`, augmented with:

- `examination_id`: the examination UUID, shared by all rows;
- `total_analyses_count`: the total number of rows in that CSV, shared by all
  messages in the publication.

`analysis_id` is not generated or transmitted by preprocessing. ML is responsible
for managing analysis identifiers internally. If the CSV contains `analysis_id`,
the publisher removes it. CSV values of `examination_id` and
`total_analyses_count` are replaced with the publication metadata above.
All other CSV fields are preserved, with no envelope or publication timestamp.

Example (feature fields abbreviated; this is not a complete schema-valid payload):

```json
{
  "examination_id": "86b0602a-1452-440b-aeef-6c6c39fdf29b",
  "total_analyses_count": 2,
  "experiment_id": "study",
  "subject_id": "subject",
  "recording_id": "run",
  "window_id": 0,
  "event_id": 1,
  "baseline_absolute_alpha_power": 0.42
}
```

The strict versioned JSON Schema is in
`combined-features.v1.schema.json`:

- it declares 209 required fields (207 CSV fields plus the two metadata fields);
- `examination_id` is a string with UUID format;
- `total_analyses_count` is an integer greater than or equal to 1;
- `additionalProperties` is `false`, so unknown fields, including `analysis_id`,
  are invalid;
- numeric fields are JSON `number` values or `null`;
- identifier fields (`experiment_id`, `subject_id`, `recording_id`) are strings;
- index and counter types are specified individually by the schema;
- validity/quality flags accept booleans, numbers (including the `0`/`1` values
  emitted by pandas CSV conversion), or `null`.

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
