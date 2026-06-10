"""Config-first CLI helpers for Nexus Cloud tools."""

from __future__ import annotations

import argparse
import json
from typing import Any

from nexus_cloud.config import CloudConfig, RunConfig, RunJob


def require_config_path(args: argparse.Namespace, tool_name: str) -> None:
    if not args.config:
        raise ValueError(
            f"--config is required for {tool_name}. "
            f"Copy the example config from nexus_cloud/config*.example.json."
        )


def parse_extra_args(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError("--extra-args must be a JSON array of strings")
    return parsed


def merge_cloud_config(config: CloudConfig, args: argparse.Namespace, credentials: dict[str, Any]) -> CloudConfig:
    if not any([args.provider, args.bucket_path, credentials]):
        return config
    return CloudConfig(
        provider=(args.provider or config.provider).lower(),
        bucket_path=args.bucket_path or config.bucket_path,
        credentials={**config.credentials, **credentials} if credentials else config.credentials,
    )


def merge_run_config(config: RunConfig, args: argparse.Namespace) -> RunConfig:
    jobs = list(config.jobs)
    if args.input_key or args.output_key or args.input2_key or args.report_key:
        if args.input_key and args.output_key:
            jobs = [RunJob(
                input_key=args.input_key,
                output_key=args.output_key,
                input2_key=args.input2_key,
                report_key=args.report_key,
            )]
        elif jobs:
            current = jobs[0]
            jobs = [RunJob(
                input_key=args.input_key or current.input_key,
                output_key=args.output_key or current.output_key,
                input2_key=args.input2_key or current.input2_key,
                report_key=args.report_key or current.report_key,
            )]
    return RunConfig(
        pool_workers=args.pool_workers if args.pool_workers is not None else config.pool_workers,
        jobs=jobs,
    )
