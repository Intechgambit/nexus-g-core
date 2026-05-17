#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Format Converter for Biological Sequences (standalone)

Author: Amina Jackson, Intechgambit
email: developers@intechgamit.com
Date: 2026-05-13
License: GPL-3.0 license

Usage:
  - Convert FASTA to FASTQ using a fixed dummy quality (lossy, for tools requiring FASTQ):
      python format_converter.py --in sequences.fasta --informat fasta --out sequences.fastq --outformat fastq \
        --dummy-quality "I"

  - Convert FASTQ to FASTA:
      python format_converter.py --in reads.fastq --informat fastq --out reads.fasta --outformat fasta

  - Convert CSV/TSV (columns: id,sequence) to FASTA:
      python format_converter.py --in seqs.csv --informat csv --out seqs.fasta --outformat fasta

  - Convert FASTA to CSV:
      python format_converter.py --in seqs.fasta --informat fasta --out seqs.csv --outformat csv

Notes:
  - This script is UI-independent and uses only the Python standard library.
  - It supports: fasta, fastq, csv, tsv as input/output formats.
  - CSV/TSV are expected to have a header with at least 'id' and 'sequence' columns.
"""

import argparse
import csv
from pathlib import Path
import sys

# Minimal FASTA parser (standard library only)
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
                seq_id = line[1:].strip().split()[0]  # take first token as ID
                seq_chunks = []
            else:
                seq_chunks.append(line.strip())
        if seq_id is not None:
            yield seq_id, ''.join(seq_chunks)

# Minimal FASTQ parser
def read_fastq(path):
    with open(path, 'r', encoding='utf-8') as fh:
        while True:
            header = fh.readline()
            if not header:
                break
            seq = fh.readline()
            plus = fh.readline()
            qual = fh.readline()
            if not (seq and plus and qual):
                raise ValueError("Malformed FASTQ: unexpected EOF")
            if not header.startswith('@') or not plus.startswith('+'):
                raise ValueError("Malformed FASTQ: missing @/+ lines")
            seq_id = header[1:].strip().split()[0]
            yield seq_id, seq.rstrip('\n'), qual.rstrip('\n')

# Writers
def write_fasta(items, path):
    with open(path, 'w', encoding='utf-8') as out:
        for seq_id, seq in items:
            out.write(f'>{seq_id}\n')
            # wrap at 80 chars for readability
            for i in range(0, len(seq), 80):
                out.write(seq[i:i+80] + '\n')


def write_fastq(items, path):
    with open(path, 'w', encoding='utf-8') as out:
        for seq_id, seq, qual in items:
            if len(qual) != len(seq):
                raise ValueError(f"Quality length != sequence length for {seq_id}")
            out.write(f'@{seq_id}\n{seq}\n+\n{qual}\n')


def write_delimited(items, path, delimiter=','):
    # items are tuples (id, sequence)
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        writer = csv.writer(fh, delimiter=delimiter)
        writer.writerow(['id', 'sequence'])
        for seq_id, seq in items:
            writer.writerow([seq_id, seq])


def read_delimited(path, delimiter=','):
    with open(path, 'r', encoding='utf-8') as fh:
        reader = csv.DictReader(fh, delimiter=delimiter)
        if 'id' not in reader.fieldnames or 'sequence' not in reader.fieldnames:
            raise ValueError("Input table must have 'id' and 'sequence' columns")
        for row in reader:
            yield row['id'], row['sequence']


def convert(in_path, informat, out_path, outformat, dummy_quality_char='I'):
    # Normalize to lowercase
    informat = informat.lower()
    outformat = outformat.lower()

    # Load input into a uniform structure
    if informat == 'fasta':
        fasta_items = list(read_fasta(in_path))  # [(id, seq)]
    elif informat == 'fastq':
        fastq_items = list(read_fastq(in_path))  # [(id, seq, qual)]
    elif informat == 'csv':
        fasta_items = list(read_delimited(in_path, delimiter=','))  # [(id, seq)]
    elif informat == 'tsv':
        fasta_items = list(read_delimited(in_path, delimiter='\t'))
    else:
        raise ValueError("Unsupported --informat. Choose from: fasta, fastq, csv, tsv")

    # Convert depending on output format
    if outformat == 'fasta':
        if informat == 'fastq':
            fasta_items = [(sid, seq) for sid, seq, _ in fastq_items]
        write_fasta(fasta_items, out_path)
    elif outformat == 'fastq':
        if informat == 'fastq':
            write_fastq(fastq_items, out_path)
        else:
            # Create dummy qualities of a single char repeated to sequence length
            conv = []
            for sid, seq in fasta_items:
                qual = dummy_quality_char * len(seq)
                conv.append((sid, seq, qual))
            write_fastq(conv, out_path)
    elif outformat == 'csv':
        if informat == 'fastq':
            fasta_items = [(sid, seq) for sid, seq, _ in fastq_items]
        write_delimited(fasta_items, out_path, delimiter=',')
    elif outformat == 'tsv':
        if informat == 'fastq':
            fasta_items = [(sid, seq) for sid, seq, _ in fastq_items]
        write_delimited(fasta_items, out_path, delimiter='\t')
    else:
        raise ValueError("Unsupported --outformat. Choose from: fasta, fastq, csv, tsv")


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Convert between FASTA/FASTQ and CSV/TSV (standalone)")
    ap.add_argument('--in', dest='in_path', required=True, help='Input file path')
    ap.add_argument('--informat', required=True, choices=['fasta', 'fastq', 'csv', 'tsv'], help='Input format')
    ap.add_argument('--out', dest='out_path', required=True, help='Output file path')
    ap.add_argument('--outformat', required=True, choices=['fasta', 'fastq', 'csv', 'tsv'], help='Output format')
    ap.add_argument('--dummy-quality', default='I', help='Single character used for FASTA->FASTQ quality (default: I)')
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        convert(args.in_path, args.informat, args.out_path, args.outformat, args.dummy_quality)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    # Success
    out = Path(args.out_path)
    print(f"Wrote: {out.resolve()}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
