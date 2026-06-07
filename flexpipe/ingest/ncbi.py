"""
Fetch sequences and metadata from NCBI Entrez for use in the flexpipe pipeline.

Outputs in Pathoplexus-compatible (PPX) TSV format so that
``merge_local_sequences`` and ``curate`` can process Pathoplexus and NCBI
data uniformly.

Column mapping (GenBank → Pathoplexus):
    accession.version     → accessionVersion
    collection_date       → sampleCollectionDate
    country (parsed)      → geoLocCountry, geoLocAdmin1, geoLocAdmin2
    host                  → hostNameCommon
    authors               → authors
    fixed "OPEN"          → dataUseTerms
    fixed ""              → lineage   (Nextclade fills this later)
    fixed "NCBI"          → source

Extracted verbatim from ``scripts/fetch_ncbi.py``.
``print()`` calls replaced with ``logging``.
"""

import argparse
import logging
import os
import socket
import sys
import time
from http.client import IncompleteRead
from urllib.error import HTTPError, URLError

import pandas as pd
import yaml
from Bio import Entrez, SeqIO

logger = logging.getLogger(__name__)

BATCH_SIZE = 200
DELAY_SEC = 0.4  # ≤ 3 req/s without API key, ≤ 10 with API key


# ── Parsing helpers ───────────────────────────────────────────────────────────


_INSDC_MISSING_PREFIXES = (
    "missing",
    "not applicable",
    "not collected",
    "not provided",
    "restricted access",
    "n/a",
    "na",
)


def _normalize_insdc(value: str) -> str:
    """Return empty string for INSDC 'missing:*' / 'not applicable' sentinels.

    NCBI encodes absent metadata as 'missing: reason', 'not collected', etc.
    These are not real field values and must not be passed to augur curation.
    """
    v = (value or "").strip()
    if v.lower().split(":")[0].strip() in _INSDC_MISSING_PREFIXES:
        return ""
    return v


def parse_country_field(raw: str):
    """Parse NCBI country field ``'Country: Division, Location'`` → ``(country, div, loc)``."""
    country = division = location = ""
    if not raw:
        return country, division, location
    if ":" in raw:
        country, sub = raw.split(":", 1)
        country = country.strip()
        sub = sub.strip()
        if "," in sub:
            parts = [p.strip() for p in sub.split(",", 1)]
            division, location = parts[0], parts[1]
        else:
            division = sub
    else:
        country = raw.strip()
    return country, division, location


def parse_gb_record(rec) -> dict:
    """Extract a metadata dict from a BioPython GenBank SeqRecord.

    Returns a dict with PPX-compatible column names.
    """
    host = raw_country = collection_date = authors = ""

    for feature in rec.features:
        if feature.type == "source":
            host_q = feature.qualifiers.get("host") or [""]
            host = host_q[0] if host_q else ""
            # INSDC migrated from "country" to "geo_loc_name" qualifier (~2023)
            raw_country = (
                feature.qualifiers.get("geo_loc_name") or feature.qualifiers.get("country") or [""]
            )[0]
            cdate_q = feature.qualifiers.get("collection_date") or [""]
            collection_date = _normalize_insdc(cdate_q[0] if cdate_q else "")
            break

    for ref in rec.annotations.get("references", []):
        if ref.authors and not authors:
            first = ref.authors.split(",")[0].strip()
            authors = f"{first} et al"

    country, division, location = parse_country_field(_normalize_insdc(raw_country))

    return {
        "accessionVersion": rec.id,
        "sampleCollectionDate": collection_date,
        "geoLocCountry": country,
        "geoLocAdmin1": division,
        "geoLocAdmin2": location,
        "hostNameCommon": host,
        "authors": authors,
        "dataUseTerms": "OPEN",
        "lineage": "",
        "source": "NCBI",
    }


# ── NCBI search + fetch ───────────────────────────────────────────────────────


def _ncbi_date(value: str) -> str:
    return str(value).replace("-", "/")


def search_ncbi(
    taxid,
    min_length: int,
    max_length: int,
    min_date=None,
    max_date=None,
    extra_term=None,
):
    """Search NCBI Entrez and return ``(count, webenv, query_key)``."""
    query = f"txid{taxid}[Organism] {min_length}:{max_length}[SLEN]"
    if min_date or max_date:
        lower = _ncbi_date(min_date) if min_date else "1900/01/01"
        upper = _ncbi_date(max_date) if max_date else "3000/12/31"
        query += f" {lower}:{upper}[PDAT]"
    if extra_term:
        query += f" {extra_term}"
    logger.info("NCBI query: %s", query)

    handle = Entrez.esearch(db="nucleotide", term=query, idtype="acc", usehistory="y")
    result = Entrez.read(handle)
    handle.close()

    count = int(result["Count"])
    logger.info("Found %d records on NCBI.", count)
    return count, result["WebEnv"], result["QueryKey"]


def iter_records(count: int, webenv: str, query_key: str):
    """Yield BioPython SeqRecords from NCBI server history in batches, with retries."""
    _transient = (IncompleteRead, HTTPError, URLError, socket.error, OSError)
    for start in range(0, count, BATCH_SIZE):
        end = min(start + BATCH_SIZE, count)
        logger.info("Fetching records %d–%d / %d ...", start + 1, end, count)
        for attempt in range(1, 6):
            handle = None
            try:
                handle = Entrez.efetch(
                    db="nucleotide",
                    rettype="gb",
                    retmode="text",
                    retstart=start,
                    retmax=BATCH_SIZE,
                    webenv=webenv,
                    query_key=query_key,
                )
                records = list(SeqIO.parse(handle, "gb"))
                handle.close()
                break
            except _transient as exc:
                if handle is not None:
                    try:
                        handle.close()
                    except Exception:
                        pass
                if attempt < 5:
                    wait = 5 * attempt
                    logger.warning(
                        "Network error (%s), retry %d/5 in %ds...",
                        exc.__class__.__name__,
                        attempt,
                        wait,
                    )
                    time.sleep(wait)
                else:
                    raise
        yield from records
        time.sleep(DELAY_SEC)


# ── main ──────────────────────────────────────────────────────────────────────


def load_config(path: str) -> dict:
    """Load and return the pipeline config YAML."""
    with open(path) as f:
        return yaml.safe_load(f)


def main() -> None:
    """Entry point for ``flexpipe-fetch-ncbi``."""
    parser = argparse.ArgumentParser(
        description="Fetch sequences and metadata from NCBI for the flexpipe pipeline."
    )
    parser.add_argument("--config", required=True, help="Path to config/config.yaml")
    parser.add_argument("--metadata-output", required=True, help="Output TSV (PPX format)")
    parser.add_argument("--sequences-output", required=True, help="Output FASTA path")
    parser.add_argument("--run-date", required=False, default="", help="Upper publication date")
    args = parser.parse_args()

    from flexpipe.logging_setup import configure_logging

    configure_logging()

    cfg = load_config(args.config)
    ncbi = cfg.get("ncbi", {})
    sub = cfg.get("subsampling", {})

    taxid = ncbi.get("taxid")
    genome_size = ncbi.get("genome_size")
    email = ncbi.get("email", "") or os.environ.get("NCBI_EMAIL") or ""
    api_key = ncbi.get("api_key", "") or os.environ.get("NCBI_API_KEY") or None
    min_frac = float(ncbi.get("min_length", 0.7))
    max_frac = float(ncbi.get("max_length", 1.1))

    if not taxid:
        sys.exit("ERROR: ncbi.taxid is required in config.yaml")
    if not genome_size:
        sys.exit("ERROR: ncbi.genome_size is required in config.yaml")
    if not email:
        sys.exit(
            "ERROR: ncbi.email or NCBI_EMAIL is required for NCBI Entrez requests. "
            "Use a real contact email."
        )

    min_length = int(genome_size * min_frac)
    max_length = int(genome_size * max_frac)

    min_date = ncbi.get("min_date") or None
    if not min_date:
        min_year = sub.get("min_year")
        if min_year:
            min_date = str(min_year)

    extra_term = ncbi.get("extra_search_term") or None
    max_date = args.run_date or None

    Entrez.email = email  # type: ignore[assignment]
    if api_key:
        Entrez.api_key = api_key  # type: ignore[assignment]

    os.makedirs(os.path.dirname(os.path.abspath(args.metadata_output)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(args.sequences_output)), exist_ok=True)

    logger.info(
        "Length filter: %d–%d bp  |  min_date: %s",
        min_length,
        max_length,
        min_date or "none",
    )
    if max_date:
        logger.info("Upper publication-date bound: %s", max_date)
    if extra_term:
        logger.info("Extra search term: %s", extra_term)

    count, webenv, query_key = search_ncbi(
        taxid,
        min_length,
        max_length,
        min_date=min_date,
        max_date=max_date,
        extra_term=extra_term,
    )

    # Write empty outputs so Snakemake never fails on a 0-result query
    if count == 0:
        pd.DataFrame(
            columns=[
                "accessionVersion",
                "sampleCollectionDate",
                "geoLocCountry",
                "geoLocAdmin1",
                "geoLocAdmin2",
                "hostNameCommon",
                "authors",
                "dataUseTerms",
                "lineage",
                "source",
            ]
        ).to_csv(args.metadata_output, sep="\t", index=False)
        open(args.sequences_output, "w").close()
        logger.info("No records found — empty outputs written.")
        return

    rows = []
    n_seq = 0

    with open(args.sequences_output, "w") as fa:
        for rec in iter_records(count, webenv, query_key):
            rows.append(parse_gb_record(rec))
            fa.write(f">{rec.id}\n{rec.seq}\n")
            n_seq += 1

    df = pd.DataFrame(rows)
    df.to_csv(args.metadata_output, sep="\t", index=False)

    logger.info("Metadata:  %d records → %s", len(df), args.metadata_output)
    logger.info("Sequences: %d records  → %s", n_seq, args.sequences_output)


if __name__ == "__main__":
    main()
