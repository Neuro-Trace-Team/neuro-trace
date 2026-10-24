from __future__ import annotations

import re
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from service.config import Settings
from service.rabbitmq import publish_combined_features
from service.storage import RustFSStorage


_STUDY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class JobManager:
    def __init__(self, settings: Settings, storage: RustFSStorage):
        self.settings = settings
        self.storage = storage
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def create(self, study_id: str) -> str:
        if not _STUDY_ID.fullmatch(study_id):
            raise ValueError("study_id contains unsupported characters")
        job_id = str(uuid.uuid4())
        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id,
                "study_id": study_id,
                "status": "queued",
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

    def run(self, job_id: str, study_id: str) -> None:
        job_root = self.settings.work_root / job_id
        input_recording = job_root / "input" / "study" / "subject" / "run"
        output_root = job_root / "output"
        self._update(job_id, status="running", started_at=self._now())
        try:
            self.storage.download_study(study_id, input_recording)
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
                status="completed",
                finished_at=self._now(),
                output_path=str(output_root),
                pipeline_stdout=completed.stdout[-4000:],
                published_rows=published_rows,
                rabbitmq_queue=self.settings.rabbitmq_queue,
            )
        except Exception as exc:
            self._update(job_id, status="failed", finished_at=self._now(), error=str(exc))
