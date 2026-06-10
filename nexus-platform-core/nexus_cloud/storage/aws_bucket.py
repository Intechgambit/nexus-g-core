"""
AWS S3 bucket storage for Nexus Cloud.

Author: Amina Jackson, Intechgambit
License: GPL-3.0
"""

from __future__ import annotations

from pathlib import Path
from typing import Union
from urllib.parse import urlparse

from nexus_cloud.storage.base import CloudStorage


class AwsBucketStorage(CloudStorage):
    """
    Read and upload objects in Amazon S3.

    Credentials (all optional if using ambient IAM / profile):
      - aws_access_key_id
      - aws_secret_access_key
      - aws_session_token
      - region_name
      - profile_name

    bucket_path examples:
      - s3://my-bucket/prefix
      - my-bucket/prefix
    """

    def __init__(self, bucket_path: str, credentials: dict | None = None):
        super().__init__(bucket_path, credentials)
        self._bucket, self._prefix = self._parse_bucket_path(bucket_path)
        self._client = None

    @staticmethod
    def _parse_bucket_path(bucket_path: str) -> tuple[str, str]:
        if bucket_path.startswith("s3://"):
            parsed = urlparse(bucket_path)
            bucket = parsed.netloc
            prefix = parsed.path.lstrip("/")
        else:
            parts = bucket_path.split("/", 1)
            bucket = parts[0]
            prefix = parts[1] if len(parts) > 1 else ""
        return bucket, prefix.rstrip("/")

    def _full_key(self, object_key: str) -> str:
        key = object_key.lstrip("/")
        if self._prefix:
            return f"{self._prefix}/{key}".lstrip("/")
        return key

    def _remote_uri(self, object_key: str) -> str:
        return f"s3://{self._bucket}/{self._full_key(object_key)}"

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            import boto3
        except ImportError as exc:
            raise ImportError(
                "boto3 is required for AWS storage. Install with: pip install boto3"
            ) from exc

        creds = self.credentials
        session_kwargs = {}
        if creds.get("profile_name"):
            session_kwargs["profile_name"] = creds["profile_name"]
        if creds.get("region_name"):
            session_kwargs["region_name"] = creds["region_name"]

        session = boto3.Session(**session_kwargs)
        client_kwargs = {}
        for key in ("aws_access_key_id", "aws_secret_access_key", "aws_session_token", "region_name"):
            if creds.get(key):
                client_kwargs[key] = creds[key]

        self._client = session.client("s3", **client_kwargs)
        return self._client

    def read(self, object_key: str, local_path: Union[str, Path]) -> Path:
        destination = Path(local_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._get_client().download_file(self._bucket, self._full_key(object_key), str(destination))
        return destination

    def upload(self, local_path: Union[str, Path], object_key: str) -> str:
        source = Path(local_path)
        if not source.is_file():
            raise FileNotFoundError(f"Local file not found: {source}")
        self._get_client().upload_file(str(source), self._bucket, self._full_key(object_key))
        return self._remote_uri(object_key)
