from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    rustfs_endpoint_url: str
    rustfs_access_key_id: str
    rustfs_secret_access_key: str
    rustfs_bucket: str
    work_root: Path
    pipeline_log_level: str = "INFO"

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            rustfs_endpoint_url=os.getenv("RUSTFS_ENDPOINT_URL", "http://rustfs:9000"),
            rustfs_access_key_id=os.getenv("RUSTFS_ACCESS_KEY_ID", ""),
            rustfs_secret_access_key=os.getenv("RUSTFS_SECRET_ACCESS_KEY", ""),
            rustfs_bucket=os.getenv("RUSTFS_BUCKET", "eeg-data"),
            work_root=Path(os.getenv("PREPROCESSING_WORK_ROOT", "/tmp/preprocessing")),
            pipeline_log_level=os.getenv("PIPELINE_LOG_LEVEL", "INFO"),
        )
