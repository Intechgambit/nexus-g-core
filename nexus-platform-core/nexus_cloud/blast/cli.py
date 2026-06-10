#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NCBI BLAST Cloud CLI

Author: Amina Jackson, Intechgambit
email: developers@intechgambit.com
Date: 2026-06-10
License: GPL-3.0 license

Usage:
  python -m nexus_cloud.blast --config nexus_cloud/config.example.json

Notes:
  - --config is required. All parameters are read from the config file.
  - CLI flags only override values from the loaded config.
"""

from __future__ import annotations

import argparse
import sys

from nexus_cloud.blast.runner import BlastConfig, BlastRunner
from nexus_cloud.common.cli import add_cloud_args, extract_credentials, print_batch_results
from nexus_cloud.common.config_cli import (
    merge_cloud_config,
    merge_run_config,
    parse_extra_args,
    require_config_path,
)
from nexus_cloud.config import NexusCloudConfig


def _config_from_args(args: argparse.Namespace) -> NexusCloudConfig:
    require_config_path(args, "BLAST")
    config = NexusCloudConfig.from_file(args.config)
    extra_args = parse_extra_args(args.extra_args)

    cloud = merge_cloud_config(config.cloud, args, extract_credentials(args))
    blast = BlastConfig(
        db_path=args.db_path or config.blast.db_path,
        program=args.program or config.blast.program,
        evalue=args.evalue if args.evalue is not None else config.blast.evalue,
        word_size=args.word_size if args.word_size is not None else config.blast.word_size,
        num_threads=args.num_threads if args.num_threads is not None else config.blast.num_threads,
        outfmt=args.outfmt or config.blast.outfmt,
        extra_args=extra_args if extra_args is not None else config.blast.extra_args,
    )
    run = merge_run_config(config.run, args)
    return NexusCloudConfig(cloud=cloud, blast=blast, run=run)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run NCBI BLAST with cloud storage I/O (config required)",
        epilog="Copy nexus_cloud/config.example.json and pass --config.",
    )
    add_cloud_args(parser)
    parser.add_argument("--db-path", help="Override blast.db_path")
    parser.add_argument("--program", choices=["blastn", "blastp", "blastx", "tblastn", "tblastx"])
    parser.add_argument("--evalue", type=float)
    parser.add_argument("--word-size", type=int)
    parser.add_argument("--num-threads", type=int)
    parser.add_argument("--outfmt")
    parser.add_argument("--extra-args", help="Override blast.extra_args as JSON array")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        config = _config_from_args(args)
        runner = BlastRunner(config.to_storage(), config.blast)
        jobs = [(job.input_key, job.output_key) for job in config.run.jobs]

        if len(jobs) == 1 and config.run.pool_workers == 1:
            remote_uri = runner.run(jobs[0][0], jobs[0][1])
            print(f"BLAST complete. Output uploaded to: {remote_uri}")
            return 0

        return print_batch_results(
            runner.run_batch(jobs, pool_workers=config.run.pool_workers),
            "BLAST",
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
