#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NCBI Data Retriever (standalone)

Author: Amina Jackson, Intechgambit
email: developers@intechgambit.com
Date: 2026-05-13
License: GPL-3.0 license

Usage:
  - Fetch GenBank records for a search term from the nucleotide database and save FASTA:
      python ncbi_data_retriever.py --db nuccore --term "COX1[Gene] AND Homo sapiens[Organism]" \
        --rettype fasta --retmode text --retmax 50 --out cox1_hs.fasta

  - Fetch JSON summary for protein search:
      python ncbi_data_retriever.py --db protein --term "kinase Homo sapiens" --retmode json --rettype docsum \
        --retmax 20 --out results.json

  - Provide an NCBI API key to increase rate limits:
      python ncbi_data_retriever.py --db nuccore --term "ribosomal RNA" --api-key YOUR_KEY --retmax 10 --out rRNA.gb

Notes:
  - This tool calls NCBI E-utilities (esearch → efetch or esummary) over HTTPS using requests.
  - No UI dependencies. Only needs the 'requests' package. If not installed, shows a clear error.
  - Be mindful of NCBI usage policies: include email, throttle requests, and use an API key when possible.
"""

import argparse
import sys
import time
from pathlib import Path

# Try to import requests with a friendly message if missing
try:
    import requests
except Exception as e:
    requests = None

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def esearch_ids(db, term, api_key=None, email=None, retmax=100):
    # Build esearch URL
    params = {
        'db': db,
        'term': term,
        'retmax': retmax,
        'retmode': 'json',
    }
    if api_key:
        params['api_key'] = api_key
    if email:
        params['email'] = email
    resp = requests.get(f"{EUTILS_BASE}/esearch.fcgi", params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    ids = data.get('esearchresult', {}).get('idlist', [])
    return ids


def efetch_or_esummary(db, ids, rettype='fasta', retmode='text', api_key=None, email=None):
    # Choose efetch or esummary based on rettype/retmode
    if rettype == 'docsum' or retmode == 'json':
        endpoint = 'esummary.fcgi'
        params = {'db': db, 'id': ','.join(ids), 'retmode': retmode or 'json'}
    else:
        endpoint = 'efetch.fcgi'
        params = {'db': db, 'id': ','.join(ids), 'rettype': rettype, 'retmode': retmode}
    if api_key:
        params['api_key'] = api_key
    if email:
        params['email'] = email
    resp = requests.get(f"{EUTILS_BASE}/{endpoint}", params=params, timeout=120)
    resp.raise_for_status()
    return resp.text if retmode != 'json' else resp.json()


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Retrieve data from NCBI using E-utilities (standalone)")
    ap.add_argument('--db', required=True, help='NCBI database (e.g., nuccore, protein, bioproject, pubmed)')
    ap.add_argument('--term', required=True, help='E-utilities search term')
    ap.add_argument('--retmax', type=int, default=100, help='Max records to retrieve (default 100)')
    ap.add_argument('--rettype', default='fasta', help='Return type for efetch (e.g., fasta, gb, docsum)')
    ap.add_argument('--retmode', default='text', help='Return mode (text, xml, json)')
    ap.add_argument('--api-key', help='NCBI API key for higher rate limits')
    ap.add_argument('--email', help='Your contact email per NCBI policy')
    ap.add_argument('--sleep', type=float, default=0.34, help='Delay between calls (seconds)')
    ap.add_argument('--out', required=True, help='Output file path')
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    if requests is None:
        print("ERROR: Python package 'requests' is required. Install with: pip install requests", file=sys.stderr)
        return 1

    try:
        ids = esearch_ids(args.db, args.term, api_key=args.api_key, email=args.email, retmax=args.retmax)
        if not ids:
            print("No IDs returned by esearch. Nothing to fetch.")
            return 0
        # Be polite with a small delay
        time.sleep(max(0.0, args.sleep))
        data = efetch_or_esummary(args.db, ids, rettype=args.rettype, retmode=args.retmode, api_key=args.api_key, email=args.email)
        out_path = Path(args.out)
        # Write either text or JSON
        mode = 'w'
        if isinstance(data, (dict, list)):
            import json
            txt = json.dumps(data, indent=2)
        else:
            txt = data
        out_path.write_text(txt, encoding='utf-8')
        print(f"Wrote: {out_path.resolve()}  (records: {len(ids)})")
        return 0
    except requests.HTTPError as he:
        print(f"HTTP error: {he}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
