# RSV-A Global Build — Scaffold Notes

This build exercises the **NCBI source + `region_source: country`** code path in flexpipe.
The ingest pipeline (DAG planning, NCBI fetch, curation, QC, subsampling, colours,
coordinates) is fully wired and tested via the integration dry-run suite.

The **phylogenetic pipeline** requires three biological inputs that cannot be
auto-generated and must be provided before a production run:

---

## 1. Reference genome — `reference.gb`

**Current state:** placeholder file with 'n' sequence; `augur align` will fail.

**Required:** a complete GenBank record for an RSV-A reference strain.

### Recommended reference: PP109421.1

RSV-A isolate from the WHO/Nextstrain RSV-A clade system. Download with:

```bash
# Requires NCBI Entrez Direct (ncbi-entrez-direct conda package)
efetch -db nucleotide -id PP109421.1 -format gb > builds/rsv-global/reference.gb
```

Or from the NCBI web UI:
<https://www.ncbi.nlm.nih.gov/nuccore/PP109421.1>

### Terminal masking

After choosing a reference, update `mask_5prime` and `mask_3prime` in
`builds/rsv-global/config.yaml` with the correct values for that reference.
The current values (both `0`) disable terminal masking. RSV-A genomes often
have ~44 bp leader and ~155 bp trailer that are poorly resolved and benefit
from masking — calibrate against your chosen reference using a pilot alignment.

Also add the reference accession to `ignore.txt` so it is excluded from
subsampling:

```bash
echo "PP109421" >> builds/rsv-global/ignore.txt
```

---

## 2. Clade definitions — `clades.tsv`

**Current state:** header-only placeholder; `augur clades` will return empty output.

**Required:** tab-separated file with columns `clade`, `gene`, `site`, `alt`.
One row per defining mutation; augur assigns the deepest clade whose mutations
all match.

### RSV-A clade nomenclature

RSV-A uses the WHO/Bedford-lab hierarchical notation (e.g. `A.D.1.1`).
`clade_levels: 3` in `config.yaml` truncates this to 3 levels (`A.D.1`),
reported in the `clade_truncated` column.

**Sources:**

- **Nextstrain RSV-A clade definitions** (F and G gene mutations):
  <https://github.com/nextstrain/rsv/blob/main/phylogenetic/defaults/clades_a.tsv>
- **WHO/Pebody nomenclature proposal (2022):**
  Pebody et al., *Influenza Other Respir Viruses* 2022; PMID 36199214.

Copy or adapt `clades.tsv` from the Nextstrain RSV repository for the F-gene
definitions; add any Brazil-specific genotypes from the local surveillance data.

---

## 3. ViralQC RSV-A dataset

**Current state:** no RSV-A dataset is bundled in `viralQC/datasets/`.

**Required:** a ViralQC dataset containing:
- A BLAST nucleotide database built from RSV-A genomes.
- A Nextclade dataset for RSV-A (for clade assignment and coverage computation).

### Setup steps

```bash
# 1. Activate the viralQC environment
conda activate viralQC

# 2. Download the Nextclade RSV-A dataset
nextclade dataset get --name nextstrain/rsv/a --output-dir viralQC/datasets/rsv-a/nextclade

# 3. Build the BLAST database from a curated RSV-A FASTA
#    (use e.g. a Nextstrain RSV-A sequences.fasta downloaded from data.nextstrain.org)
makeblastdb -in rsv-a-sequences.fasta -dbtype nucl \
    -out viralQC/datasets/rsv-a/blast/rsv-a \
    -title "RSV-A BLAST DB"

# 4. Update builds/rsv-global/config.yaml:
#    viralqc:
#      datasets_dir: "viralQC/datasets/rsv-a"
```

Alternatively set `VIRALQC_DATASETS_DIR` to a directory containing the RSV-A
dataset so multiple builds can share the same install.

---

## Status

| Component | State |
|---|---|
| `config.yaml` | ✅ complete — NCBI source, country region, RSV-A taxid 208893 |
| `subsample.yaml` | ✅ complete — country + year grouping |
| `auspice_config.json` | ✅ complete |
| `keep.txt` / `ignore.txt` | ✅ scaffold (add reference accession to ignore.txt) |
| `cache_coordinates.tsv` | ✅ empty seed (will be populated at runtime) |
| `reference.gb` | ⚠️ placeholder — download PP109421.1 |
| `clades.tsv` | ⚠️ placeholder — copy from nextstrain/rsv |
| ViralQC dataset | ⚠️ not bundled — download Nextclade RSV-A + build BLAST DB |
| Integration dry-run | ✅ wiring test covers NCBI ingest DAG |
