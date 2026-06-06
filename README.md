# flexpipe

A flexible Nextstrain pipeline for genomic epidemiology of viral pathogens. Supports data ingestion from [Pathoplexus](https://pathoplexus.org/) or [NCBI](https://www.ncbi.nlm.nih.gov/labs/virus/vssi/), optional integration of local surveillance sequences, automated QC via [ViralQC](https://github.com/InstitutoTodosPelaSaude/viralQC), and a complete phylogenetic workflow ending in an [Auspice](https://auspice.us/)-compatible JSON.

This repository includes a working example build for **Yellow Fever Virus (YFV) in Brazil**, covering sequences from 2015 to the present using Pathoplexus as the data source.

---

## Getting Started

### Requirements

- [conda](https://docs.conda.io/) / [mamba](https://mamba.readthedocs.io/) / [micromamba](https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html)
- A `nextstrain` conda environment (see below)
- [ViralQC](https://github.com/InstitutoTodosPelaSaude/viralQC) — vendored as a git submodule; set up with the install script below

### Installation

```bash
# 1. Clone the repo with the viralQC submodule
git clone --recurse-submodules https://github.com/InstitutoTodosPelaSaude/flexpipe.git
cd flexpipe

# If you already cloned without --recurse-submodules:
#   git submodule update --init --recursive

# 2. Create the nextstrain conda environment
conda env create -f config/nextstrain.yml
conda activate nextstrain

# 3. Install the flexpipe package
pip install -e '.[test,dev]'

# 4. Set up ViralQC (creates env, downloads Nextclade datasets + BLAST DB, runs tests)
bash scripts/install_viralqc.sh
```

### Running the example (YFV Brazil)

All pipeline outputs go to a **workdir** — the source tree is never modified.

```bash
# Run the full pipeline (ingest + phylogenetics) for the YFV Brazil build
flexpipe-run \
    --config  builds/yfv-brazil/config.yaml \
    --workdir /path/to/workdir/yfv-brazil

# Visualise
auspice view --datasetDir /path/to/workdir/yfv-brazil/auspice/
```

Open `http://localhost:4000` in your browser.

#### Stage-by-stage execution

```bash
# Stage 1: ingest only
flexpipe-run --config builds/yfv-brazil/config.yaml --workdir /tmp/run --stage ingest

# Stage 2: phylogenetics only (after ingest completes)
flexpipe-run --config builds/yfv-brazil/config.yaml --workdir /tmp/run --stage phylo
```

#### Direct Snakemake invocation (advanced)

`--configfile` is required — the Snakefiles have no built-in default.

```bash
# Dry-run to preview ingest steps
snakemake --snakefile ingest/Snakefile \
    --configfile builds/yfv-brazil/config.yaml \
    --config workdir=/tmp/run \
    --dry-run --cores 4

# Run ingest directly
snakemake --snakefile ingest/Snakefile \
    --configfile builds/yfv-brazil/config.yaml \
    --config workdir=/tmp/run --cores 4

# Run phylogenetics directly
snakemake --snakefile phylogenetic/Snakefile \
    --configfile builds/yfv-brazil/config.yaml \
    --config workdir=/tmp/run --cores 4
```

### ViralQC datasets

`scripts/install_viralqc.sh` downloads the Nextclade datasets and BLAST database into
`viralQC/datasets/`. flexpipe auto-discovers that path — **no extra configuration needed**
after running the install script.

If you prefer to store datasets elsewhere (e.g. shared across projects), override the
auto-discovery with an environment variable or a `config.yaml` key (higher precedence):

```bash
# Option A: environment variable
export VIRALQC_DATASETS_DIR=/path/to/viralqc-datasets
flexpipe-run --config builds/yfv-brazil/config.yaml --workdir /tmp/run

# Option B: config.yaml key
# viralqc:
#   datasets_dir: /path/to/viralqc-datasets
```

To re-download just the datasets without reinstalling the environment:

```bash
bash scripts/install_viralqc.sh --skip-tests
```

---

## Multi-build layout

Each build has its own directory under `builds/` with a self-contained `config.yaml`.
Run multiple builds independently by pointing `--workdir` to separate directories:

```bash
flexpipe-run --config builds/yfv-brazil/config.yaml  --workdir /workdir/yfv-brazil
flexpipe-run --config builds/rsv-global/config.yaml  --workdir /workdir/rsv-global
```

Build directories contain:
- `config.yaml` — all pipeline parameters for this build
- `subsample.yaml` — subsampling strategy
- `auspice_config.json` — Auspice display settings
- `reference.gb` — reference genome (GenBank format)
- `clades.tsv` — clade definitions for `augur clades`
- `keep.txt` / `ignore.txt` — strains to always include/exclude
- `cache_coordinates.tsv` — read-only geocoding seed (runtime cache lives in `--workdir`)

---

## Pipeline Overview

```
fetch_pathoplexus  (or fetch_ncbi)
    └── merge_local_sequences  (optional local sequences)
            └── viralqc        (BLAST + Nextclade: QC grades + clade assignment)
                    └── curate_qc  (normalisation, dedup, augur filter)
                            └── prepare  (augur subsample)
                                    ├── coordinates  (geocoding → latlongs.tsv)
                                    ├── generate_name2hue  (colour palette)
                                    └── colours  (colour_scheme.tsv)
                                            └── [phylogenetic/Snakefile]
                                                    align → mask → tree → refine
                                                    → ancestral → translate → traits
                                                    → clades → export
                                                    → <workdir>/auspice/results.json
```

---

## Stage 1 — Ingest

Sequences and metadata are fetched from **Pathoplexus** (default) or **NCBI**, controlled by
`data_source` in your build's `config.yaml`.

### Example — YFV Brazil

| Parameter | Value |
|-----------|-------|
| `data_source` | `pathoplexus` |
| `pathoplexus.organism` | `yellow-fever` |
| `pathoplexus.min_completeness` | `0.70` |
| `ncbi.taxid` (fallback) | `11089` |
| `ncbi.genome_size` (bp) | `10862` |

Local surveillance sequences (`data/new_sequences.fasta` + `data/metadata.xlsx`) are merged
with remote data. Set `local_sequences.enabled: true` in `config.yaml` to activate.

---

## Stage 2 — QC and Curation

**ViralQC** (BLAST + Nextclade) assigns genome quality grades (A–D) and clade labels. The
`flexpipe-curate` entry point then:

- Renames and standardises metadata fields (`strain`, `date`, `country`, `division`, `location`, `data_use`, `clade`)
- Computes `clade_truncated` by trimming hierarchical clade names to `clade_levels` levels
- Assigns a `region` column from either country names (global builds) or state names (Brazil-only builds — see `region_source` below)
- Marks each sequence with a `source` label (`Pathoplexus`, `NCBI`, or `ITpS`)
- Deduplicates sequences, preferring local ITpS records

**QC filters** applied by `augur filter`:

| Parameter | Value |
|-----------|-------|
| `qc.genome_quality` | `A`, `B` (grades C and D discarded) |
| `qc.min_coverage` | `0.70` |
| Required columns | `strain`, `date`, `clade` |

### Region mapping

The `region_source` field in `config.yaml` controls how the `region` column is derived:

| `region_source` | Behaviour | Use case |
|----------------|-----------|----------|
| `"country"` | Maps country name → continent | Global builds |
| `"division"` | Maps Brazilian state → macro-region | Brazil-only builds |

Brazilian macro-regions: **Norte**, **Nordeste**, **Centro-Oeste**, **Sudeste**, **Sul**.

The YFV example uses `region_source: "division"`.

---

## Stage 3 — Subsampling

Controlled by `subsample.yaml`, which is read by `augur subsample`. The YFV Brazil strategy:

```yaml
defaults:
  min_date: 2015

samples:
  brazil:
    query: "country == 'Brazil'"
    group_by: [division, year]
    sequences_per_group: 100
```

For global builds, replace `division` with `country` and add `clade_truncated` to `group_by`.

---

## Stage 4 — Coordinates and Colours

**Coordinates**: `flexpipe-coordinates` queries Nominatim (OpenStreetMap) to geocode the
columns listed in `coordinates.columns`. Results are cached in `<workdir>/cache/cache_coordinates.tsv`;
the output `<workdir>/config/latlongs.tsv` is consumed by `augur export`. The geocoding seed
from the build directory (`builds/<name>/cache_coordinates.tsv`) is copied into the workdir on
first run — the source tree is never written to.

**Colours**: `flexpipe-name2hue` assigns hues from the subsampled metadata. `flexpipe-colours`
produces `<workdir>/config/colour_scheme.tsv`. Both are configured via `colours` in `config.yaml`:

```yaml
colours:
  clade:    "clade_truncated clade"
  geo:      "region division location"
  source:   "source"
  data_use: "data_use"
```

---

## Stage 5 — Phylogenetic

Steps: `align` (MAFFT) → `mask` → `tree` (IQ-TREE 3 UFBoot) → `refine` (TreeTime) →
`ancestral` → `translate` → `traits` → `clades` → `export` → `<workdir>/auspice/results.json`

### Key phylogenetic parameters — YFV example

| Parameter | Value | Description |
|-----------|-------|-------------|
| `parameters.model` | `MFP` | ModelFinder Plus — auto-selects best substitution model |
| `parameters.ufboot` | `1000` | Ultrafast bootstrap replicates |
| `parameters.root` | `least-squares` | Root method for time-calibrated tree |
| `parameters.coalescent` | `skyline` | Effective population size model in TreeTime |
| `parameters.date_inference` | `marginal` | Marginal date inference for ambiguous dates |
| `parameters.divergence_units` | `mutations` | Branch length units in timetree |
| `parameters.clock_filter_iqd` | `4` | IQD filter for clock outliers |
| `parameters.ancestral_inference` | `joint` | Joint ancestral reconstruction |
| `parameters.mask_5prime` | `142` | Bases masked at 5′ end (X03700.1-specific) |
| `parameters.mask_3prime` | `548` | Bases masked at 3′ end (X03700.1-specific) |
| `options.threads` | `4` | Threads for MAFFT and IQ-TREE |
| `traits.columns` | `division location clade` | Columns for ancestral trait inference |

### Clade annotation

Clade labels are defined in `clades.tsv` and applied by `augur clades`. YFV genotypes are
single-level (`I`, `II`, `III`…), so `clade_levels: 1` keeps `clade_truncated` equal to `clade`.

---

## Adapting to Another Pathogen

Create a new build directory and edit `config.yaml`:

```bash
cp -r builds/yfv-brazil builds/my-pathogen
# edit builds/my-pathogen/config.yaml, subsample.yaml, reference.gb, clades.tsv
```

Key fields to update:

| Field | Description |
|-------|-------------|
| `data_source` | `"pathoplexus"` or `"ncbi"` |
| `pathoplexus.organism` | Pathoplexus organism slug (e.g. `rsv-a`, `yellow-fever`) |
| `ncbi.taxid` | NCBI taxonomy ID |
| `ncbi.genome_size` | Reference genome size in bp |
| `parameters.mask_5prime/3prime` | Terminal masking in bp (0 for full-genome builds) |
| `curation.clade_levels` | Hierarchy depth for `clade_truncated` |
| `region_source` | `"country"` for global builds; `"division"` for Brazil-only |
| `viralqc.*` | ViralQC paths (or set `VIRALQC_DATASETS_DIR`) |
| `traits.columns` | Columns for ancestral trait reconstruction |

---

## Build Configuration Files

| File | Purpose |
|------|---------|
| `builds/<name>/config.yaml` | All pipeline parameters for this build |
| `builds/<name>/subsample.yaml` | Subsampling strategy (read by `augur subsample`) |
| `builds/<name>/auspice_config.json` | Auspice display settings (colorings, filters, panels) |
| `builds/<name>/reference.gb` | Reference genome in GenBank format |
| `builds/<name>/clades.tsv` | Clade definitions for `augur clades` |
| `builds/<name>/cache_coordinates.tsv` | Geocoding seed (read-only; workdir copy is updated each run) |
| `builds/<name>/keep.txt` | Strains to always include (one accession per line) |
| `builds/<name>/ignore.txt` | Strains to always exclude (reference accession goes here) |
| `config/nextstrain.yml` | Conda environment definition (shared across all builds) |

---

## Entry Points

| Command | Role |
|---------|------|
| `flexpipe-run` | Orchestrator — run ingest + phylo end-to-end for one build |
| `flexpipe-fetch-pathoplexus` | Download metadata + sequences from Pathoplexus/LAPIS |
| `flexpipe-fetch-ncbi` | Download from NCBI Entrez by taxid |
| `flexpipe-merge` | Merge remote data with local surveillance sequences |
| `flexpipe-curate` | ViralQC join, region, `clade_truncated`, source, dedup |
| `flexpipe-coordinates` | Geocode locations via Nominatim with rate-limiting and caching |
| `flexpipe-update-cache` | Merge newly geocoded coordinates into the workdir cache |
| `flexpipe-name2hue` | Generate colour hue mapping from subsampled metadata |
| `flexpipe-colours` | Assign hex colours per metadata value |

---

## Docker

```bash
docker build -t flexpipe .

docker run --rm \
    -v $(pwd)/builds:/app/builds \
    -v /path/to/viralqc-datasets:/viralqc-datasets \
    -v /path/to/workdir:/workdir \
    -e VIRALQC_DATASETS_DIR=/viralqc-datasets \
    flexpipe \
    flexpipe-run \
        --config  /app/builds/yfv-brazil/config.yaml \
        --workdir /workdir/yfv-brazil
```

---

## License

This project is licensed under the [MIT License](LICENSE).
