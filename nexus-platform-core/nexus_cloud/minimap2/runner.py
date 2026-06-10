"""
Minimap2 runner with cloud storage I/O.

Author: Amina Jackson, Intechgambit
License: GPL-3.0
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from nexus_cloud.common.batch import JobResult, run_batch, storage_cloud_config
from nexus_cloud.common.constants import DEFAULT_NUM_THREADS, DEFAULT_POOL_WORKERS
from nexus_cloud.common.staging import stage_reference
from nexus_cloud.config import RunJob, build_storage
from nexus_cloud.storage.base import CloudStorage

DEFAULT_PRESET = "map-ont"
DEFAULT_OUTPUT_FORMAT = "sam"


@dataclass
class Minimap2Config:
    reference_path: str
    preset: str = DEFAULT_PRESET
    num_threads: int = DEFAULT_NUM_THREADS
    output_format: Literal["sam", "paf"] = DEFAULT_OUTPUT_FORMAT
    extra_args: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference_path": self.reference_path,
            "preset": self.preset,
            "num_threads": self.num_threads,
            "output_format": self.output_format,
            "extra_args": list(self.extra_args),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Minimap2Config:
        return cls(
            reference_path=str(data["reference_path"]),
            preset=data.get("preset", DEFAULT_PRESET),
            num_threads=int(data.get("num_threads", DEFAULT_NUM_THREADS)),
            output_format=data.get("output_format", DEFAULT_OUTPUT_FORMAT),
            extra_args=list(data.get("extra_args") or []),
        )


@dataclass
class Minimap2CloudConfig:
    cloud: Any
    minimap2: Minimap2Config
    run: Any

    def to_storage(self) -> CloudStorage:
        return self.cloud.to_storage()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Minimap2CloudConfig:
        from nexus_cloud.config import CloudConfig, RunConfig

        cloud = CloudConfig.from_dict(data.get("cloud") or {})
        tool_data = data.get("minimap2") or {}
        if not tool_data.get("reference_path"):
            raise ValueError("minimap2.reference_path is required")
        minimap2 = Minimap2Config.from_dict(tool_data)
        run = RunConfig.from_dict(data.get("run") or {})
        return cls(cloud=cloud, minimap2=minimap2, run=run)

    @classmethod
    def from_file(cls, path: str | Path) -> Minimap2CloudConfig:
        from nexus_cloud.config import load_raw_config

        return cls.from_dict(load_raw_config(path))


def _execute_minimap2_job(
    cloud_config: dict[str, Any],
    tool_config: dict[str, Any],
    input_key: str,
    output_key: str,
    reference_path: str | None,
) -> JobResult:
    try:
        storage = build_storage(
            cloud_config["provider"],
            cloud_config["bucket_path"],
            cloud_config.get("credentials") or {},
        )
        runner = Minimap2Runner(storage, Minimap2Config.from_dict(tool_config))
        remote_uri = runner.run(input_key, output_key, reference_path=reference_path)
        return JobResult(input_key=input_key, output_key=output_key, remote_uri=remote_uri, success=True)
    except Exception as exc:
        return JobResult(input_key=input_key, output_key=output_key, success=False, error=str(exc))


class Minimap2Runner:
    def __init__(self, storage: CloudStorage, config: Minimap2Config):
        self.storage = storage
        self.config = config

    @staticmethod
    def _which_minimap2() -> str:
        path = shutil.which("minimap2")
        if not path:
            raise RuntimeError("minimap2 not found in PATH. Install Minimap2.")
        return path

    def _resolve_reference(self, work_dir: Path) -> str:
        return stage_reference(self.storage, self.config.reference_path, work_dir)

    def _run_minimap2(self, reference: str, reads_path: Path, output_path: Path) -> None:
        cmd = [
            self._which_minimap2(),
            "-x", self.config.preset,
            "-t", str(self.config.num_threads),
            *self.config.extra_args,
            reference,
            str(reads_path),
        ]
        if self.config.output_format == "sam":
            cmd.insert(1, "-a")

        with open(output_path, "wb") as out_handle:
            proc = subprocess.run(cmd, stdout=out_handle, stderr=subprocess.PIPE, text=False)
        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", errors="replace") if proc.stderr else ""
            raise RuntimeError(f"Minimap2 failed (exit {proc.returncode}):\n{stderr}")

    def run(
        self,
        input_key: str,
        output_key: str,
        reference_path: str | None = None,
        work_dir: Path | None = None,
    ) -> str:
        if work_dir is not None:
            reads_path = work_dir / "reads.fa"
            ext = "sam" if self.config.output_format == "sam" else "paf"
            output_path = work_dir / f"alignment.{ext}"

            self.storage.read(input_key, reads_path)
            reference = reference_path or self._resolve_reference(work_dir)
            self._run_minimap2(reference, reads_path, output_path)
            return self.storage.upload(output_path, output_key)

        with tempfile.TemporaryDirectory(prefix="nexus-minimap2-") as tmp:
            return self.run(input_key, output_key, reference_path=reference_path, work_dir=Path(tmp))

    def _stage_reference_for_batch(self) -> tuple[str, tempfile.TemporaryDirectory | None]:
        if Path(self.config.reference_path).is_file():
            return self.config.reference_path, None
        temp = tempfile.TemporaryDirectory(prefix="nexus-minimap2-ref-")
        ref = stage_reference(self.storage, self.config.reference_path, Path(temp.name))
        return ref, temp

    def run_batch(
        self,
        jobs: list[RunJob],
        pool_workers: int = DEFAULT_POOL_WORKERS,
    ) -> list[JobResult]:
        if not jobs:
            return []

        cloud_config = storage_cloud_config(self.storage)
        tool_config = self.config.to_dict()
        reference, ref_temp = self._stage_reference_for_batch()

        try:
            worker_jobs = [
                (cloud_config, tool_config, j.input_key, j.output_key, reference)
                for j in jobs
            ]
            return run_batch(_execute_minimap2_job, worker_jobs, pool_workers)
        finally:
            if ref_temp is not None:
                ref_temp.cleanup()
