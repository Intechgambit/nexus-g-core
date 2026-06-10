#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sequence Cluster from Data Tools (standalone)

Author: Amina Jackson, Intechgambit
email: developers@intechgambit.com
Date: 2026-05-13
License: GPL-3.0 license

Usage:
  - Cluster sequences from a FASTA file using a simple similarity threshold (0..1):
      python sequence_cluster.py --in sequences.fasta --informat fasta --threshold 0.9 --out clusters.tsv

  - Cluster sequences from CSV (id,sequence) and write clusters as TSV:
      python sequence_cluster.py --in seqs.csv --informat csv --threshold 0.85 --out clusters.tsv

  - Change similarity method to 'ratio' (default) or 'hamming' (requires equal lengths):
      python sequence_cluster.py --in seqs.fasta --informat fasta --method hamming --threshold 0.95 --out clusters.tsv

Notes:
  - Greedy single-link clustering: iterate sequences; assign to first cluster with similarity >= threshold;
    otherwise start a new cluster. Fast and simple, but order-dependent.
  - No UI dependencies. Standard library only.
  - Output TSV columns: cluster_id, member_id, sequence_length
"""

import argparse
import csv
from pathlib import Path
import sys
from difflib import SequenceMatcher

# I/O helpers reused from format_converter style

def read_fasta(path):
    seq_id = None
    seq_chunks = []
    with open(path, 'r', encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line:
                continue
            if line.startswith('>'):
                if seq_id is not None:
                    yield seq_id, ''.join(seq_chunks)
                seq_id = line[1:].strip().split()[0]
                seq_chunks = []
            else:
                seq_chunks.append(line.strip())
        if seq_id is not None:
            yield seq_id, ''.join(seq_chunks)


def read_delimited(path, delimiter=','):
    with open(path, 'r', encoding='utf-8') as fh:
        reader = csv.DictReader(fh, delimiter=delimiter)
        if 'id' not in reader.fieldnames or 'sequence' not in reader.fieldnames:
            raise ValueError("Input table must have 'id' and 'sequence' columns")
        for row in reader:
            yield row['id'], row['sequence']


def write_clusters_tsv(assignments, path):
    # assignments: list of (cluster_id, member_id, seqlen)
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh, delimiter='\t')
        w.writerow(['cluster_id', 'member_id', 'sequence_length'])
        for cid, mid, slen in assignments:
            w.writerow([cid, mid, slen])


# Similarity functions

def ratio_identity(a, b):
    # difflib's quick ratio gives a measure between 0 and 1
    return SequenceMatcher(None, a, b).ratio()


def hamming_identity(a, b):
    if len(a) != len(b):
        return 0.0  # cannot compare via Hamming if lengths differ
    same = sum(1 for x, y in zip(a, b) if x == y)
    return same / len(a) if a else 1.0


# Greedy single-link clustering

def greedy_cluster(items, threshold=0.9, method='ratio'):
    # items: list of (id, seq)
    sims = ratio_identity if method == 'ratio' else hamming_identity
    clusters = []  # list of dict: { 'rep_id': id, 'rep_seq': seq, 'members': [(id, seq)] }
    for sid, seq in items:
        placed = False
        for cl in clusters:
            # Compare against representative sequence (first member) for speed
            rep_seq = cl['rep_seq']
            if sims(seq, rep_seq) >= threshold:
                cl['members'].append((sid, seq))
                placed = True
                break
        if not placed:
            clusters.append({'rep_id': sid, 'rep_seq': seq, 'members': [(sid, seq)]})
    # Build assignments
    out = []
    for idx, cl in enumerate(clusters, start=1):
        for mid, mseq in cl['members']:
            out.append((idx, mid, len(mseq)))
    return out


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Greedy sequence clustering (standalone)")
    ap.add_argument('--in', dest='in_path', required=True, help='Input file path')
    ap.add_argument('--informat', required=True, choices=['fasta', 'csv', 'tsv'], help='Input format')
    ap.add_argument('--threshold', type=float, default=0.9, help='Similarity threshold between 0 and 1 (default 0.9)')
    ap.add_argument('--method', choices=['ratio', 'hamming'], default='ratio', help='Similarity method (default ratio)')
    ap.add_argument('--out', dest='out_path', required=True, help='Output TSV file with cluster assignments')
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if not (0.0 <= args.threshold <= 1.0):
        print("ERROR: --threshold must be between 0 and 1", file=sys.stderr)
        return 1

    # Load inputs
    if args.informat == 'fasta':
        items = list(read_fasta(args.in_path))
    elif args.informat == 'csv':
        items = list(read_delimited(args.in_path, delimiter=','))
    else:  # tsv
        items = list(read_delimited(args.in_path, delimiter='\t'))

    # Perform clustering
    try:
        assignments = greedy_cluster(items, threshold=args.threshold, method=args.method)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # Write output
    write_clusters_tsv(assignments, args.out_path)
    print(f"Wrote clusters: {Path(args.out_path).resolve()} (n={len(assignments)})")
    return 0


if __name__ == '__main__':
    sys.exit(main())
