from __future__ import annotations

import subprocess
import sys
import threading
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

class JobManager:
    def __init__(
        self,
        settings: Settings,
        storage: RustFSStorage,
        backend: NeuroTraceClient | None = None,
    ):
        self.settings = settings
        self.storage = storage
        self.backend = backend
        self._jobs: dict[str, dict] = {}
        self._storage_coordinates: dict[str, tuple[str | None, str | None]] = {}
        self._lock = threading.Lock()

    def create(
        self,
        examination_id: str,
        *,
        storage_bucket: str | None = None,
        storage_key: str | None = None,
    ) -> str:
        try:
            examination_uuid = uuid.UUID(examination_id)
        except (ValueError, AttributeError, TypeError) as exc:
            raise ValueError("examination_id must be a UUID") from exc
        examination_id = str(examination_uuid)
        if storage_bucket is None or storage_key is None:
            raise ValueError("storage_bucket and storage_key must be provided together")
        if not storage_bucket.strip():
            raise ValueError("storage_bucket must not be blank")
        if not storage_key.strip():
            raise ValueError("storage_key must not be blank")
        with self._lock:
            self._jobs[examination_id] = {
                "examination_id": examination_id,
                "status": "QUEUED",
                "pipeline_version": self.settings.pipeline_version,
                "created_at": self._now(),
            }
            self._storage_coordinates[examination_id] = (storage_bucket, storage_key)
        return examination_id

    def get(self, examination_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(examination_id)
            return dict(job) if job else None

    def get_for_examination(self, examination_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(examination_id)
            return dict(job) if job else None

    def _get_storage_coordinates(self, examination_id: str) -> tuple[str | None, str | None]:
        with self._lock:
            return self._storage_coordinates.get(examination_id, (None, None))

    def _update(self, examination_id: str, **values) -> None:
        with self._lock:
            self._jobs[examination_id].update(values)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def run(self, examination_id: str) -> None:
        job_root = self.settings.work_root / examination_id
        input_recording = job_root / "input" / "study" / "subject" / "run"
        output_root = job_root / "output"
        self._update(examination_id, status="RUNNING", started_at=self._now())
        try:
            if self.backend is None:
                raise RuntimeError("NeuroTrace backend client is not configured")
            storage_bucket, storage_key = self._get_storage_coordinates(examination_id)
            self.storage.download_recording_inputs(
                storage_bucket, storage_key, input_recording
            )
            output_bucket = storage_bucket
            command = [
                sys.executable,
                "-m",
                "eeg_pipeline.cli",
                "--input",
                str(job_root / "input"),
                "--output",
                str(output_root),
                "--all",
                "--log-level",
                self.settings.pipeline_log_level,
            ]
            completed = subprocess.run(
                command,
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode:
                raise RuntimeError(
                    f"Pipeline exited with code {completed.returncode}: "
                    f"{completed.stderr[-4000:]}"
                )
            combined_features_path = (
                output_root / "study" / "subject" / "run" / "combined_features.csv"
            )
            if not isinstance(output_bucket, str) or not output_bucket.strip():
                raise ValueError("Examination response does not contain a storage bucket")
            output_storage_key = (
                f"preprocessing/{examination_id}/combined_features.csv"
            )
            self.storage.upload_result(
                combined_features_path, output_bucket, output_storage_key
            )
            published_rows = publish_combined_features(
                self.settings, combined_features_path, examination_id=examination_id
            )
            self._update(
                examination_id,
                status="COMPLETED",
                finished_at=self._now(),
                output_path=str(output_root),
                output_bucket=output_bucket,
                output_storage_key=output_storage_key,
                pipeline_stdout=completed.stdout[-4000:],
                published_rows=published_rows,
                rabbitmq_queue=self.settings.rabbitmq_queue,
            )
        except Exception as exc:
            message = str(exc)
            self._update(examination_id, status="FAILED", finished_at=self._now(), error=message)
