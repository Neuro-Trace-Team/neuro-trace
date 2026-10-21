from __future__ import annotations

from pathlib import Path

from service.config import Settings


class RustFSStorage:
    """Small S3-compatible client. RustFS is addressed through its S3 API."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def _client(self):
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise RuntimeError("RustFS support requires boto3") from exc

        return boto3.client(
            "s3",
            endpoint_url=self.settings.rustfs_endpoint_url,
            aws_access_key_id=self.settings.rustfs_access_key_id,
            aws_secret_access_key=self.settings.rustfs_secret_access_key,
            config=Config(s3={"addressing_style": "path"}),
        )

    def download_study(self, study_id: str, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        client = self._client()
        for filename in ("events.csv", "eeg_data.bdf"):
            # The public contract is bucket/{study_id}/{filename}.
            client.download_file(
                self.settings.rustfs_bucket,
                f"{study_id}/{filename}",
                str(destination / filename),
            )
