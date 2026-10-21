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
| `POST` | `/api/v1/internal/preprocessing/studies/{study_id}` | Creates a job and starts preprocessing in the background |
| `GET` | `/api/v1/internal/preprocessing/jobs/{job_id}` | Returns the current job status |

Example job submission:

```bash
curl -X POST \
  http://localhost:8001/api/v1/internal/preprocessing/studies/study-001
```

The response is returned immediately with status `202 Accepted`:

```json
{
  "job_id": "<uuid>",
  "study_id": "study-001",
  "status": "queued"
}
```

The job status can be checked with:

```bash
curl http://localhost:8001/api/v1/internal/preprocessing/jobs/<job_id>
```

`study_id` may contain letters, digits, dots, underscores, and hyphens. An
invalid identifier returns `400`; an unknown `job_id` returns `404`.

### Job flow

The job execution process is as follows:

1. FastAPI receives a `POST` request containing `study_id`.
2. `JobManager.create()` validates the identifier, generates a job UUID, and
   stores the `queued` state in process memory.
3. FastAPI adds `JobManager.run()` to `BackgroundTasks` and returns the job
   identifier to the client.
4. The job changes to `running`. `RustFSStorage.download_study()` downloads
   two objects from the selected bucket:
   `{bucket}/{study_id}/events.csv` and `{bucket}/{study_id}/eeg_data.bdf`.
5. The files are stored locally in the job directory:

   ```text
   /tmp/preprocessing/<job_id>/input/study/subject/run/
   ├── events.csv
   └── eeg_data.bdf
   ```

6. `JobManager` runs `python -m eeg_pipeline.cli` with the `--input`,
   `--output`, and `--all` parameters and the configured log level.
7. When processing finishes successfully, the state changes to `completed`
   and the output is stored in `/tmp/preprocessing/<job_id>/output`. A download
   or pipeline error changes the state to `failed` and stores the error message.

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
    └── events.csv
```

`eeg_data.bdf` must be a BioSemi BDF file, and `events.csv` must contain an
`onset` column, as required by the pipeline contract described below. Connecting
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
- an `events.csv` file containing event timestamps.

The files should be located in one recording directory. The pipeline does not
require additional parent directories such as `experiment`, `subject`, or
`task`. A minimal directory may look like this:

```text
recording/
├── eeg_data.bdf
└── events.csv
```

`events.csv` must contain an `onset` column. Its values are event times in
seconds from the beginning of the recording. Other columns are ignored. Row
order determines `event_index` in the output; empty onset values are skipped,
while invalid or negative values cause a recording-loading error.

```csv
onset,event_type
7.8,stimulus
121.9,stimulus
```

If `events.csv` or its `onset` column is missing, no substitute events are
created. `configuration.json` is no longer a source of events or metadata
required for analysis.

## How the pipeline works

The main stages are implemented in the following files:

1. `eeg_pipeline/data_loader.py` searches for `.bdf` files, opens them with
   MNE, and reads the sampling frequency, channel names, and channel types from
   the BDF header. It also reads event onsets from `events.csv`. Files such as
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
The event type in additional `events.csv` columns is not interpreted and is not
automatically mapped to pain ratings.
