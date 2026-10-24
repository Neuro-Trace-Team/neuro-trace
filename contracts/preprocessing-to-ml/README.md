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
`combined_features.csv`. The payload is flat: it has no envelope, generated
message identifier, publication timestamp, or other added metadata. Existing
fields such as `experiment_id`, `event_id` and `event_timestamp` are retained
because they already belong to the CSV row; no new fields were added by the
contract.

The strict versioned JSON Schema is in
`combined-features.v1.schema.json`:

- it declares all 207 fields currently present in the payload;
- all 207 fields are required;
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
