#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GIAT shared configuration loader for local genomic tool runs.

Author: Amina Jackson, Intechgambit
License: GPL-3.0
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_POOL_WORKERS = 1


@dataclass
class RunJob:
    input_path: str
    output_path: str
    input2_path: str | None = None
    report_path: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunJob:
        input_path = data.get("input") or data.get("input_path")
        output_path = data.get("output") or data.get("output_path")
        if not input_path or not output_path:
            raise ValueError("Each job requires input and output paths")
        input2 = data.get("input2") or data.get("input2_path")
        report = data.get("report") or data.get("report_path")
        return cls(
            input_path=str(input_path),
            output_path=str(output_path),
            input2_path=str(input2) if input2 else None,
            report_path=str(report) if report else None,
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
        elif data.get("input") or data.get("input_path"):
            jobs = [RunJob.from_dict(data)]

        pool_workers = int(data.get("pool_workers", DEFAULT_POOL_WORKERS))
        if pool_workers < 1:
            raise ValueError("run.pool_workers must be >= 1")
        if not jobs:
            raise ValueError("run.jobs or run.input/run.output is required")
        return cls(pool_workers=pool_workers, jobs=jobs)


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    text = config_path.read_text(encoding="utf-8")
    suffix = config_path.suffix.lower()

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
        raise ValueError("Config file must contain a top-level object")
    return data


def merge_run_jobs(
    jobs: list[RunJob],
    *,
    input_path: str | None = None,
    output_path: str | None = None,
    input2_path: str | None = None,
    report_path: str | None = None,
) -> list[RunJob]:
    if not any([input_path, output_path, input2_path, report_path]):
        return jobs
    if input_path and output_path:
        return [RunJob(input_path, output_path, input2_path=input2_path, report_path=report_path)]
    if jobs:
        current = jobs[0]
        return [RunJob(
            input_path=input_path or current.input_path,
            output_path=output_path or current.output_path,
            input2_path=input2_path or current.input2_path,
            report_path=report_path or current.report_path,
        )]
    raise ValueError("run.jobs required when partially overriding input/output")
