"""
Abstract cloud storage interface for Nexus Cloud.

Author: Amina Jackson, Intechgambit
License: GPL-3.0
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union


class CloudStorage(ABC):
    """Provider-agnostic read/upload contract for cloud object storage."""

    def __init__(self, bucket_path: str, credentials: dict | None = None):
        self.bucket_path = bucket_path.rstrip("/")
        self.credentials = credentials or {}

    @abstractmethod
    def read(self, object_key: str, local_path: Union[str, Path]) -> Path:
        """Download an object from cloud storage to a local file."""

    @abstractmethod
    def upload(self, local_path: Union[str, Path], object_key: str) -> str:
        """Upload a local file to cloud storage; returns the remote URI."""

    def read_to_bytes(self, object_key: str) -> bytes:
        """Download object contents into memory."""
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            self.read(object_key, tmp_path)
            return tmp_path.read_bytes()
        finally:
            tmp_path.unlink(missing_ok=True)

    def upload_from_bytes(self, data: bytes, object_key: str, suffix: str = "") -> str:
        """Upload in-memory bytes to cloud storage."""
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)
        try:
            return self.upload(tmp_path, object_key)
        finally:
            tmp_path.unlink(missing_ok=True)
