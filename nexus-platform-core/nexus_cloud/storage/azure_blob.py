"""
Azure Blob Storage module for Nexus Cloud.

Author: Amina Jackson, Intechgambit
License: GPL-3.0
"""

from __future__ import annotations

from pathlib import Path
from typing import Union
from urllib.parse import urlparse

from nexus_cloud.storage.base import CloudStorage


class AzureBlobStorage(CloudStorage):
    """
    Read and upload objects in Azure Blob Storage.

    Credentials (provide one of):
      - connection_string
      - account_name + account_key

    bucket_path examples:
      - https://account.blob.core.windows.net/container/prefix
      - container/prefix
    """

    def __init__(self, bucket_path: str, credentials: dict | None = None):
        super().__init__(bucket_path, credentials)
        self._container, self._prefix = self._parse_bucket_path(bucket_path)
        self._account_url = self._resolve_account_url()
        self._client = None

    @staticmethod
    def _parse_bucket_path(bucket_path: str) -> tuple[str, str]:
        if bucket_path.startswith("http://") or bucket_path.startswith("https://"):
            parsed = urlparse(bucket_path)
            parts = parsed.path.lstrip("/").split("/", 1)
            container = parts[0]
            prefix = parts[1] if len(parts) > 1 else ""
            return container, prefix.rstrip("/")
        parts = bucket_path.split("/", 1)
        container = parts[0]
        prefix = parts[1] if len(parts) > 1 else ""
        return container, prefix.rstrip("/")

    def _resolve_account_url(self) -> str | None:
        creds = self.credentials
        if creds.get("account_url"):
            return creds["account_url"].rstrip("/")
        account_name = creds.get("account_name")
        if account_name:
            return f"https://{account_name}.blob.core.windows.net"
        if self.bucket_path.startswith("http://") or self.bucket_path.startswith("https://"):
            parsed = urlparse(self.bucket_path)
            return f"{parsed.scheme}://{parsed.netloc}"
        return None

    def _full_key(self, object_key: str) -> str:
        key = object_key.lstrip("/")
        if self._prefix:
            return f"{self._prefix}/{key}".lstrip("/")
        return key

    def _remote_uri(self, object_key: str) -> str:
        base = self._account_url or "https://<account>.blob.core.windows.net"
        return f"{base}/{self._container}/{self._full_key(object_key)}"

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from azure.storage.blob import BlobServiceClient
        except ImportError as exc:
            raise ImportError(
                "azure-storage-blob is required for Azure storage. "
                "Install with: pip install azure-storage-blob"
            ) from exc

        creds = self.credentials
        if creds.get("connection_string"):
            self._client = BlobServiceClient.from_connection_string(creds["connection_string"])
        elif creds.get("account_name") and creds.get("account_key"):
            account_url = self._account_url or f"https://{creds['account_name']}.blob.core.windows.net"
            self._client = BlobServiceClient(
                account_url=account_url,
                credential=creds["account_key"],
            )
        else:
            raise ValueError(
                "Azure credentials require connection_string or account_name + account_key"
            )
        return self._client

    def read(self, object_key: str, local_path: Union[str, Path]) -> Path:
        destination = Path(local_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        blob_client = self._get_client().get_blob_client(
            container=self._container,
            blob=self._full_key(object_key),
        )
        with open(destination, "wb") as handle:
            handle.write(blob_client.download_blob().readall())
        return destination

    def upload(self, local_path: Union[str, Path], object_key: str) -> str:
        source = Path(local_path)
        if not source.is_file():
            raise FileNotFoundError(f"Local file not found: {source}")
        blob_client = self._get_client().get_blob_client(
            container=self._container,
            blob=self._full_key(object_key),
        )
        with open(source, "rb") as handle:
            blob_client.upload_blob(handle, overwrite=True)
        return self._remote_uri(object_key)
