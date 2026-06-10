"""
NCBI BLAST runner with cloud storage I/O.

Author: Amina Jackson, Intechgambit
License: GPL-3.0
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from nexus_cloud.storage.base import CloudStorage


DEFAULT_EVALUE = 1e-5
DEFAULT_WORD_SIZE = 16
DEFAULT_NUM_THREADS = 4
DEFAULT_POOL_WORKERS = 1

BLAST_DB_EXTENSIONS = [
    ".nhr", ".nin", ".nsq", ".nog", ".nos", ".not", ".nnd", ".nni",
    ".phr", ".pin", ".psq", ".pog", ".pos", ".pot", ".pnd", ".pni",
]


@dataclass
class BlastConfig:
    """BLAST execution parameters."""

    db_path: str
    program: Literal["blastn", "blastp", "blastx", "tblastn", "tblastx"] = "blastn"
    evalue: float = DEFAULT_EVALUE
    word_size: int = DEFAULT_WORD_SIZE
    num_threads: int = DEFAULT_NUM_THREADS
    outfmt: str = "6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore"
    extra_args: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "db_path": self.db_path,
            "program": self.program,
            "evalue": self.evalue,
            "word_size": self.word_size,
            "num_threads": self.num_threads,
            "outfmt": self.outfmt,
            "extra_args": list(self.extra_args),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BlastConfig:
        return cls(
            db_path=str(data["db_path"]),
            program=data.get("program", "blastn"),
            evalue=float(data.get("evalue", DEFAULT_EVALUE)),
            word_size=int(data.get("word_size", DEFAULT_WORD_SIZE)),
            num_threads=int(data.get("num_threads", DEFAULT_NUM_THREADS)),
            outfmt=data.get(
                "outfmt",
                "6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore",
            ),
            extra_args=list(data.get("extra_args") or []),
        )


@dataclass
class BlastJobResult:
    input_key: str
    output_key: str
    remote_uri: str | None = None
    success: bool = True
    error: str | None = None


def _execute_blast_job(
    cloud_config: dict[str, Any],
    blast_config: dict[str, Any],
    input_key: str,
    output_key: str,
    db_prefix: str | None,
) -> BlastJobResult:
    """Module-level worker for process pool execution."""
    from nexus_cloud.config import build_storage

    try:
        storage = build_storage(
            cloud_config["provider"],
            cloud_config["bucket_path"],
            cloud_config.get("credentials") or {},
        )
        runner = BlastRunner(storage, BlastConfig.from_dict(blast_config))
        remote_uri = runner.run(input_key, output_key, db_prefix=db_prefix)
        return BlastJobResult(
            input_key=input_key,
            output_key=output_key,
            remote_uri=remote_uri,
            success=True,
        )
    except Exception as exc:
        return BlastJobResult(
            input_key=input_key,
            output_key=output_key,
            success=False,
            error=str(exc),
        )


class BlastRunner:
    """
    Run NCBI BLAST against queries in cloud storage and write results back.

    Supports single-job execution and high-volume batch runs via a process pool.
    """

    def __init__(self, storage: CloudStorage, config: BlastConfig):
        self.storage = storage
        self.config = config

    @staticmethod
    def _which_blast(program: str) -> str:
        path = shutil.which(program)
        if not path:
            raise RuntimeError(
                f"{program} not found in PATH. Install NCBI BLAST+ and ensure it is available."
            )
        return path

    def _resolve_db_prefix(self, work_dir: Path) -> str:
        """
        Resolve the BLAST database prefix.

        If db_path is local, use it directly. Otherwise download index files from cloud.
        """
        db_path = self.config.db_path
        local_candidate = Path(db_path)
        if local_candidate.exists():
            return str(local_candidate)

        db_dir = work_dir / "blastdb"
        db_dir.mkdir(parents=True, exist_ok=True)
        prefix = db_path.rstrip("/")
        base_name = Path(prefix).name or "db"

        for ext in BLAST_DB_EXTENSIONS:
            key = f"{prefix}{ext}"
            try:
                self.storage.read(key, db_dir / f"{base_name}{ext}")
            except Exception:
                continue

        staged = db_dir / base_name
        if not any(staged.with_suffix(ext).exists() for ext in BLAST_DB_EXTENSIONS[:3]):
            raise FileNotFoundError(
                f"BLAST database not found locally or in cloud at prefix: {prefix}"
            )
        return str(staged)

    def stage_db_prefix(self, work_dir: Path | None = None) -> tuple[str, tempfile.TemporaryDirectory | None]:
        """
        Stage the BLAST database once for reuse across parallel workers.

        Returns (db_prefix, temp_dir). Caller must keep temp_dir alive while workers run.
        """
        if Path(self.config.db_path).exists():
            return self.config.db_path, None

        temp_dir = work_dir
        owns_temp = False
        if temp_dir is None:
            temp = tempfile.TemporaryDirectory(prefix="nexus-blast-db-")
            temp_dir = Path(temp.name)
            owns_temp = True
        else:
            temp = None

        db_prefix = self._resolve_db_prefix(Path(temp_dir))
        return db_prefix, temp if owns_temp else None

    def _run_blast(self, query_path: Path, db_prefix: str, output_path: Path) -> None:
        program = self.config.program
        blast_bin = self._which_blast(program)
        cmd = [
            blast_bin,
            "-query", str(query_path),
            "-db", db_prefix,
            "-out", str(output_path),
            "-outfmt", self.config.outfmt,
            "-evalue", str(self.config.evalue),
            "-word_size", str(self.config.word_size),
            "-num_threads", str(self.config.num_threads),
            *self.config.extra_args,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(
                f"BLAST failed (exit {proc.returncode}):\n{proc.stderr or proc.stdout}"
            )

    def run(
        self,
        input_key: str,
        output_key: str,
        db_prefix: str | None = None,
        work_dir: Path | None = None,
    ) -> str:
        """
        Execute BLAST for one cloud-stored query and upload results.

        When db_prefix is provided (e.g. from a shared staging step), database
        resolution is skipped.
        """
        if work_dir is not None:
            query_path = work_dir / "query.fasta"
            output_path = work_dir / "blast_results.tsv"
            self.storage.read(input_key, query_path)
            resolved_db = db_prefix or self._resolve_db_prefix(work_dir)
            self._run_blast(query_path, resolved_db, output_path)
            return self.storage.upload(output_path, output_key)

        with tempfile.TemporaryDirectory(prefix="nexus-blast-") as tmp:
            return self.run(input_key, output_key, db_prefix=db_prefix, work_dir=Path(tmp))

    def run_batch(
        self,
        jobs: list[tuple[str, str]],
        pool_workers: int = DEFAULT_POOL_WORKERS,
    ) -> list[BlastJobResult]:
        """
        Run many BLAST jobs in parallel using a process pool.

        The BLAST database is staged once and shared across workers. Each worker
        runs an independent BLAST process with num_threads from config.
        """
        if not jobs:
            return []

        pool_workers = max(1, pool_workers)
        cloud_config = {
            "provider": self._provider_name(),
            "bucket_path": self.storage.bucket_path,
            "credentials": self.storage.credentials,
        }
        blast_config = self.config.to_dict()

        db_temp: tempfile.TemporaryDirectory | None
        db_prefix, db_temp = self.stage_db_prefix()

        try:
            if pool_workers == 1 or len(jobs) == 1:
                results = [
                    _execute_blast_job(cloud_config, blast_config, input_key, output_key, db_prefix)
                    for input_key, output_key in jobs
                ]
                return results

            results: list[BlastJobResult] = []
            with ProcessPoolExecutor(max_workers=pool_workers) as executor:
                futures = {
                    executor.submit(
                        _execute_blast_job,
                        cloud_config,
                        blast_config,
                        input_key,
                        output_key,
                        db_prefix,
                    ): (input_key, output_key)
                    for input_key, output_key in jobs
                }
                for future in as_completed(futures):
                    results.append(future.result())
            return results
        finally:
            if db_temp is not None:
                db_temp.cleanup()

    def _provider_name(self) -> str:
        class_name = self.storage.__class__.__name__
        if class_name == "AwsBucketStorage":
            return "aws"
        if class_name == "GcpBucketStorage":
            return "gcp"
        if class_name == "AzureBlobStorage":
            return "azure"
        raise ValueError(f"Unknown storage class: {class_name}")
