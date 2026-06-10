#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimap2 Cloud CLI — config-driven cloud alignment."""

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
from nexus_cloud.minimap2.runner import Minimap2CloudConfig, Minimap2Config, Minimap2Runner


def _config_from_args(args: argparse.Namespace) -> Minimap2CloudConfig:
    require_config_path(args, "Minimap2")
    config = Minimap2CloudConfig.from_file(args.config)
    extra_args = parse_extra_args(args.extra_args)

    cloud = merge_cloud_config(config.cloud, args, extract_credentials(args))
    minimap2 = Minimap2Config(
        reference_path=args.reference_path or config.minimap2.reference_path,
        preset=args.preset or config.minimap2.preset,
        num_threads=args.num_threads if args.num_threads is not None else config.minimap2.num_threads,
        output_format=args.output_format or config.minimap2.output_format,
        extra_args=extra_args if extra_args is not None else config.minimap2.extra_args,
    )
    run = merge_run_config(config.run, args)
    return Minimap2CloudConfig(cloud=cloud, minimap2=minimap2, run=run)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Minimap2 with cloud storage I/O (config required)",
        epilog="Copy nexus_cloud/config.minimap2.example.json and pass --config.",
    )
    add_cloud_args(parser)
    parser.add_argument("--reference-path", help="Override minimap2.reference_path")
    parser.add_argument("--preset")
    parser.add_argument("--output-format", choices=["sam", "paf"])
    parser.add_argument("--num-threads", type=int)
    parser.add_argument("--extra-args", help="Override minimap2.extra_args as JSON array")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        config = _config_from_args(args)
        runner = Minimap2Runner(config.to_storage(), config.minimap2)
        jobs = config.run.jobs

        if len(jobs) == 1 and config.run.pool_workers == 1:
            uri = runner.run(jobs[0].input_key, jobs[0].output_key)
            print(f"Minimap2 complete. Output: {uri}")
            return 0

        return print_batch_results(
            runner.run_batch(jobs, pool_workers=config.run.pool_workers),
            "Minimap2",
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
