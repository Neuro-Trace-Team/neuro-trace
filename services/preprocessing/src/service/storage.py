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

    def download_examination(self, examination: dict, destination: Path) -> None:
        """Download the recording described by the backend examination DTO.

        The backend DTO currently carries the RustFS prefix as ``study_id``.
        The additional aliases keep this adapter tolerant of the equivalent
        names used by older backend deployments; the EEG pipeline sees exactly
        the same local files as before.
        """
        study_id = next(
            (
                examination.get(key)
                for key in (
                    "study_id",
                    "storage_prefix",
                    "data_prefix",
                    "recording_prefix",
                    "storage_path",
                )
            ),
            None,
        )
        if not isinstance(study_id, str) or not study_id:
            raise ValueError("Examination response does not contain a storage prefix")
        self.download_study(study_id, destination)
