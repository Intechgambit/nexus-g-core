#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kraken2 Cloud CLI — config-driven cloud classification."""

from __future__ import annotations

import argparse
import sys

from nexus_cloud.common.cli import add_cloud_args, extract_credentials, print_batch_results
from nexus_cloud.common.config_cli import (
    merge_cloud_config,
    merge_run_config,
    parse_extra_args,
    require_config_path,
)
from nexus_cloud.kraken2.runner import Kraken2CloudConfig, Kraken2Config, Kraken2Runner


def _config_from_args(args: argparse.Namespace) -> Kraken2CloudConfig:
    require_config_path(args, "Kraken2")
    config = Kraken2CloudConfig.from_file(args.config)
    extra_args = parse_extra_args(args.extra_args)

    cloud = merge_cloud_config(config.cloud, args, extract_credentials(args))
    kraken2 = Kraken2Config(
        db_path=args.db_path or config.kraken2.db_path,
        confidence=args.confidence if args.confidence is not None else config.kraken2.confidence,
        minimum_base_quality=(
            args.minimum_base_quality
            if args.minimum_base_quality is not None
            else config.kraken2.minimum_base_quality
        ),
        num_threads=args.num_threads if args.num_threads is not None else config.kraken2.num_threads,
        extra_args=extra_args if extra_args is not None else config.kraken2.extra_args,
    )
    run = merge_run_config(config.run, args)
    return Kraken2CloudConfig(cloud=cloud, kraken2=kraken2, run=run)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Kraken2 with cloud storage I/O (config required)",
        epilog="Copy nexus_cloud/config.kraken2.example.json and pass --config.",
    )
    add_cloud_args(parser)
    parser.add_argument("--db-path", help="Override kraken2.db_path")
    parser.add_argument("--confidence", type=float)
    parser.add_argument("--minimum-base-quality", type=int)
    parser.add_argument("--num-threads", type=int)
    parser.add_argument("--extra-args", help="Override kraken2.extra_args as JSON array")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        config = _config_from_args(args)
        runner = Kraken2Runner(config.to_storage(), config.kraken2)
        jobs = config.run.jobs

        if len(jobs) == 1 and config.run.pool_workers == 1:
            uri, report_uri = runner.run(
                jobs[0].input_key, jobs[0].output_key, report_key=jobs[0].report_key
            )
            print(f"Kraken2 complete. Output: {uri}")
            if report_uri:
                print(f"Report: {report_uri}")
            return 0

        return print_batch_results(
            runner.run_batch(jobs, pool_workers=config.run.pool_workers),
            "Kraken2",
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
