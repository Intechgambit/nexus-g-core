"""Shared CLI helpers for Nexus Cloud tools."""

from __future__ import annotations

import argparse


def add_cloud_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config", "-c",
        required=True,
        help="Path to JSON or YAML config file (required)",
    )
    parser.add_argument("--provider", choices=["aws", "gcp", "azure"], help="Cloud provider")
    parser.add_argument("--bucket-path", help="Bucket/container URI or name with optional prefix")
    parser.add_argument("--input", dest="input_key", help="Cloud object key for primary input")
    parser.add_argument("--input2", dest="input2_key", help="Cloud object key for R2 reads (paired-end)")
    parser.add_argument("--output", dest="output_key", help="Cloud object key for primary output")
    parser.add_argument("--report", dest="report_key", help="Cloud object key for report output (Kraken2)")
    parser.add_argument(
        "--pool-workers",
        type=int,
        help="Parallel jobs for batch runs",
    )
    parser.add_argument("--aws-access-key-id")
    parser.add_argument("--aws-secret-access-key")
    parser.add_argument("--aws-session-token")
    parser.add_argument("--region-name")
    parser.add_argument("--profile-name")
    parser.add_argument("--credentials-path", help="Path to GCP service-account JSON key")
    parser.add_argument("--project-id")
    parser.add_argument("--connection-string")
    parser.add_argument("--account-name")
    parser.add_argument("--account-key")
    parser.add_argument("--account-url")


def extract_credentials(args: argparse.Namespace) -> dict:
    provider = (args.provider or "").lower()
    if provider == "aws":
        creds = {}
        for key, attr in [
            ("aws_access_key_id", "aws_access_key_id"),
            ("aws_secret_access_key", "aws_secret_access_key"),
            ("aws_session_token", "aws_session_token"),
            ("region_name", "region_name"),
            ("profile_name", "profile_name"),
        ]:
            value = getattr(args, attr, None)
            if value:
                creds[key] = value
        return creds
    if provider == "gcp":
        creds = {}
        if args.credentials_path:
            creds["credentials_path"] = args.credentials_path
        if args.project_id:
            creds["project_id"] = args.project_id
        return creds
    if provider == "azure":
        creds = {}
        for key, attr in [
            ("connection_string", "connection_string"),
            ("account_name", "account_name"),
            ("account_key", "account_key"),
            ("account_url", "account_url"),
        ]:
            value = getattr(args, attr, None)
            if value:
                creds[key] = value
        return creds
    return {}


def print_batch_results(results, tool_name: str) -> int:
    import sys

    succeeded = sum(1 for r in results if r.success)
    failed = len(results) - succeeded
    for result in results:
        if result.success:
            msg = f"OK  {result.input_key} -> {result.remote_uri}"
            if result.report_uri:
                msg += f" (report: {result.report_uri})"
            print(msg)
        else:
            print(f"ERR {result.input_key}: {result.error}", file=sys.stderr)
    print(f"{tool_name} batch complete: {succeeded} succeeded, {failed} failed")
    return 0 if failed == 0 else 1
