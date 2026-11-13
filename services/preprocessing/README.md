# EEG Pain Pipeline

An MNE/NumPy pipeline for EEG preprocessing and neurophysiological feature extraction. It accepts BioSemi `.bdf` files as EEG input. The analysis uses 19 channels:

```text
Fp1 Fp2 F7 F3 Fz F4 F8 T7 C3 Cz C4 T8 P7 P3 Pz P4 P8 O1 O2
```

The pipeline does not interpolate missing channels. A recording whose channels cannot be identified unambiguously is rejected.

## Installation and running

```bash
cd /home/marek/Projects/zpi-pipeline
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
```

## FastAPI HTTP service and RustFS

In addition to the CLI library, the project contains an HTTP service
(`src/main.py`). The service container starts the FastAPI application through
Uvicorn on port `8001`.

### Configuration

Configuration is read at startup from the following environment variables
(`src/service/config.py`):

| Variable | Default value | Meaning |
|---|---|---|
| `RUSTFS_ENDPOINT_URL` | `http://rustfs:9000` | RustFS S3 endpoint available in the Compose network |
| `RUSTFS_ACCESS_KEY_ID` | empty | S3 access key |
| `RUSTFS_SECRET_ACCESS_KEY` | empty | S3 secret key |
| `RUSTFS_BUCKET` | `eeg-data` | Bucket containing study data |
| `PREPROCESSING_WORK_ROOT` | `/tmp/preprocessing` | Working directory for individual jobs |
| `PIPELINE_LOG_LEVEL` | `INFO` | Pipeline log level |
| `RABBITMQ_URL` | `amqp://guest:guest@rabbitmq:5672/` | RabbitMQ connection URL |
| `RABBITMQ_QUEUE` | `preprocessing.combined_features` | Durable queue for combined feature rows |
| `BACKEND_URL` | `http://backend:8080` | NeuroTrace backend base URL |
| `BACKEND_TOKEN` | empty | Bearer token used for backend API calls |
| `BACKEND_TIMEOUT_SECONDS` | `10` | Backend request timeout |

The `RUSTFS_*` values must match the RustFS user configuration. When running
through `docker compose`, make sure that the variable names passed to the
container match the names read by `Settings.from_environment()`.

RustFS is accessed through its S3-compatible API. `RustFSStorage` creates a
boto3 client for the RustFS endpoint and enforces path-style addressing, so the
application does not require a RustFS-specific library.

### API

| Method | Endpoint | Action |
|---|---|---|
| `GET` | `/health` | Returns `{"status": "ok"}`; used by the container healthcheck |
| `GET` | `/health/connections` | Checks RustFS bucket access and RabbitMQ queue existence/access |
| `POST` | `/api/v1/examinations/{examination_id}/preprocessing` | Accepts backend upload coordinates and starts preprocessing |
| `GET` | `/api/v1/examinations/{examination_id}/preprocessing-status` | Returns the latest local status for an examination |

`GET http://preprocessing:8001/health/connections` is available within the
Compose network (the preprocessing port is not published to the host).
It returns HTTP 200 with `status: "ok"` when all probes succeed, or HTTP 503
with `status: "degraded"` otherwise. `connections` contains `rustfs` and
`rabbitmq`, each with `status` (`ok` or `error`), `latency_ms`,
and `error` (null or a sanitized error code).

Probes run concurrently with a three-second response deadline per dependency
and no retries. Blocking S3 calls run in worker threads with socket
timeouts; a timed-out worker may finish after the response deadline.
RustFS uses `head_bucket` on `RUSTFS_BUCKET`. RabbitMQ uses a passive
declaration of `RABBITMQ_QUEUE`, the same queue used by the publisher: it does
not create queues or publish messages. A missing queue reports
`queue_not_found`, including before its first creation by the publisher.
This probe does not verify publish permissions or routing.
The existing `/health` endpoint and pipeline behavior are unchanged.
| `POST` | `/api/v1/examinations/{examination_id}/preprocessing-jobs` | Starts preprocessing when the body includes the examination UUID and nonblank RustFS bucket and key |

The backend-compatible submission request contains the same examination UUID in
the URL and body, plus the exact RustFS object coordinates:

```json
{
  "examination_id": "00000000-0000-0000-0000-000000000001",
  "storage_bucket": "examinations",
  "storage_key": "examinations/patient/examination/recording.bdf"
}
```

The service downloads the EEG object directly from RustFS using the supplied
`storage_bucket` and `storage_key`, then downloads `timestamps.json` from the same
bucket and sibling object directory. For example, a key of
`examinations/patient/examination/raw_eeg.bdf` results in downloads of that key
and `examinations/patient/examination/timestamps.json`. The timestamps file is
saved locally as `events.json` for the pipeline. Backend uploads use the JSON
shape `{"timestamps": [0, 83456]}` (milliseconds).

Example preprocessing submission:

```bash
curl -X POST \
  http://localhost:8001/api/v1/examinations/00000000-0000-0000-0000-000000000001/preprocessing-jobs \
  -H 'Content-Type: application/json' \
  -d '{"examination_id":"00000000-0000-0000-0000-000000000001","storage_bucket":"examinations","storage_key":"examinations/patient/examination/recording.bdf"}'
```

The response is returned immediately with status `202 Accepted`:

```json
{
  "examination_id": "00000000-0000-0000-0000-000000000001",
  "status": "QUEUED"
}
```

The status can be checked by examination UUID at
`/api/v1/examinations/{examination_id}/preprocessing-status`.

### Job flow

The job execution process is as follows:

1. FastAPI receives a `POST` request containing `examination_id`,
   `storage_bucket`, and `storage_key`; it rejects missing or blank coordinates
   and checks that the body and URL examination UUIDs match.
2. `JobManager.create()` stores the supplied object coordinates and `QUEUED`
   state in process memory, keyed by examination UUID.
3. FastAPI adds `JobManager.run()` to `BackgroundTasks` and returns the
   examination UUID and current status.
4. Preprocessing downloads the EEG object and
   sibling `timestamps.json` from RustFS using `RustFSStorage.download_recording_inputs`,
   saving the latter locally as `events.json`.
   It does not fetch source-file coordinates from the backend.
5. Both files are stored in the pipeline's existing local input directory:

   ```text
   /tmp/preprocessing/<examination_id>/input/study/subject/run/
   ├── raw_eeg.bdf
   └── events.json
   ```

6. `JobManager` runs `python -m eeg_pipeline.cli` with the `--input`,
   `--output`, and `--all` parameters and the configured log level.
7. When processing finishes successfully, the service uploads the unchanged
   `combined_features.csv` to the supplied `storage_bucket`, using the object key
   `preprocessing/<examination_id>/combined_features.csv`.
   The configured S3 credentials need write access to that bucket.
8. Every CSV row is then published to RabbitMQ. Successful completion or
   failure is reflected in the local status endpoint. Missing output, missing
   bucket, upload, or publication errors result in `FAILED`. If publication
   fails after upload, the CSV remains in the bucket.

### RabbitMQ message identifiers

The backend supplies `examination_id` for the whole examination; it no longer
needs to supply `analysis_id`. The job response from the backend must contain
`examination_id` matching the requested examination. The existing POST endpoint
also accepts an optional JSON body `{"examination_id": "<uuid>"}`; when supplied,
it must match the examination UUID in the URL.

Each message contains these fields first, in this order:

```json
{
  "examination_id": "<examination UUID from backend>",
  "analysis_id": "<UUID generated by preprocessing for this CSV row>",
  "total_analyses_count": 2,
  "event_index": 0,
  "alpha_power": 0.42
}
```

`total_analyses_count` is the number of data rows in the output CSV (excluding
the header), identical in every message for that examination. It counts events
present in the output, not events discarded by the pipeline.

All remaining fields come from the CSV row. The service generates `analysis_id`
as UUIDv5 using the examination UUID and the zero-based CSV row position
(`combined_features:row:<index>`). Different rows have different IDs; publishing
the same CSV again for the same examination preserves them. This identity
assumes unchanged row order; it does not track events across reordered CSVs.
Identifiers are added only to broker messages, without modifying the pipeline
or the CSV uploaded to storage. CSV columns with these reserved names cannot
override the message identifiers. JSON consumers should use field names;
field order is a serialization convention.

Job state is stored only in process memory. Restarting the container removes
the job history, and background jobs do not constitute a durable queue.

### Required bucket contents

The bucket does not require special folders — the `study_id/` prefix is treated
as an S3 object directory. For a study named `study-001`, the minimal content
should look like this:

```text
eeg-data/
└── study-001/
    ├── eeg_data.bdf
    └── timestamps.json
```

`eeg_data.bdf` must be a BioSemi BDF file, and `timestamps.json` must contain a
JSON list of timestamps in milliseconds or an object wrapping that list under
`timestamps`. It is downloaded as `events.json`, as required by the pipeline
contract described below. Connecting
to RustFS only requires a valid endpoint, credentials, bucket name, and S3 read
permissions for the objects.

Full-dataset analysis:

```bash
python -m eeg_pipeline.cli \
  --input ~/EEG_Pain_Dataset \
  --output ~/EEG_Pain_Processed \
  --all
```

Analysis of one experiment or subject:

```bash
python -m eeg_pipeline.cli \
  --input ~/EEG_Pain_Dataset \
  --output ~/EEG_Pain_Processed \
  --experiment 1 \
  --subject sub-001
```

Event-based analysis uses configurable windows: `baseline=(-5.5,-0.5)`,
`early_response=(0,1)`, and `sustained_response=(0.5,5.5)` seconds. Windows are
calculated after resampling, and the output preserves one row per event
cluster. Windows outside the recording or overlapping with the next stimulus
are marked invalid/contaminated instead of being silently shortened.

## Input data

Preprocessing requires two files:

- one EEG file in BioSemi `.bdf` format;
- an `events.json` file containing event timestamps.

The files should be located in one recording directory. The pipeline does not
require additional parent directories such as `experiment`, `subject`, or
`task`. A minimal directory may look like this:

```text
recording/
├── eeg_data.bdf
└── events.json
```

`events.json` must contain a JSON list (or an object with a `timestamps` list)
of numeric event timestamps in
milliseconds from the beginning of the recording. The loader converts them to
seconds for preprocessing. List order determines `event_index` in the output;
invalid, non-finite, or negative values cause a recording-loading error.

```json
[7800, 121900]
```

If `events.json` is missing, no substitute events are created.
`configuration.json` is no longer a source of events or metadata required for
analysis.

## How the pipeline works

The main stages are implemented in the following files:

1. `eeg_pipeline/data_loader.py` searches for `.bdf` files, opens them with
   MNE, and reads the sampling frequency, channel names, and channel types from
   the BDF header. It also reads event onsets from `events.json`. Files such as
   `*_channels.tsv` are not used; channels must be described unambiguously in
   the BDF header.
2. `eeg_pipeline/preprocessing.py` selects the required 19 channels, applies
   the `standard_1020` montage, filters the signal, applies an average
   reference, optionally runs explicitly configured ICA, and resamples to
   256 Hz.
3. The same module extracts one epoch for each onset, from `onset + tmin` to
   `onset + tmax`. Epochs outside the recording boundaries or containing
   artifacts are rejected. No unrelated recording fragments are generated.
4. `eeg_pipeline/spectral_features.py`, `entropy.py`, `connectivity.py`,
   `microstates.py`, and `graph_features.py` calculate spectral features,
   entropy, dwPLI connectivity, microstates, and graph metrics for each
   accepted epoch.
5. `eeg_pipeline/feature_export.py` writes the results, while
   `feature_merge.py` creates the combined table.

The default preprocessing parameters are a `0.5–45 Hz` band-pass filter, a
`50 Hz` notch filter, resampling to `256 Hz`, and average reference. The
pipeline calculates, among other features, delta/theta/alpha/beta band power,
PAF, theta/alpha ratio, gamma, permutation entropy, dwPLI, microstates, and
graph features.

## Output data

For each processed recording, the pipeline writes the following output files:

```text
output/
├── features.csv
├── channel_features.csv
├── connectivity.npz
├── connectivity_dwpli.csv
├── microstates.csv
├── network_metrics.csv
├── combined_features.csv
└── preprocessing_report.json
```

`features.csv` contains one row per accepted epoch and feature averages across
the 19 channels. `channel_features.csv` contains channel-level features.
`connectivity.npz` stores connectivity matrices, `connectivity_dwpli.csv`
stores dwPLI connectivity values, `microstates.csv` stores microstate
features, `network_metrics.csv` stores network metrics,
`combined_features.csv` stores the combined modeling features, and
`preprocessing_report.json` stores the execution report with metadata, warnings,
and errors.

The existing column schema preserves fields such as `experiment_id`,
`subject_id`, `recording_id`, `window_id`, `event_index`, `event_time_s`,
`segment_start_s`, and `segment_end_s`. The `window_id` name remains part of
the output format for backward compatibility, but it identifies an event-based
epoch rather than an equal-length window. `event_time_s` contains the event
onset.

`preprocessing_report.json` contains the preprocessing parameters, source file,
metadata read by MNE from the BDF, the number of accepted and rejected epochs,
rejection reasons, warnings, and errors.

## Limitations

Randomized clustering operations use fixed seeds. Missing or incomplete data
required for preprocessing causes an error, and channels are not filled in.
Connectivity may contain `NaN` values when an epoch contains too little data.
The timestamp list does not specify event types or map them to pain ratings.
