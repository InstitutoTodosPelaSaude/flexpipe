# Pipeline Overview

The flexpipe workflow is divided into two stages: **Ingest** and **Phylogenetics**. Both are implemented as Snakemake workflows.

## High-Level Data Flow

```{mermaid}
graph LR
    A["Data Source<br/>(Pathoplexus/NCBI/Local)"]
    B["ViralQC<br/>(BLAST + Nextclade)"]
    C["Curation<br/>(metadata normalization)"]
    D["Subsampling<br/>(balanced selection)"]
    E["Colors & Coords<br/>(visualization prep)"]
    F["Phylogenetics<br/>(align → tree → refine)"]
    G["Export<br/>(Auspice JSON)"]
    
    A -->|fetch| B
    B -->|join| C
    C -->|filter| D
    D -->|embellish| E
    D -->|provide| F
    F -->|export| G
```

## Ingest Stage

The `ingest/Snakefile` orchestrates data fetching, quality control, and preparation for phylogenetics.

### Ingest Rules

| Rule | Input | Output | Purpose |
|------|-------|--------|---------|
| `fetch_pathoplexus` | config (organism, query_params) | metadata.tsv, sequences.fasta | Fetch Pathoplexus (LAPIS) sequences |
| `fetch_ncbi` | config (taxid, email) | metadata.tsv, sequences.fasta | Fetch NCBI Entrez sequences |
| `fetch_local` | config (local.metadata, local.sequences) | — | Local data mode (no download) |
| `merge_local_sequences` | ITpS xlsx/TSV + remote data | merged_metadata.tsv, sequences.fasta | Combine local surveillance with remote |
| `viralqc` | sequences.fasta | results.tsv (qc output) | ViralQC classification (genome_quality, clade) |
| `curate_qc` | metadata, viralqc results | dated_metadata.tsv | Normalize metadata, join QC, compute region |
| `qc_summary` | dated_metadata.tsv | qc_summary.tsv | Generate QC statistics |
| `augur filter` | dated_metadata.tsv | filter_log.tsv | Apply genome quality + coverage thresholds |
| `augur subsample` | filtered metadata + sequences | subsampled/{metadata.tsv,sequences.fasta} | Balanced strain selection |
| `generate_name2hue` | subsampled metadata | name2hue.tsv | Deterministic hue assignment |
| `flexpipe-colours` | subsampled metadata + name2hue | colour_scheme.tsv | Color assignments by metadata value |
| `flexpipe-coordinates` | subsampled metadata | latlongs.tsv | Geographic coordinates (Nominatim + cache) |

### Key Ingest Features

- **Data source switching**: `data_source: pathoplexus|ncbi|local` in config determines which fetch rule runs
- **ViralQC integration**: alias-aware virus/segment matching, dataset resolution, mode (run/precomputed/skip)
- **Curation**: field renaming, date normalization, lineage parsing, geographic assignment, deduplication
- **Subsampling**: `augur subsample` with division/year stratification (configurable via `subsample.yaml`)

## Phylogenetic Stage

The `phylogenetic/Snakefile` builds and calibrates a phylogenetic tree from subsampled sequences.

### Phylogenetic Rules

| Rule | Input | Output | Purpose |
|------|-------|--------|---------|
| `augur align` | sequences.fasta + reference | alignments.fasta | MAFFT alignment |
| `augur mask` | alignments.fasta | masked.fasta | Mask terminal/ambiguous regions (or copy) |
| `iqtree3` | masked.fasta | tree.nwk | Maximum-likelihood tree (IQ-TREE 3) |
| `augur refine` | tree, metadata, masked.fasta | tree.nwk, branch_lengths.json | TreeTime temporal calibration |
| `augur ancestral` | tree, alignment | nt_muts.json | Nucleotide mutation reconstruction |
| `augur translate` | nt_muts, reference | aa_muts.json | Amino acid mutation reconstruction |
| `augur traits` | tree, metadata (traits columns) | traits.json | Ancestral state inference (geographic/clade) |
| `augur clades` | tree, nt_muts | clades.json | Clade assignment via mutation criteria |
| `augur export v2` | all above outputs | auspice/results.json | Auspice JSON export |

### Key Phylogenetic Features

- **Masking**: terminal bp masking (reference-specific; YFV: 142/548) or disabled for full-genome
- **UFBoot**: enabled when `parameters.ufboot > 0`; disabled for fast first-pass runs
- **Temporal calibration**: TreeTime with configurable root method, coalescent model, clock filter
- **Trait inference**: geographic traits (continent, country, division, location) and clade-based traits
- **Clade definitions**: mutation-based (read from `builds/<name>/clades.tsv`)

## Stage Control

Run only ingest:
```bash
flexpipe-run --config builds/yfv-brazil/config.yaml --workdir /tmp/run --stage ingest
```

Run only phylo (after ingest completes):
```bash
flexpipe-run --config builds/yfv-brazil/config.yaml --workdir /tmp/run --stage phylo
```

Run both (default):
```bash
flexpipe-run --config builds/yfv-brazil/config.yaml --workdir /tmp/run
```

## Explore Further

- [Ingest Details](ingest.md) — fetch, merge, ViralQC, curation, subsampling, colors
- [Phylogenetics Details](phylogenetics.md) — alignment, masking, tree, refinement, export
- [Local Data Mode](local-data.md) — bring-your-own sequences without remote data
