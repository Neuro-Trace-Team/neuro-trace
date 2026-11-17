from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote


@dataclass(frozen=True)
class Settings:
    backend_url: str
    backend_token: str
    backend_timeout_seconds: float
    rustfs_endpoint_url: str
    rustfs_access_key_id: str
    rustfs_secret_access_key: str
    rustfs_bucket: str
    work_root: Path
    pipeline_version: str = "0.1.0"
    pipeline_log_level: str = "INFO"
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"
    rabbitmq_exchange: str = ""
    rabbitmq_routing_key: str = "preprocessing.combined_features"
    rabbitmq_queue: str = "preprocessing.combined_features"

    @classmethod
    def from_environment(cls) -> "Settings":
        rabbitmq_user = os.getenv("RABBITMQ_USER", "guest")
        rabbitmq_password = os.getenv("RABBITMQ_PASSWORD", "guest")
        rabbitmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq")
        rabbitmq_port = os.getenv("RABBITMQ_PORT", "5672")
        configured_rabbitmq_url = os.getenv("RABBITMQ_URL")
        rabbitmq_url = configured_rabbitmq_url or (
            "amqp://"
            f"{quote(rabbitmq_user, safe='')}:{quote(rabbitmq_password, safe='')}"
            f"@{rabbitmq_host}:{rabbitmq_port}/"
        )
        return cls(
            backend_url=os.getenv("BACKEND_URL", "http://backend:8080").rstrip("/"),
            backend_token=os.getenv("BACKEND_TOKEN", ""),
            backend_timeout_seconds=float(os.getenv("BACKEND_TIMEOUT_SECONDS", "10")),
            rustfs_endpoint_url=os.getenv("RUSTFS_ENDPOINT", "http://rustfs:9000"),
            rustfs_access_key_id=os.getenv("RUSTFS_ACCESS_KEY", ""),
            rustfs_secret_access_key=os.getenv("RUSTFS_SECRET_KEY", ""),
            rustfs_bucket=os.getenv("RUSTFS_BUCKET", "eeg-data"),
            work_root=Path(os.getenv("PREPROCESSING_WORK_ROOT", "/tmp/preprocessing")),
            pipeline_version=os.getenv("PIPELINE_VERSION", "0.1.0"),
            pipeline_log_level=os.getenv("PIPELINE_LOG_LEVEL", "INFO"),
            rabbitmq_url=rabbitmq_url,
            rabbitmq_exchange=os.getenv("RABBITMQ_EXCHANGE", ""),
            rabbitmq_routing_key=os.getenv(
                "RABBITMQ_ROUTING_KEY", "preprocessing.combined_features"
            ),
            rabbitmq_queue=os.getenv(
                "RABBITMQ_QUEUE", "preprocessing.combined_features"
            ),
        )
