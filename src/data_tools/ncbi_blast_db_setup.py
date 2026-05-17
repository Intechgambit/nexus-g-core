#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NCBI BLAST DB Setup (standalone)

Author: Amina Jackson, Intechgambit
email: developers@intechgambit.com
Date: 2026-05-13
License: GPL-3.0 license

Usage:
  - Create a BLAST database from a local FASTA file (requires makeblastdb in PATH):
      python ncbi_blast_db_setup.py --from-fasta sequences.fasta --dbtype nucl --out mydb --title "My DB"

  - Download a prebuilt BLAST database from NCBI (requires update_blastdb.pl or update_blastdb in PATH):
      python ncbi_blast_db_setup.py --download-nt --out-dir ./blastdb
      python ncbi_blast_db_setup.py --download-db nr --out-dir ./blastdb

  - Verify an existing database directory:
      python ncbi_blast_db_setup.py --verify ./blastdb/nt

Notes:
  - This script has no dependency on any UI components.
  - It uses only standard library and external BLAST+ command-line tools if available.
  - For downloads, either update_blastdb (new) or update_blastdb.pl (older) is needed.
"""

import argparse
import shutil
import subprocess
import sys
import os
from pathlib import Path

# Helper: run a command and stream output
def run(cmd):
    # Inline comments explain that we capture and forward stdout/stderr
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in proc.stdout:  # streamlines to console
        print(line, end="")
    return proc.wait()

# Helper: find an executable in PATH
def which_any(names):
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    return None

# Create BLAST DB from FASTA using makeblastdb
def make_db_from_fasta(fasta, dbtype, out, title=None, parse_seqids=False):
    makeblastdb = which_any(["makeblastdb"])  # rely on BLAST+ installed
    if not makeblastdb:
        print("ERROR: makeblastdb not found in PATH. Please install NCBI BLAST+.", file=sys.stderr)
        return 1
    cmd = [makeblastdb, "-in", str(fasta), "-dbtype", dbtype, "-out", str(out)]
    if title:
        cmd += ["-title", title]
    if parse_seqids:
        cmd += ["-parse_seqids"]  # allows using sequence IDs directly in BLAST queries
    return run(cmd)

# Download prebuilt BLAST DB using update_blastdb(.pl)
def download_blast_db(dbname, out_dir, decompress=True):
    updater = which_any(["update_blastdb", "update_blastdb.pl"])  # either new or perl script
    if not updater:
        print("ERROR: update_blastdb/update_blastdb.pl not found in PATH. Install BLAST+ data downloader.", file=sys.stderr)
        return 1
    cmd = [updater, "--decompress" if decompress else "--passive", dbname]
    # The new `update_blastdb` supports --decompress; for the .pl version this flag is also recognized.
    env = os.environ.copy()
    # Ensure downloads land in out_dir by changing CWD; tool saves into current dir
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading database '{dbname}' to {out_dir.resolve()} using {updater}")
    return run(["bash", "-lc", f"cd {out_dir.resolve()} && {' '.join(cmd)}"])  # use a shell to cd then run

# Verify that a BLAST DB exists (checks for common index files)
def verify_db(db_prefix):
    # For BLAST databases, multiple files share the same prefix with extensions like .nhr/.nin/.nsq or .phr/.pin/.psq
    prefix = Path(db_prefix)
    base = str(prefix)
    nucl_exts = [".nhr", ".nin", ".nsq"]
    prot_exts = [".phr", ".pin", ".psq"]
    found = any(Path(base + e).exists() for e in nucl_exts + prot_exts)
    print(f"Checking {base} -> {'FOUND' if found else 'MISSING'}")
    return 0 if found else 2

def parse_args(argv=None):
    p = argparse.ArgumentParser(description="NCBI BLAST DB setup helper (standalone)")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-fasta", help="Path to input FASTA to build a BLAST DB from")
    src.add_argument("--download-nt", action="store_true", help="Shorthand to download the 'nt' database")
    src.add_argument("--download-db", help="Download the named prebuilt DB (e.g., nt, nr, taxdb)")
    p.add_argument("--dbtype", choices=["nucl", "prot"], default="nucl", help="Database type for --from-fasta")
    p.add_argument("--out", help="Output DB prefix (for --from-fasta)")
    p.add_argument("--title", help="DB title (optional, for --from-fasta)")
    p.add_argument("--parse-seqids", action="store_true", help="Pass -parse_seqids to makeblastdb")
    p.add_argument("--out-dir", default=".", help="Directory to place downloaded DB (for --download-*)")
    p.add_argument("--verify", help="Verify an existing DB prefix (path without extension)")
    return p.parse_args(argv)

def main(argv=None):
    args = parse_args(argv)

    # If verifying only, do it and exit
    if args.verify:
        return verify_db(args.verify)

    if args.from_fasta:
        if not args.out:
            print("ERROR: --out is required with --from-fasta", file=sys.stderr)
            return 1
        return make_db_from_fasta(args.from_fasta, args.dbtype, args.out, args.title, args.parse_seqids)

    # Determine db name for download
    if args.download_nt:
        dbname = "nt"
    else:
        dbname = args.download_db
    if dbname:
        return download_blast_db(dbname, args.out_dir)

    print("Nothing to do. See --help for usage.", file=sys.stderr)
    return 1

if __name__ == "__main__":
    sys.exit(main())
