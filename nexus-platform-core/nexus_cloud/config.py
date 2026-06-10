"""
Configuration loader for Nexus Cloud.

Author: Amina Jackson, Intechgambit
License: GPL-3.0
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nexus_cloud.blast.runner import BlastConfig
from nexus_cloud.common.constants import DEFAULT_POOL_WORKERS
from nexus_cloud.storage.aws_bucket import AwsBucketStorage
from nexus_cloud.storage.azure_blob import AzureBlobStorage
from nexus_cloud.storage.base import CloudStorage
from nexus_cloud.storage.gcp_bucket import GcpBucketStorage


@dataclass
class CloudConfig:
    provider: str
    bucket_path: str
    credentials: dict[str, Any] = field(default_factory=dict)

    def to_storage(self) -> CloudStorage:
        return build_storage(self.provider, self.bucket_path, self.credentials)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "bucket_path": self.bucket_path,
            "credentials": self.credentials,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CloudConfig:
        if not data.get("provider"):
            raise ValueError("cloud.provider is required")
        if not data.get("bucket_path"):
            raise ValueError("cloud.bucket_path is required")
        return cls(
            provider=str(data["provider"]).lower(),
            bucket_path=str(data["bucket_path"]),
            credentials=dict(data.get("credentials") or {}),
        )


@dataclass
class RunJob:
    input_key: str
    output_key: str
    input2_key: str | None = None
    report_key: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunJob:
        input_key = data.get("input") or data.get("input_key")
        output_key = data.get("output") or data.get("output_key")
        if not input_key or not output_key:
            raise ValueError("Each job requires input and output keys")
        input2 = data.get("input2") or data.get("input2_key")
        report = data.get("report") or data.get("report_key")
        return cls(
            input_key=str(input_key),
            output_key=str(output_key),
            input2_key=str(input2) if input2 else None,
            report_key=str(report) if report else None,
        )


@dataclass
class RunConfig:
    pool_workers: int = DEFAULT_POOL_WORKERS
    jobs: list[RunJob] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunConfig:
        jobs: list[RunJob] = []
        if data.get("jobs"):
            jobs = [RunJob.from_dict(job) for job in data["jobs"]]
        elif data.get("input") or data.get("input_key"):
            jobs = [RunJob.from_dict(data)]

        pool_workers = int(data.get("pool_workers", DEFAULT_POOL_WORKERS))
        if pool_workers < 1:
            raise ValueError("run.pool_workers must be >= 1")
        if not jobs:
            raise ValueError("run.jobs or run.input/run.output is required")
        return cls(pool_workers=pool_workers, jobs=jobs)


@dataclass
class NexusCloudConfig:
    """BLAST-specific top-level config (backward compatible)."""

    cloud: CloudConfig
    blast: BlastConfig
    run: RunConfig

    def to_storage(self) -> CloudStorage:
        return self.cloud.to_storage()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NexusCloudConfig:
        cloud = CloudConfig.from_dict(data.get("cloud") or {})
        blast_data = data.get("blast") or {}
        if not blast_data.get("db_path"):
            raise ValueError("blast.db_path is required")
        blast = BlastConfig.from_dict(blast_data)
        run = RunConfig.from_dict(data.get("run") or {})
        return cls(cloud=cloud, blast=blast, run=run)

    @classmethod
    def from_file(cls, path: str | Path) -> NexusCloudConfig:
        return cls.from_dict(load_raw_config(path))


def build_storage(provider: str, bucket_path: str, credentials: dict[str, Any] | None = None) -> CloudStorage:
    provider = provider.lower()
    creds = credentials or {}
    if provider == "aws":
        return AwsBucketStorage(bucket_path, creds)
    if provider == "gcp":
        return GcpBucketStorage(bucket_path, creds)
    if provider == "azure":
        return AzureBlobStorage(bucket_path, creds)
    raise ValueError(f"Unsupported cloud provider: {provider}")


def load_raw_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    return _load_raw_config(config_path)


def _load_raw_config(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")

    if suffix == ".json":
        data = json.loads(text)
    elif suffix in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:
            raise ImportError(
                "PyYAML is required for YAML configs. Install with: pip install pyyaml"
            ) from exc
        data = yaml.safe_load(text)
    else:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            try:
                import yaml
            except ImportError as exc:
                raise ValueError(
                    f"Unsupported config format '{suffix}'. Use .json or install PyYAML for .yaml"
                ) from exc
            data = yaml.safe_load(text)

    if not isinstance(data, dict):
        raise ValueError("Config file must contain a top-level mapping/object")
    return data


def merge_cli_overrides(
    config: NexusCloudConfig,
    *,
    provider: str | None = None,
    bucket_path: str | None = None,
    input_key: str | None = None,
    output_key: str | None = None,
    db_path: str | None = None,
    program: str | None = None,
    evalue: float | None = None,
    word_size: int | None = None,
    num_threads: int | None = None,
    outfmt: str | None = None,
    extra_args: list[str] | None = None,
    pool_workers: int | None = None,
) -> NexusCloudConfig:
    """Apply CLI flag overrides on top of a loaded BLAST config file."""
    cloud = config.cloud
    if provider or bucket_path:
        cloud = CloudConfig(
            provider=(provider or cloud.provider).lower(),
            bucket_path=bucket_path or cloud.bucket_path,
            credentials=cloud.credentials,
        )

    blast = BlastConfig(
        db_path=db_path or config.blast.db_path,
        program=program or config.blast.program,
        evalue=evalue if evalue is not None else config.blast.evalue,
        word_size=word_size if word_size is not None else config.blast.word_size,
        num_threads=num_threads if num_threads is not None else config.blast.num_threads,
        outfmt=outfmt or config.blast.outfmt,
        extra_args=extra_args if extra_args is not None else config.blast.extra_args,
    )

    jobs = list(config.run.jobs)
    if input_key or output_key:
        if input_key and output_key:
            jobs = [RunJob(input_key=input_key, output_key=output_key)]
        elif jobs:
            current = jobs[0]
            jobs = [RunJob(
                input_key=input_key or current.input_key,
                output_key=output_key or current.output_key,
            )]

    run = RunConfig(
        pool_workers=pool_workers if pool_workers is not None else config.run.pool_workers,
        jobs=jobs,
    )
    return NexusCloudConfig(cloud=cloud, blast=blast, run=run)
