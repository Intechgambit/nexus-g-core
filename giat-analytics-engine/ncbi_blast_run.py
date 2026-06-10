#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NCBI BLAST Run (local, config-driven)

Author: Amina Jackson, Intechgambit
email: developers@intechgambit.com
Date: 2026-06-10
License: GPL-3.0 license

Usage:
  python ncbi_blast_run.py --config configs/blast.example.json

  python ncbi_blast_run.py --config configs/blast.example.json --pool-workers 8

Notes:
  - Requires NCBI BLAST+ (blastn, blastp, etc.) in PATH.
  - All parameters are defined in the config file; CLI flags only override config values.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from giat_config import RunConfig, RunJob, load_config, merge_run_jobs  # noqa: E402

DEFAULT_EVALUE = 1e-5
DEFAULT_WORD_SIZE = 16
DEFAULT_NUM_THREADS = 4
DEFAULT_POOL_WORKERS = 1
DEFAULT_OUTFMT = "6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore"


@dataclass
class BlastConfig:
    db_path: str
    program: Literal["blastn", "blastp", "blastx", "tblastn", "tblastx"] = "blastn"
    evalue: float = DEFAULT_EVALUE
    word_size: int = DEFAULT_WORD_SIZE
    num_threads: int = DEFAULT_NUM_THREADS
    outfmt: str = DEFAULT_OUTFMT
    extra_args: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BlastConfig:
        if not data.get("db_path"):
            raise ValueError("blast.db_path is required in config")
        return cls(
            db_path=str(data["db_path"]),
            program=data.get("program", "blastn"),
            evalue=float(data.get("evalue", DEFAULT_EVALUE)),
            word_size=int(data.get("word_size", DEFAULT_WORD_SIZE)),
            num_threads=int(data.get("num_threads", DEFAULT_NUM_THREADS)),
            outfmt=data.get("outfmt", DEFAULT_OUTFMT),
            extra_args=list(data.get("extra_args") or []),
        )

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


@dataclass
class BlastRunConfig:
    blast: BlastConfig
    run: RunConfig

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BlastRunConfig:
        return cls(
            blast=BlastConfig.from_dict(data.get("blast") or {}),
            run=RunConfig.from_dict(data.get("run") or {}),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> BlastRunConfig:
        return cls.from_dict(load_config(path))


@dataclass
class BlastJobResult:
    input_path: str
    output_path: str
    success: bool = True
    error: str | None = None


def _which_blast(program: str) -> str:
    path = shutil.which(program)
    if not path:
        raise RuntimeError(f"{program} not found in PATH. Install NCBI BLAST+.")
    return path


def _verify_db_prefix(db_path: str) -> str:
    prefix = Path(db_path)
    extensions = [".nhr", ".nin", ".nsq", ".phr", ".pin", ".psq"]
    if any(prefix.with_suffix(ext).is_file() for ext in extensions):
        return str(prefix)
    if any(Path(f"{db_path}{ext}").is_file() for ext in extensions):
        return db_path
    raise FileNotFoundError(f"BLAST database not found at prefix: {db_path}")


def _run_blast_process(
    blast_config: dict[str, Any],
    input_path: str,
    output_path: str,
    db_prefix: str,
) -> BlastJobResult:
    try:
        config = BlastConfig.from_dict({**blast_config, "db_path": db_prefix})
        query = Path(input_path)
        output = Path(output_path)
        if not query.is_file():
            raise FileNotFoundError(f"Query file not found: {query}")
        output.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            _which_blast(config.program),
            "-query", str(query),
            "-db", db_prefix,
            "-out", str(output),
            "-outfmt", config.outfmt,
            "-evalue", str(config.evalue),
            "-word_size", str(config.word_size),
            "-num_threads", str(config.num_threads),
            *config.extra_args,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or proc.stdout)
        return BlastJobResult(input_path=input_path, output_path=output_path, success=True)
    except Exception as exc:
        return BlastJobResult(
            input_path=input_path,
            output_path=output_path,
            success=False,
            error=str(exc),
        )


class LocalBlastRunner:
    def __init__(self, config: BlastConfig):
        self.config = config
        self.db_prefix = _verify_db_prefix(config.db_path)

    def run(self, input_path: str, output_path: str) -> str:
        result = _run_blast_process(
            self.config.to_dict(),
            input_path,
            output_path,
            self.db_prefix,
        )
        if not result.success:
            raise RuntimeError(result.error)
        return output_path

    def run_batch(self, jobs: list[RunJob], pool_workers: int = DEFAULT_POOL_WORKERS) -> list[BlastJobResult]:
        if not jobs:
            return []

        pool_workers = max(1, pool_workers)
        blast_config = {**self.config.to_dict(), "db_path": self.db_prefix}
        worker_args = [
            (blast_config, job.input_path, job.output_path, self.db_prefix)
            for job in jobs
        ]

        if pool_workers == 1 or len(jobs) == 1:
            return [_run_blast_process(*args) for args in worker_args]

        results: list[BlastJobResult] = []
        with ProcessPoolExecutor(max_workers=pool_workers) as executor:
            futures = {executor.submit(_run_blast_process, *args): args for args in worker_args}
            for future in as_completed(futures):
                results.append(future.result())
        return results


def _parse_extra_args(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError("--extra-args must be a JSON array of strings")
    return parsed


def _config_from_args(args: argparse.Namespace) -> BlastRunConfig:
    if not args.config:
        raise ValueError("--config is required. Copy configs/blast.example.json and pass --config path.")

    config = BlastRunConfig.from_file(args.config)
    extra_args = _parse_extra_args(args.extra_args)

    blast = BlastConfig(
        db_path=args.db_path or config.blast.db_path,
        program=args.program or config.blast.program,
        evalue=args.evalue if args.evalue is not None else config.blast.evalue,
        word_size=args.word_size if args.word_size is not None else config.blast.word_size,
        num_threads=args.num_threads if args.num_threads is not None else config.blast.num_threads,
        outfmt=args.outfmt or config.blast.outfmt,
        extra_args=extra_args if extra_args is not None else config.blast.extra_args,
    )
    jobs = merge_run_jobs(
        config.run.jobs,
        input_path=args.input,
        output_path=args.output,
    )
    run = RunConfig(
        pool_workers=args.pool_workers if args.pool_workers is not None else config.run.pool_workers,
        jobs=jobs,
    )
    return BlastRunConfig(blast=blast, run=run)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run NCBI BLAST locally using a config file",
        epilog="All parameters live in the config file. CLI flags override config values only.",
    )
    parser.add_argument("--config", "-c", required=True, help="Path to JSON or YAML config file")
    parser.add_argument("--input", help="Override run input path")
    parser.add_argument("--output", help="Override run output path")
    parser.add_argument("--db-path", help="Override blast.db_path")
    parser.add_argument("--program", choices=["blastn", "blastp", "blastx", "tblastn", "tblastx"])
    parser.add_argument("--evalue", type=float)
    parser.add_argument("--word-size", type=int)
    parser.add_argument("--num-threads", type=int)
    parser.add_argument("--pool-workers", type=int)
    parser.add_argument("--outfmt")
    parser.add_argument("--extra-args", help="Override blast.extra_args as JSON array")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        config = _config_from_args(args)
        runner = LocalBlastRunner(config.blast)
        jobs = config.run.jobs

        if len(jobs) == 1 and config.run.pool_workers == 1:
            out = runner.run(jobs[0].input_path, jobs[0].output_path)
            print(f"BLAST complete. Output: {out}")
            return 0

        results = runner.run_batch(jobs, pool_workers=config.run.pool_workers)
        succeeded = sum(1 for r in results if r.success)
        failed = len(results) - succeeded
        for result in results:
            if result.success:
                print(f"OK  {result.input_path} -> {result.output_path}")
            else:
                print(f"ERR {result.input_path}: {result.error}", file=sys.stderr)
        print(f"Batch complete: {succeeded} succeeded, {failed} failed")
        return 0 if failed == 0 else 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
