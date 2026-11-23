from __future__ import annotations

import subprocess
import sys
import threading
import fcntl
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from service.config import Settings
from service.rabbitmq import publish_combined_features
from service.storage import RustFSStorage


class BackendAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class NeuroTraceClient:
    """Small, dependency-free client for the NeuroTrace preprocessing API."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if self.settings.backend_token:
            headers["Authorization"] = f"Bearer {self.settings.backend_token}"
        request = Request(
            f"{self.settings.backend_url}{path}",
            data=json.dumps(payload).encode() if payload is not None else None,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self.settings.backend_timeout_seconds) as response:
                raw = response.read()
        except HTTPError as exc:
            body = exc.read().decode(errors="replace")[-2000:]
            raise BackendAPIError(
                f"Backend returned HTTP {exc.code}: {body}", exc.code
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise BackendAPIError(f"Cannot reach NeuroTrace backend: {exc}") from exc

        if not raw:
            return {}
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise BackendAPIError("Backend returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise BackendAPIError("Backend returned a JSON value instead of an object")
        return value

    def get_examination(self, examination_id: str) -> dict:
        return self._request(
            "GET", f"/api/v1/internal/preprocessing/examinations/{examination_id}"
        )

class JobConflictError(ValueError):
    """The examination already has an active preprocessing attempt."""


class JobManager:
    def __init__(self, settings: Settings, storage: RustFSStorage,
                 backend: NeuroTraceClient | None = None):
        self.settings = settings
        self.storage = storage
        self.backend = backend  # Retained for callers; inputs come from POST coordinates.
        self._lock = threading.RLock()
        self._leases = {}

    def _state_path(self, examination_id):
        return self.settings.work_root / 'jobs' / f'{uuid.UUID(examination_id)}.json'

    def _acquire(self, examination_id):
        path = self._state_path(examination_id).with_suffix('.lock')
        path.parent.mkdir(parents=True, exist_ok=True)
        lease = path.open('a')
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lease.close()
            raise JobConflictError('Preprocessing is already queued or running for this examination')
        return lease

    def _save(self, job):
        path = self._state_path(job['examination_id'])
        temporary = path.with_suffix(f'.{uuid.uuid4().hex}.tmp')
        temporary.write_text(json.dumps(job), encoding='utf-8')
        temporary.replace(path)

    def create(self, examination_id: str, *, storage_bucket=None, storage_key=None) -> str:
        try:
            examination_id = str(uuid.UUID(examination_id))
        except (ValueError, AttributeError, TypeError) as exc:
            raise ValueError('examination_id must be a UUID') from exc
        if storage_bucket is None or storage_key is None:
            raise ValueError('storage_bucket and storage_key must be provided together')
        if not isinstance(storage_bucket, str) or not storage_bucket.strip():
            raise ValueError('storage_bucket must not be blank')
        if not isinstance(storage_key, str) or not storage_key.strip():
            raise ValueError('storage_key must not be blank')
        if Path(storage_key).suffix.lower() not in {'.edf', '.bdf'}:
            raise ValueError('Only EDF and BDF EEG objects are supported')
        with self._lock:
            lease = self._acquire(examination_id)
            try:
                self._save(dict(examination_id=examination_id, status='QUEUED',
                    pipeline_version=self.settings.pipeline_version, created_at=self._now(),
                    attempt_id=uuid.uuid4().hex, storage_bucket=storage_bucket, storage_key=storage_key))
                self._leases[examination_id] = lease
            except Exception:
                lease.close()
                raise
        return examination_id

    def get(self, examination_id: str) -> dict | None:
        with self._lock:
            path = self._state_path(examination_id)
            if not path.is_file():
                return None
            job = json.loads(path.read_text(encoding='utf-8'))
            if job['status'] in {'QUEUED', 'RUNNING'} and examination_id not in self._leases:
                try:
                    lease = self._acquire(examination_id)
                except JobConflictError:
                    return job
                try:
                    # Reread after locking: the preceding worker may just have finished.
                    job = json.loads(path.read_text(encoding='utf-8'))
                    if job['status'] in {'QUEUED', 'RUNNING'}:
                        job.update(status='FAILED', finished_at=self._now(),
                                   error='Preprocessing interrupted before completion; submit again')
                        self._save(job)
                finally:
                    lease.close()
            return job

    def get_for_examination(self, examination_id):
        return self.get(examination_id)

    def _update(self, examination_id: str, **values):
        with self._lock:
            job = self.get(examination_id)
            job.update(values)
            self._save(job)

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    def run(self, examination_id: str):
        with self._lock:
            job = self.get(examination_id)
            if job is None or job['status'] != 'QUEUED' or examination_id not in self._leases:
                return
            self._update(examination_id, status='RUNNING', started_at=self._now())
        job_root = self.settings.work_root / examination_id / job['attempt_id']
        input_recording = job_root / 'input/study/subject/run'
        output_root = job_root / 'output'
        recording_output = output_root / 'study/subject/run'
        report_path = recording_output / 'preprocessing_report.json'
        report_key = f'preprocessing/{examination_id}/preprocessing_report.json'
        bucket = job['storage_bucket']
        try:
            self.storage.download_recording_inputs(bucket, job['storage_key'], input_recording)
            # Validate transport input without changing the pipeline's scientific logic.
            from eeg_pipeline.data_loader import _read_event_onsets
            if not _read_event_onsets(input_recording):
                raise ValueError('timestamps.json must contain at least one stimulus timestamp')
            completed = subprocess.run([
                sys.executable, '-m', 'eeg_pipeline.cli', '--input', str(job_root / 'input'),
                '--output', str(output_root), '--all', '--log-level', self.settings.pipeline_log_level,
            ], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=False,
                timeout=self.settings.pipeline_timeout_seconds)
            self._update(examination_id, pipeline_stdout=completed.stdout[-4000:])
            if report_path.is_file():
                self.storage.upload_result(report_path, bucket, report_key)
                self._update(examination_id, output_report_key=report_key)
            if completed.returncode:
                raise RuntimeError(f'Pipeline exited with code {completed.returncode}: {completed.stderr[-4000:]}')
            if not report_path.is_file():
                raise RuntimeError('Pipeline did not produce preprocessing_report.json')
            report = json.loads(report_path.read_text(encoding='utf-8'))
            if not isinstance(report, dict):
                raise ValueError('Pipeline report must be a JSON object')
            if report.get('preprocessing_status') != 'success':
                raise RuntimeError('Pipeline failed: ' + '; '.join(map(str, report.get('errors', []))))
            self._update(examination_id, data_quality_status=report.get('data_quality_status'),
                         warnings=report.get('warnings', []))
            csv_path = recording_output / 'combined_features.csv'
            from service.rabbitmq import _read_rows, validate_rows
            validate_rows(_read_rows(csv_path))
            output_key = f'preprocessing/{examination_id}/combined_features.csv'
            self.storage.upload_result(csv_path, bucket, output_key)
            published = publish_combined_features(self.settings, csv_path, examination_id=examination_id)
            self._update(examination_id, status='COMPLETED', finished_at=self._now(),
                         output_path=str(output_root), output_bucket=bucket, output_storage_key=output_key,
                         published_rows=published, rabbitmq_queue=self.settings.rabbitmq_queue)
        except Exception as exc:
            diagnostics = dict(preprocessing_status='failed', errors=[str(exc)],
                               examination_id=examination_id, attempt_id=job['attempt_id'])
            if report_path.is_file():
                try:
                    existing = json.loads(report_path.read_text(encoding='utf-8'))
                    if isinstance(existing, dict):
                        diagnostics = existing
                except (ValueError, OSError):
                    pass
            diagnostics.update(service_status='FAILED', service_error=str(exc))
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(diagnostics), encoding='utf-8')
            values = dict(status='FAILED', finished_at=self._now(), error=str(exc))
            try:
                self.storage.upload_result(report_path, bucket, report_key)
                values['output_report_key'] = report_key
            except Exception as upload_error:
                values['report_upload_error'] = str(upload_error)
            self._update(examination_id, **values)
        finally:
            with self._lock:
                lease = self._leases.pop(examination_id, None)
                if lease is not None:
                    lease.close()
