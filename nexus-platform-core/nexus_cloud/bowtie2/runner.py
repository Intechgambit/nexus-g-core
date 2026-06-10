"""
Bowtie2 runner with cloud storage I/O.

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
from nexus_cloud.common.staging import stage_index_files
from nexus_cloud.config import RunJob, build_storage
from nexus_cloud.storage.base import CloudStorage

DEFAULT_MODE = "single"

BOWTIE2_INDEX_SUFFIXES = [
    ".1.bt2", ".2.bt2", ".3.bt2", ".4.bt2",
    ".rev.1.bt2", ".rev.2.bt2",
    ".1.bt2l", ".2.bt2l", ".3.bt2l", ".4.bt2l",
    ".rev.1.bt2l", ".rev.2.bt2l",
]


@dataclass
class Bowtie2Config:
    index_path: str
    mode: Literal["single", "paired"] = DEFAULT_MODE
    num_threads: int = DEFAULT_NUM_THREADS
    extra_args: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index_path": self.index_path,
            "mode": self.mode,
            "num_threads": self.num_threads,
            "extra_args": list(self.extra_args),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Bowtie2Config:
        return cls(
            index_path=str(data["index_path"]),
            mode=data.get("mode", DEFAULT_MODE),
            num_threads=int(data.get("num_threads", DEFAULT_NUM_THREADS)),
            extra_args=list(data.get("extra_args") or []),
        )


@dataclass
class Bowtie2CloudConfig:
    cloud: Any
    bowtie2: Bowtie2Config
    run: Any

    def to_storage(self) -> CloudStorage:
        return self.cloud.to_storage()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Bowtie2CloudConfig:
        from nexus_cloud.config import CloudConfig, RunConfig

        cloud = CloudConfig.from_dict(data.get("cloud") or {})
        tool_data = data.get("bowtie2") or {}
        if not tool_data.get("index_path"):
            raise ValueError("bowtie2.index_path is required")
        bowtie2 = Bowtie2Config.from_dict(tool_data)
        run = RunConfig.from_dict(data.get("run") or {})
        return cls(cloud=cloud, bowtie2=bowtie2, run=run)

    @classmethod
    def from_file(cls, path: str | Path) -> Bowtie2CloudConfig:
        from nexus_cloud.config import load_raw_config

        return cls.from_dict(load_raw_config(path))


def _execute_bowtie2_job(
    cloud_config: dict[str, Any],
    tool_config: dict[str, Any],
    input_key: str,
    output_key: str,
    input2_key: str | None,
    index_prefix: str | None,
) -> JobResult:
    try:
        storage = build_storage(
            cloud_config["provider"],
            cloud_config["bucket_path"],
            cloud_config.get("credentials") or {},
        )
        runner = Bowtie2Runner(storage, Bowtie2Config.from_dict(tool_config))
        remote_uri = runner.run(
            input_key, output_key, input2_key=input2_key, index_prefix=index_prefix
        )
        return JobResult(input_key=input_key, output_key=output_key, remote_uri=remote_uri, success=True)
    except Exception as exc:
        return JobResult(input_key=input_key, output_key=output_key, success=False, error=str(exc))


class Bowtie2Runner:
    def __init__(self, storage: CloudStorage, config: Bowtie2Config):
        self.storage = storage
        self.config = config

    @staticmethod
    def _which_bowtie2() -> str:
        path = shutil.which("bowtie2")
        if not path:
            raise RuntimeError("bowtie2 not found in PATH. Install Bowtie2.")
        return path

    def _resolve_index(self, work_dir: Path) -> str:
        return stage_index_files(
            self.storage,
            self.config.index_path,
            work_dir,
            BOWTIE2_INDEX_SUFFIXES,
            subdir="bowtie2index",
        )

    def _run_bowtie2(
        self,
        index_prefix: str,
        reads_path: Path,
        reads2_path: Path | None,
        output_path: Path,
    ) -> None:
        cmd = [
            self._which_bowtie2(),
            "-x", index_prefix,
            "--threads", str(self.config.num_threads),
            "-S", str(output_path),
            *self.config.extra_args,
        ]
        if self.config.mode == "paired":
            if reads2_path is None:
                raise ValueError("Paired-end mode requires input2 / R2 reads")
            cmd.extend(["-1", str(reads_path), "-2", str(reads2_path)])
        else:
            cmd.extend(["-U", str(reads_path)])

        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(
                f"Bowtie2 failed (exit {proc.returncode}):\n{proc.stderr or proc.stdout}"
            )

    def run(
        self,
        input_key: str,
        output_key: str,
        input2_key: str | None = None,
        index_prefix: str | None = None,
        work_dir: Path | None = None,
    ) -> str:
        if work_dir is not None:
            reads_path = work_dir / "reads_R1.fa"
            reads2_path = work_dir / "reads_R2.fa" if input2_key else None
            output_path = work_dir / "alignment.sam"

            self.storage.read(input_key, reads_path)
            if input2_key:
                self.storage.read(input2_key, reads2_path)
            resolved_index = index_prefix or self._resolve_index(work_dir)
            self._run_bowtie2(resolved_index, reads_path, reads2_path, output_path)
            return self.storage.upload(output_path, output_key)

        with tempfile.TemporaryDirectory(prefix="nexus-bowtie2-") as tmp:
            return self.run(
                input_key, output_key,
                input2_key=input2_key,
                index_prefix=index_prefix,
                work_dir=Path(tmp),
            )

    def _index_is_local(self) -> bool:
        prefix = self.config.index_path
        return any(Path(f"{prefix}{suffix}").is_file() for suffix in BOWTIE2_INDEX_SUFFIXES)

    def _stage_index_for_batch(self) -> tuple[str, tempfile.TemporaryDirectory | None]:
        if self._index_is_local():
            return self.config.index_path, None
        temp = tempfile.TemporaryDirectory(prefix="nexus-bowtie2-index-")
        index_prefix = self._resolve_index(Path(temp.name))
        return index_prefix, temp

    def run_batch(
        self,
        jobs: list[RunJob],
        pool_workers: int = DEFAULT_POOL_WORKERS,
    ) -> list[JobResult]:
        if not jobs:
            return []

        cloud_config = storage_cloud_config(self.storage)
        tool_config = self.config.to_dict()
        index_prefix, index_temp = self._stage_index_for_batch()

        try:
            worker_jobs = [
                (cloud_config, tool_config, j.input_key, j.output_key, j.input2_key, index_prefix)
                for j in jobs
            ]
            return run_batch(_execute_bowtie2_job, worker_jobs, pool_workers)
        finally:
            if index_temp is not None:
                index_temp.cleanup()
