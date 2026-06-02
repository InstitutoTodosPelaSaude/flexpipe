#!/usr/bin/env python3
"""Download RSV-A metadata and sequences from Pathoplexus via LAPIS."""

import argparse
import os
import sys
import time
import requests
import yaml


def load_config(config_path):
    with open(config_path) as f:
        return yaml.safe_load(f)


def build_url(base_url, organism, endpoint):
    return f"{base_url.rstrip('/')}/{organism}/sample/{endpoint}"


def base_params(min_date, min_completeness):
    p = {"versionStatus": "LATEST_VERSION"}
    if min_date:
        p["sampleCollectionDateRangeLowerFrom"] = min_date
    if min_completeness is not None:
        p["completenessFrom"] = min_completeness
    return p


def fetch_metadata(url, auth_token=None, min_date=None, min_completeness=None, chunk_size=10000):
    headers = {"Accept": "text/tab-separated-values"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    params = base_params(min_date, min_completeness)
    params.update({"downloadAsFile": "false", "dataFormat": "TSV",
                   "limit": chunk_size, "offset": 0})

    rows = []
    header = None

    while True:
        print(f"  Fetching metadata: offset={params['offset']}", flush=True)
        resp = requests.get(url, headers=headers, params=params, timeout=120)
        resp.raise_for_status()

        lines = resp.text.strip().splitlines()
        if not lines:
            break

        if header is None:
            header = lines[0]
            data_lines = lines[1:]
        else:
            data_lines = lines[1:]

        if not data_lines:
            break

        rows.extend(data_lines)

        if len(data_lines) < chunk_size:
            break

        params["offset"] += chunk_size
        time.sleep(0.5)

    return header, rows


def fetch_sequences(url, auth_token=None, min_date=None, min_completeness=None, chunk_size=10000):
    headers = {"Accept": "text/x-fasta"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    params = base_params(min_date, min_completeness)
    params.update({"limit": chunk_size, "offset": 0})

    all_fasta = []

    while True:
        print(f"  Fetching sequences: offset={params['offset']}", flush=True)
        resp = requests.get(url, headers=headers, params=params, timeout=300)
        resp.raise_for_status()

        text = resp.text.strip()
        if not text:
            break

        entries = [e for e in text.split(">") if e.strip()]
        all_fasta.extend(entries)

        if len(entries) < chunk_size:
            break

        params["offset"] += chunk_size
        time.sleep(0.5)

    return all_fasta


def main():
    parser = argparse.ArgumentParser(description="Fetch RSV-A data from Pathoplexus LAPIS")
    parser.add_argument("--config", required=True)
    parser.add_argument("--metadata-output", required=True)
    parser.add_argument("--sequences-output", required=True)
    args = parser.parse_args()

    cfg = load_config(args.config)
    ppx = cfg.get("pathoplexus", {})
    sub = cfg.get("subsampling", {})

    base_url         = ppx.get("base_url", "https://lapis.pathoplexus.org")
    organism         = ppx.get("organism", "rsv-a")
    meta_ep          = ppx.get("metadata_endpoint", "details")
    seq_ep           = ppx.get("sequences_endpoint", "unalignedNucleotideSequences")
    auth_token       = ppx.get("auth_token", "") or None
    min_completeness = ppx.get("min_completeness", None)

    # min_date: prefer explicit pathoplexus.min_date, fall back to subsampling.min_year
    min_date = ppx.get("min_date") or None
    if not min_date:
        min_year = sub.get("min_year")
        if min_year:
            min_date = f"{min_year}-01-01"

    meta_url = build_url(base_url, organism, meta_ep)
    seq_url  = build_url(base_url, organism, seq_ep)

    os.makedirs(os.path.dirname(args.metadata_output), exist_ok=True)
    os.makedirs(os.path.dirname(args.sequences_output), exist_ok=True)

    print(f"Filters: min_date={min_date}, min_completeness={min_completeness}")

    # --- metadata ---
    print(f"\nDownloading metadata from:\n  {meta_url}")
    header, rows = fetch_metadata(meta_url, auth_token, min_date, min_completeness)

    if header is None:
        print("ERROR: No metadata returned from Pathoplexus.", file=sys.stderr)
        sys.exit(1)

    with open(args.metadata_output, "w") as fh:
        fh.write(header + "\n")
        for row in rows:
            fh.write(row + "\n")

    print(f"Metadata: {len(rows)} records → {args.metadata_output}")

    # --- sequences ---
    print(f"\nDownloading sequences from:\n  {seq_url}")
    fasta_entries = fetch_sequences(seq_url, auth_token, min_date, min_completeness)

    with open(args.sequences_output, "w") as fh:
        for entry in fasta_entries:
            fh.write(">" + entry)
            if not entry.endswith("\n"):
                fh.write("\n")

    print(f"Sequences: {len(fasta_entries)} records → {args.sequences_output}")


if __name__ == "__main__":
    main()
