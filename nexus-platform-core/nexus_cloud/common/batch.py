"""Batch execution helpers for Nexus Cloud tool runners."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable

from nexus_cloud.common.constants import DEFAULT_POOL_WORKERS
from nexus_cloud.storage.base import CloudStorage


@dataclass
class JobResult:
    input_key: str
    output_key: str
    remote_uri: str | None = None
    report_uri: str | None = None
    success: bool = True
    error: str | None = None


def provider_name(storage: CloudStorage) -> str:
    class_name = storage.__class__.__name__
    mapping = {
        "AwsBucketStorage": "aws",
        "GcpBucketStorage": "gcp",
        "AzureBlobStorage": "azure",
    }
    if class_name not in mapping:
        raise ValueError(f"Unknown storage class: {class_name}")
    return mapping[class_name]


def storage_cloud_config(storage: CloudStorage) -> dict[str, Any]:
    return {
        "provider": provider_name(storage),
        "bucket_path": storage.bucket_path,
        "credentials": storage.credentials,
    }


def run_batch(
    worker: Callable[..., JobResult],
    jobs: list[tuple[Any, ...]],
    pool_workers: int = DEFAULT_POOL_WORKERS,
) -> list[JobResult]:
    if not jobs:
        return []
    pool_workers = max(1, pool_workers)
    if pool_workers == 1 or len(jobs) == 1:
        return [worker(*job) for job in jobs]

    results: list[JobResult] = []
    with ProcessPoolExecutor(max_workers=pool_workers) as executor:
        futures = {executor.submit(worker, *job): job for job in jobs}
        for future in as_completed(futures):
            results.append(future.result())
    return results
