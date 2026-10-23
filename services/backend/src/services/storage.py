import logging
from typing import BinaryIO

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from src.config import get_settings

logger = logging.getLogger(__name__)


class ObjectStorageError(Exception):
    pass


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
