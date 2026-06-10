"""
Google Cloud Storage bucket module for Nexus Cloud.

Author: Amina Jackson, Intechgambit
License: GPL-3.0
"""

from __future__ import annotations

from pathlib import Path
from typing import Union
from urllib.parse import urlparse

from nexus_cloud.storage.base import CloudStorage


class GcpBucketStorage(CloudStorage):
    """
    Read and upload objects in Google Cloud Storage.

    Credentials:
      - credentials_path: path to a service-account JSON key file
      - project_id (optional)

    bucket_path examples:
      - gs://my-bucket/prefix
      - my-bucket/prefix
    """

    def __init__(self, bucket_path: str, credentials: dict | None = None):
        super().__init__(bucket_path, credentials)
        self._bucket_name, self._prefix = self._parse_bucket_path(bucket_path)
        self._client = None

    @staticmethod
    def _parse_bucket_path(bucket_path: str) -> tuple[str, str]:
        if bucket_path.startswith("gs://"):
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
        return f"gs://{self._bucket_name}/{self._full_key(object_key)}"

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from google.cloud import storage
            from google.oauth2 import service_account
        except ImportError as exc:
            raise ImportError(
                "google-cloud-storage is required for GCP storage. "
                "Install with: pip install google-cloud-storage"
            ) from exc

        creds = self.credentials
        credentials_path = creds.get("credentials_path")
        if credentials_path:
            credentials = service_account.Credentials.from_service_account_file(credentials_path)
            project = creds.get("project_id") or credentials.project_id
            self._client = storage.Client(project=project, credentials=credentials)
        else:
            self._client = storage.Client(project=creds.get("project_id"))
        return self._client

    def read(self, object_key: str, local_path: Union[str, Path]) -> Path:
        destination = Path(local_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        bucket = self._get_client().bucket(self._bucket_name)
        blob = bucket.blob(self._full_key(object_key))
        blob.download_to_filename(str(destination))
        return destination

    def upload(self, local_path: Union[str, Path], object_key: str) -> str:
        source = Path(local_path)
        if not source.is_file():
            raise FileNotFoundError(f"Local file not found: {source}")
        bucket = self._get_client().bucket(self._bucket_name)
        blob = bucket.blob(self._full_key(object_key))
        blob.upload_from_filename(str(source))
        return self._remote_uri(object_key)
