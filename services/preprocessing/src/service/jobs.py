from __future__ import annotations

import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from service.config import Settings
from service.backend import NeuroTraceClient
from service.rabbitmq import publish_combined_features
from service.storage import RustFSStorage


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
        self._lock = threading.Lock()

    def create(self, examination_id: str, job_id: str | None = None) -> str:
        try:
            examination_uuid = uuid.UUID(examination_id)
        except (ValueError, AttributeError, TypeError) as exc:
            raise ValueError("examination_id must be a UUID") from exc
        requested_job_id = job_id or str(uuid.uuid4())
        try:
            uuid.UUID(requested_job_id)
        except (ValueError, AttributeError, TypeError) as exc:
            raise ValueError("job_id must be a UUID") from exc
        job_id = str(requested_job_id)
        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id,
                "examination_id": str(examination_uuid),
                "status": "QUEUED",
                "created_at": self._now(),
            }
        return job_id

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def _update(self, job_id: str, **values) -> None:
        with self._lock:
            self._jobs[job_id].update(values)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def run(self, job_id: str, examination_id: str) -> None:
        job_root = self.settings.work_root / job_id
        input_recording = job_root / "input" / "study" / "subject" / "run"
        output_root = job_root / "output"
        self._update(job_id, status="RUNNING", started_at=self._now())
        try:
            if self.backend is None:
                raise RuntimeError("NeuroTrace backend client is not configured")
            backend_job = self.backend.get_job(job_id)
            if backend_job.get("status") == "CANCELLED":
                self._update(job_id, status="CANCELLED", finished_at=self._now())
                self.backend.update_status(job_id, "CANCELLED")
                return
            self.backend.update_status(job_id, "RUNNING")
            examination = self.backend.get_examination(examination_id)
            self.storage.download_examination(examination, input_recording)
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
            published_rows = publish_combined_features(
                self.settings, combined_features_path
            )
            self._update(
                job_id,
                status="COMPLETED",
                finished_at=self._now(),
                output_path=str(output_root),
                pipeline_stdout=completed.stdout[-4000:],
                published_rows=published_rows,
                rabbitmq_queue=self.settings.rabbitmq_queue,
            )
            self.backend.submit_result(
                job_id, "COMPLETED", result_file_location=str(output_root)
            )
        except Exception as exc:
            message = str(exc)
            self._update(job_id, status="FAILED", finished_at=self._now(), error=message)
            try:
                if self.backend is not None:
                    self.backend.submit_result(job_id, "FAILED", error_message=message)
            except Exception as callback_error:
                self._update(job_id, backend_error=str(callback_error))
