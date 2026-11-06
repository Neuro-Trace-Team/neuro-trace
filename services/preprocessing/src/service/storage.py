from __future__ import annotations

from pathlib import Path
from posixpath import dirname, join

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

    def download_study(self, study_id: str, destination: Path, bucket: str | None = None) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        client = self._client()
        source_bucket = bucket or self.settings.rustfs_bucket
        for filename in ("events.csv", "eeg_data.bdf"):
            # The public contract is bucket/{study_id}/{filename}.
            client.download_file(
                source_bucket,
                f"{study_id}/{filename}",
                str(destination / filename),
            )

    def download_object(self, bucket: str, storage_key: str, destination: Path) -> Path:
        """Download exactly one RustFS object using the supplied S3 coordinates."""
        if not isinstance(bucket, str) or not bucket.strip():
            raise ValueError("storage_bucket must not be blank")
        if not isinstance(storage_key, str) or not storage_key.strip():
            raise ValueError("storage_key must not be blank")
        filename = Path(storage_key).name
        if not filename:
            raise ValueError("storage_key must identify an object")
        destination.mkdir(parents=True, exist_ok=True)
        local_path = destination / filename
        self._client().download_file(bucket, storage_key, str(local_path))
        return local_path

    def download_recording_inputs(
        self, bucket: str, storage_key: str, destination: Path
    ) -> tuple[Path, Path]:
        """Download the EEG object and its sibling events.csv from RustFS."""
        if not isinstance(bucket, str) or not bucket.strip():
            raise ValueError("storage_bucket must not be blank")
        if not isinstance(storage_key, str) or not storage_key.strip():
            raise ValueError("storage_key must not be blank")
        filename = storage_key.rsplit("/", 1)[-1]
        if not filename:
            raise ValueError("storage_key must identify an object")

        event_key = join(dirname(storage_key), "events.csv")
        if event_key == storage_key:
            raise ValueError("storage_key must identify the EEG object, not events.csv")

        destination.mkdir(parents=True, exist_ok=True)
        eeg_path = destination / filename
        events_path = destination / "events.csv"
        client = self._client()
        client.download_file(bucket, storage_key, str(eeg_path))
        client.download_file(bucket, event_key, str(events_path))
        return eeg_path, events_path

    def upload_result(self, csv_path: Path, bucket: str, storage_key: str) -> None:
        """Upload the pipeline output unchanged to backend-provided storage."""
        if not csv_path.is_file():
            raise FileNotFoundError(f"Combined features file not found: {csv_path}")
        if not isinstance(bucket, str) or not bucket.strip():
            raise ValueError("Examination response does not contain a storage bucket")
        self._client().upload_file(str(csv_path), bucket, storage_key)

    def download_examination(self, examination: dict, destination: Path) -> None:
        """Download the recording described by the backend examination DTO.

        The backend DTO currently carries the RustFS prefix as ``study_id``.
        The additional aliases keep this adapter tolerant of the equivalent
        names used by older backend deployments; the EEG pipeline sees exactly
        the same local files as before.
        """
        source_file = examination.get("source_file")
        storage_key = source_file.get("storage_key") if isinstance(source_file, dict) else None
        bucket = source_file.get("bucket") if isinstance(source_file, dict) else None
        if not isinstance(storage_key, str) or not storage_key:
            raise ValueError("Examination response does not contain a storage prefix")
        study_id = storage_key.rsplit("/", 1)[0] if "/" in storage_key else ""
        if not study_id:
            raise ValueError("Examination response does not contain a storage prefix")
        self.download_study(study_id, destination, bucket=bucket)
