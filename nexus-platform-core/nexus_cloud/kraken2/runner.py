"""
Kraken2 runner with cloud storage I/O.

Author: Amina Jackson, Intechgambit
License: GPL-3.0
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nexus_cloud.common.batch import JobResult, run_batch, storage_cloud_config
from nexus_cloud.common.constants import DEFAULT_NUM_THREADS, DEFAULT_POOL_WORKERS
from nexus_cloud.common.staging import stage_directory
from nexus_cloud.config import RunJob, build_storage
from nexus_cloud.storage.base import CloudStorage

DEFAULT_CONFIDENCE = 0.0
DEFAULT_MINIMUM_BASE_QUALITY = 0

KRAKEN2_DB_FILES = ["hash.k2d", "opts.k2d", "taxo.k2d"]


@dataclass
class Kraken2Config:
    db_path: str
    confidence: float = DEFAULT_CONFIDENCE
    minimum_base_quality: int = DEFAULT_MINIMUM_BASE_QUALITY
    num_threads: int = DEFAULT_NUM_THREADS
    extra_args: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "db_path": self.db_path,
            "confidence": self.confidence,
            "minimum_base_quality": self.minimum_base_quality,
            "num_threads": self.num_threads,
            "extra_args": list(self.extra_args),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Kraken2Config:
        return cls(
            db_path=str(data["db_path"]),
            confidence=float(data.get("confidence", DEFAULT_CONFIDENCE)),
            minimum_base_quality=int(data.get("minimum_base_quality", DEFAULT_MINIMUM_BASE_QUALITY)),
            num_threads=int(data.get("num_threads", DEFAULT_NUM_THREADS)),
            extra_args=list(data.get("extra_args") or []),
        )


@dataclass
class Kraken2CloudConfig:
    cloud: Any
    kraken2: Kraken2Config
    run: Any

    def to_storage(self) -> CloudStorage:
        return self.cloud.to_storage()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Kraken2CloudConfig:
        from nexus_cloud.config import CloudConfig, RunConfig

        cloud = CloudConfig.from_dict(data.get("cloud") or {})
        kraken_data = data.get("kraken2") or {}
        if not kraken_data.get("db_path"):
            raise ValueError("kraken2.db_path is required")
        kraken2 = Kraken2Config.from_dict(kraken_data)
        run = RunConfig.from_dict(data.get("run") or {})
        return cls(cloud=cloud, kraken2=kraken2, run=run)

    @classmethod
    def from_file(cls, path: str | Path) -> Kraken2CloudConfig:
        from nexus_cloud.config import load_raw_config

        return cls.from_dict(load_raw_config(path))


def _execute_kraken2_job(
    cloud_config: dict[str, Any],
    tool_config: dict[str, Any],
    input_key: str,
    output_key: str,
    report_key: str | None,
    db_dir: str | None,
) -> JobResult:
    try:
        storage = build_storage(
            cloud_config["provider"],
            cloud_config["bucket_path"],
            cloud_config.get("credentials") or {},
        )
        runner = Kraken2Runner(storage, Kraken2Config.from_dict(tool_config))
        remote_uri, report_uri = runner.run(
            input_key, output_key, report_key=report_key, db_dir=db_dir
        )
        return JobResult(
            input_key=input_key,
            output_key=output_key,
            remote_uri=remote_uri,
            report_uri=report_uri,
            success=True,
        )
    except Exception as exc:
        return JobResult(
            input_key=input_key,
            output_key=output_key,
            success=False,
            error=str(exc),
        )


class Kraken2Runner:
    def __init__(self, storage: CloudStorage, config: Kraken2Config):
        self.storage = storage
        self.config = config

    @staticmethod
    def _which_kraken2() -> str:
        path = shutil.which("kraken2")
        if not path:
            raise RuntimeError("kraken2 not found in PATH. Install Kraken2.")
        return path

    def _resolve_db_dir(self, work_dir: Path) -> str:
        db_path = self.config.db_path
        local = Path(db_path)
        if local.is_dir():
            return str(local)

        staged = stage_directory(
            self.storage,
            db_path.rstrip("/"),
            work_dir,
            KRAKEN2_DB_FILES,
            subdir="kraken2db",
        )
        return str(staged)

    def _run_kraken2(
        self,
        input_path: Path,
        output_path: Path,
        report_path: Path | None,
        db_dir: str,
    ) -> None:
        cmd = [
            self._which_kraken2(),
            "--db", db_dir,
            "--threads", str(self.config.num_threads),
            "--confidence", str(self.config.confidence),
            "--minimum-base-quality", str(self.config.minimum_base_quality),
            "--output", str(output_path),
        ]
        if report_path is not None:
            cmd.extend(["--report", str(report_path)])
        cmd.extend(self.config.extra_args)
        cmd.append(str(input_path))

        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(
                f"Kraken2 failed (exit {proc.returncode}):\n{proc.stderr or proc.stdout}"
            )

    def run(
        self,
        input_key: str,
        output_key: str,
        report_key: str | None = None,
        db_dir: str | None = None,
        work_dir: Path | None = None,
    ) -> tuple[str, str | None]:
        if work_dir is not None:
            input_path = work_dir / "reads.fa"
            output_path = work_dir / "kraken2.output"
            report_path = work_dir / "kraken2.report" if report_key else None

            self.storage.read(input_key, input_path)
            resolved_db = db_dir or self._resolve_db_dir(work_dir)
            self._run_kraken2(input_path, output_path, report_path, resolved_db)

            remote_uri = self.storage.upload(output_path, output_key)
            report_uri = None
            if report_key and report_path and report_path.is_file():
                report_uri = self.storage.upload(report_path, report_key)
            return remote_uri, report_uri

        with tempfile.TemporaryDirectory(prefix="nexus-kraken2-") as tmp:
            return self.run(
                input_key, output_key,
                report_key=report_key,
                db_dir=db_dir,
                work_dir=Path(tmp),
            )

    def _stage_db_for_batch(self) -> tuple[str, tempfile.TemporaryDirectory | None]:
        if Path(self.config.db_path).is_dir():
            return self.config.db_path, None
        temp = tempfile.TemporaryDirectory(prefix="nexus-kraken2-db-")
        db_dir = self._resolve_db_dir(Path(temp.name))
        return db_dir, temp

    def run_batch(
        self,
        jobs: list[RunJob],
        pool_workers: int = DEFAULT_POOL_WORKERS,
    ) -> list[JobResult]:
        if not jobs:
            return []

        cloud_config = storage_cloud_config(self.storage)
        tool_config = self.config.to_dict()
        db_dir, db_temp = self._stage_db_for_batch()

        try:
            worker_jobs = [
                (cloud_config, tool_config, j.input_key, j.output_key, j.report_key, db_dir)
                for j in jobs
            ]
            return run_batch(_execute_kraken2_job, worker_jobs, pool_workers)
        finally:
            if db_temp is not None:
                db_temp.cleanup()
