import logging
from dataclasses import dataclass
from typing import BinaryIO

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from src.config import get_settings

logger = logging.getLogger(__name__)


class ObjectStorageError(Exception):
    pass


@dataclass(frozen=True)
class StorageUsage:
    bucket: str
    bucket_exists: bool
    object_count: int
    used_bytes: int


class RustFSStorage:
    """Object-storage boundary; a future upload workflow can reuse this unchanged."""

    def __init__(self) -> None:
        settings = get_settings()
        self.bucket = settings.rustfs_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.rustfs_endpoint,
            aws_access_key_id=settings.rustfs_access_key,
            aws_secret_access_key=settings.rustfs_secret_key,
            region_name="us-east-1",
            config=Config(s3={"addressing_style": "path"}),
        )

    def _ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError as error:
            status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status != 404:
                raise ObjectStorageError("RustFS bucket is unavailable") from error
            try:
                self.client.create_bucket(Bucket=self.bucket)
            except (BotoCoreError, ClientError) as create_error:
                raise ObjectStorageError("RustFS bucket could not be created") from create_error
        except BotoCoreError as error:
            raise ObjectStorageError("RustFS is unavailable") from error

    def check_available(self) -> None:
        """Check RustFS connectivity without requiring a bucket created by the first upload."""
        try:
            self.client.list_buckets()
        except (BotoCoreError, ClientError) as error:
            raise ObjectStorageError("RustFS is unavailable") from error

    def usage(self) -> StorageUsage:
        """Return live usage of the backend-owned RustFS bucket.

        S3-compatible APIs do not expose the RustFS host filesystem capacity,
        so this deliberately reports only the application bucket's objects and
        total stored bytes.
        """
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError as error:
            status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status == 404:
                return StorageUsage(self.bucket, False, 0, 0)
            raise ObjectStorageError("RustFS bucket is unavailable") from error
        except BotoCoreError as error:
            raise ObjectStorageError("RustFS is unavailable") from error

        object_count = 0
        used_bytes = 0
        continuation_token: str | None = None
        try:
            while True:
                arguments = {"Bucket": self.bucket}
                if continuation_token is not None:
                    arguments["ContinuationToken"] = continuation_token
                page = self.client.list_objects_v2(**arguments)
                for item in page.get("Contents", []):
                    object_count += 1
                    used_bytes += int(item["Size"])
                if not page.get("IsTruncated"):
                    break
                continuation_token = page.get("NextContinuationToken")
                if not continuation_token:
                    raise ObjectStorageError("RustFS returned an invalid object listing")
        except (BotoCoreError, ClientError, KeyError, TypeError, ValueError) as error:
            raise ObjectStorageError("RustFS usage could not be read") from error
        return StorageUsage(self.bucket, True, object_count, used_bytes)

    def upload(self, source: BinaryIO, *, key: str, content_type: str | None) -> None:
        self._ensure_bucket()
        try:
            extra_args = {"ContentType": content_type} if content_type else None
            self.client.upload_fileobj(source, self.bucket, key, ExtraArgs=extra_args)
        except (BotoCoreError, ClientError) as error:
            raise ObjectStorageError("File upload to RustFS failed") from error

    def delete(self, *, key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except (BotoCoreError, ClientError):
            logger.exception("Could not compensate RustFS object upload for key %s", key)

    def download(self, *, bucket: str, key: str) -> bytes:
        try:
            response = self.client.get_object(Bucket=bucket, Key=key)
            return response["Body"].read()
        except (BotoCoreError, ClientError) as error:
            raise ObjectStorageError("File download from RustFS failed") from error
