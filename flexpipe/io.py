"""
Shared I/O utilities for reading and writing tables and FASTA files.

Provides a single `load_table` implementation that previously existed as
copy-pasted helpers in `get_coordinates.py`, `generate_name2hue.py`, and
`colour_maker.py`.
"""

import logging
from pathlib import Path
from typing import Union

import pandas as pd
from Bio import SeqIO

logger = logging.getLogger(__name__)


def load_table(
    path: Union[str, Path],
    dtype: str = "str",
    fillna: str = "",
    **kwargs,
) -> pd.DataFrame:
    """Load a tabular file (TSV, CSV, XLS, XLSX) into a DataFrame.

    Args:
        path: Path to the file.
        dtype: dtype passed to pandas reader (default ``"str"`` keeps all values as strings).
        fillna: String to fill NaN values with after loading (default ``""``).
        **kwargs: Additional keyword arguments forwarded to the underlying pandas reader.

    Returns:
        DataFrame with NaN values replaced by *fillna*.

    Raises:
        ValueError: If the file extension is not one of tsv, csv, xls, xlsx.
    """
    p = Path(path)
    suffix = p.suffix.lower().lstrip(".")
    if suffix == "tsv":
        df = pd.read_csv(p, encoding="utf-8", sep="\t", dtype=dtype, **kwargs)
    elif suffix == "csv":
        df = pd.read_csv(p, encoding="utf-8", sep=",", dtype=dtype, **kwargs)
    elif suffix in ("xls", "xlsx"):
        df = pd.read_excel(p, index_col=None, header=0, sheet_name=0, dtype=dtype, **kwargs)
    else:
        raise ValueError(f"Unsupported file format '{p.suffix}'. Expected: .tsv, .csv, .xls, .xlsx")
    df.fillna(fillna, inplace=True)
    logger.debug("Loaded %d rows from %s", len(df), p)
    return df


def load_tsv(
    path: Union[str, Path],
    dtype: str = "str",
    fillna: str = "",
    **kwargs,
) -> pd.DataFrame:
    """Convenience wrapper for loading a TSV file.

    Always reads *path* as tab-separated text regardless of extension. This is
    intentionally smaller than :func:`load_table` for call sites that already
    know their input is TSV-like.
    """
    p = Path(path)
    return pd.read_csv(p, encoding="utf-8", sep="\t", dtype=dtype, **kwargs).fillna(fillna)


def read_fasta_ids(path: Union[str, Path]) -> set:
    """Return the set of sequence IDs (first whitespace-delimited token) in a FASTA file."""
    return {rec.id.split()[0] for rec in SeqIO.parse(str(path), "fasta")}


def read_fasta_records(path: Union[str, Path]) -> list:
    """Return a list of BioPython SeqRecord objects from a FASTA file."""
    return list(SeqIO.parse(str(path), "fasta"))


def write_fasta(records, path: Union[str, Path]) -> None:
    """Write a list of SeqRecord objects to a FASTA file.

    Args:
        records: Iterable of ``Bio.SeqRecord.SeqRecord`` objects.
        path: Output file path.
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    count = SeqIO.write(records, str(path), "fasta")
    logger.debug("Wrote %d sequences to %s", count, path)
