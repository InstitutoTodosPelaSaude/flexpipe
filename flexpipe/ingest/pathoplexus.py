"""
Fetch metadata and sequences from Pathoplexus via the LAPIS API.

Outputs in Pathoplexus-style (PPX) TSV format so that
``merge_local_sequences`` and ``curate`` can process Pathoplexus and NCBI
data uniformly.

Extracted from ``scripts/fetch_pathoplexus.py`` with the following fixes:
- Module docstring updated (was "Download RSV-A metadata…" — stale RSV label).
- Argparse description updated (was "Fetch RSV-A data…").
- Default ``organism`` removed from CLI fallback (always read from config).
- ``print()`` replaced with ``logging``.
"""

import argparse
import logging
import os
import sys
import time

import requests
import yaml

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """Load and return the pipeline config YAML."""
    with open(config_path) as f:
        return yaml.safe_load(f)


def build_url(base_url: str, organism: str, endpoint: str) -> str:
    """Construct a LAPIS API URL."""
    return f"{base_url.rstrip('/')}/{organism}/sample/{endpoint}"


def base_params(min_date, min_completeness) -> dict:
    """Build the common LAPIS query parameters."""
    p = {"versionStatus": "LATEST_VERSION"}
    if min_date:
        p["sampleCollectionDateRangeLowerFrom"] = min_date
    if min_completeness is not None:
        p["completenessFrom"] = min_completeness
    return p


def fetch_metadata(
    url: str,
    auth_token=None,
    min_date=None,
    min_completeness=None,
    chunk_size: int = 10000,
):
    """Paginate through the LAPIS metadata endpoint and return (header, rows).

    Args:
        url: LAPIS ``/sample/details`` URL.
        auth_token: Optional Bearer token for restricted data.
        min_date: Minimum collection date filter (ISO ``YYYY-MM-DD``).
        min_completeness: Minimum genome completeness fraction.
        chunk_size: Records per paginated request.

    Returns:
        Tuple ``(header_line, data_lines)`` where *header_line* is the TSV
        column header and *data_lines* is a list of TSV row strings.
    """
    headers = {"Accept": "text/tab-separated-values"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    params = base_params(min_date, min_completeness)
    params.update({
        "downloadAsFile": "false",
        "dataFormat": "TSV",
        "limit": chunk_size,
        "offset": 0,
    })

    rows = []
    header = None

    while True:
        logger.info("Fetching metadata: offset=%d", params["offset"])
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


def fetch_sequences(
    url: str,
    auth_token=None,
    min_date=None,
    min_completeness=None,
    chunk_size: int = 10000,
) -> list:
    """Paginate through the LAPIS sequences endpoint and return FASTA entry strings.

    Args:
        url: LAPIS ``/sample/unalignedNucleotideSequences`` URL.
        auth_token: Optional Bearer token.
        min_date: Minimum collection date filter.
        min_completeness: Minimum genome completeness fraction.
        chunk_size: Records per paginated request.

    Returns:
        List of FASTA entry strings (without the leading ``>``).
    """
    headers = {"Accept": "text/x-fasta"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    params = base_params(min_date, min_completeness)
    params.update({"limit": chunk_size, "offset": 0})

    all_fasta = []

    while True:
        logger.info("Fetching sequences: offset=%d", params["offset"])
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


def main() -> None:
    """Entry point for ``flexpipe-fetch-pathoplexus``."""
    parser = argparse.ArgumentParser(
        description="Fetch metadata and sequences from Pathoplexus via LAPIS"
    )
    parser.add_argument("--config",           required=True)
    parser.add_argument("--metadata-output",  required=True)
    parser.add_argument("--sequences-output", required=True)
    args = parser.parse_args()

    from flexpipe.logging_setup import configure_logging
    configure_logging()

    cfg = load_config(args.config)
    ppx = cfg.get("pathoplexus", {})
    sub = cfg.get("subsampling", {})

    base_url         = ppx.get("base_url", "https://lapis.pathoplexus.org")
    organism         = ppx.get("organism")
    if not organism:
        logger.error("pathoplexus.organism is required in config.yaml")
        sys.exit(1)
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

    os.makedirs(os.path.dirname(args.metadata_output),  exist_ok=True)
    os.makedirs(os.path.dirname(args.sequences_output), exist_ok=True)

    logger.info("Filters: min_date=%s, min_completeness=%s", min_date, min_completeness)

    # Metadata
    logger.info("Downloading metadata from: %s", meta_url)
    header, rows = fetch_metadata(meta_url, auth_token, min_date, min_completeness)

    if header is None:
        logger.error("No metadata returned from Pathoplexus.")
        sys.exit(1)

    with open(args.metadata_output, "w") as fh:
        fh.write(header + "\n")
        for row in rows:
            fh.write(row + "\n")

    logger.info("Metadata: %d records → %s", len(rows), args.metadata_output)

    # Sequences
    logger.info("Downloading sequences from: %s", seq_url)
    fasta_entries = fetch_sequences(seq_url, auth_token, min_date, min_completeness)

    with open(args.sequences_output, "w") as fh:
        for entry in fasta_entries:
            fh.write(">" + entry)
            if not entry.endswith("\n"):
                fh.write("\n")

    logger.info("Sequences: %d records → %s", len(fasta_entries), args.sequences_output)


if __name__ == "__main__":
    main()
