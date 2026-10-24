from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote


@dataclass(frozen=True)
class Settings:
    rustfs_endpoint_url: str
    rustfs_access_key_id: str
    rustfs_secret_access_key: str
    rustfs_bucket: str
    work_root: Path
    pipeline_log_level: str = "INFO"
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"
    rabbitmq_queue: str = "preprocessing.combined_features"

    @classmethod
    def from_environment(cls) -> "Settings":
        rabbitmq_user = os.getenv("RABBITMQ_USER", "guest")
        rabbitmq_password = os.getenv("RABBITMQ_PASSWORD", "guest")
        rabbitmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq")
        rabbitmq_port = os.getenv("RABBITMQ_PORT", "5672")
        return cls(
            rustfs_endpoint_url=os.getenv("RUSTFS_ENDPOINT", "http://rustfs:9000"),
            rustfs_access_key_id=os.getenv("RUSTFS_ACCESS_KEY", ""),
            rustfs_secret_access_key=os.getenv("RUSTFS_SECRET_KEY", ""),
            rustfs_bucket=os.getenv("RUSTFS_BUCKET", "eeg-data"),
            work_root=Path(os.getenv("PREPROCESSING_WORK_ROOT", "/tmp/preprocessing")),
            pipeline_log_level=os.getenv("PIPELINE_LOG_LEVEL", "INFO"),
            rabbitmq_url=(
                "amqp://"
                f"{quote(rabbitmq_user, safe='')}:{quote(rabbitmq_password, safe='')}"
                f"@{rabbitmq_host}:{rabbitmq_port}/"
            ),
            rabbitmq_queue=os.getenv(
                "RABBITMQ_QUEUE", "preprocessing.combined_features"
            ),
        )
