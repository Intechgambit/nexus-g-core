#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bowtie2 Cloud CLI — config-driven cloud alignment."""

from __future__ import annotations

import argparse
import sys

from nexus_cloud.bowtie2.runner import Bowtie2CloudConfig, Bowtie2Config, Bowtie2Runner
from nexus_cloud.common.cli import add_cloud_args, extract_credentials, print_batch_results
from nexus_cloud.common.config_cli import (
    merge_cloud_config,
    merge_run_config,
    parse_extra_args,
    require_config_path,
)


def _config_from_args(args: argparse.Namespace) -> Bowtie2CloudConfig:
    require_config_path(args, "Bowtie2")
    config = Bowtie2CloudConfig.from_file(args.config)
    extra_args = parse_extra_args(args.extra_args)

    cloud = merge_cloud_config(config.cloud, args, extract_credentials(args))
    bowtie2 = Bowtie2Config(
        index_path=args.index_path or config.bowtie2.index_path,
        mode=args.mode or config.bowtie2.mode,
        num_threads=args.num_threads if args.num_threads is not None else config.bowtie2.num_threads,
        extra_args=extra_args if extra_args is not None else config.bowtie2.extra_args,
    )
    run = merge_run_config(config.run, args)

    if bowtie2.mode == "paired":
        for job in run.jobs:
            if not job.input2_key:
                raise ValueError("bowtie2.mode=paired requires input2 on each run job")

    return Bowtie2CloudConfig(cloud=cloud, bowtie2=bowtie2, run=run)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Bowtie2 with cloud storage I/O (config required)",
        epilog="Copy nexus_cloud/config.bowtie2.example.json and pass --config.",
    )
    add_cloud_args(parser)
    parser.add_argument("--index-path", help="Override bowtie2.index_path")
    parser.add_argument("--mode", choices=["single", "paired"])
    parser.add_argument("--num-threads", type=int)
    parser.add_argument("--extra-args", help="Override bowtie2.extra_args as JSON array")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        config = _config_from_args(args)
        runner = Bowtie2Runner(config.to_storage(), config.bowtie2)
        jobs = config.run.jobs

        if len(jobs) == 1 and config.run.pool_workers == 1:
            uri = runner.run(jobs[0].input_key, jobs[0].output_key, input2_key=jobs[0].input2_key)
            print(f"Bowtie2 complete. Output: {uri}")
            return 0

        return print_batch_results(
            runner.run_batch(jobs, pool_workers=config.run.pool_workers),
            "Bowtie2",
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
