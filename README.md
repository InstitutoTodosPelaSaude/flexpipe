# flexpipe

A flexible Nextstrain pipeline for genomic epidemiology of viral pathogens. Supports data ingestion from [Pathoplexus](https://pathoplexus.org/) or [NCBI](https://www.ncbi.nlm.nih.gov/labs/virus/vssi/), optional integration of local surveillance sequences, automated QC via [ViralQC](https://github.com/InstitutoTodosPelaSaude/viralQC), and a complete phylogenetic workflow ending in an [Auspice](https://auspice.us/)-compatible JSON.

This repository includes two example builds:

- **Yellow Fever Virus (YFV) in Brazil** (`builds/yfv-brazil/`) — Pathoplexus source, Brazil-division region, fully runnable.
- **RSV-A global** (`builds/rsv-global/`) — NCBI source, country region, scaffold (see `builds/rsv-global/NOTES.md` for required biological inputs).

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
    --workdir /path/to/workdir/yfv-brazil \
    --run-date 2026-06-06

# Visualise
auspice view --datasetDir /path/to/workdir/yfv-brazil/auspice/
```

Open `http://localhost:4000` in your browser.

#### Stage-by-stage execution

```bash
# Stage 1: ingest only
flexpipe-run --config builds/yfv-brazil/config.yaml --workdir /tmp/run --run-date 2026-06-06 --stage ingest

# Stage 2: phylogenetics only (after ingest completes)
flexpipe-run --config builds/yfv-brazil/config.yaml --workdir /tmp/run --run-date 2026-06-06 --stage phylo
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

The ViralQC runner is configurable. Defaults preserve the historical behavior:

```yaml
viralqc:
  runner: conda        # conda, mamba, micromamba, or direct
  conda_env: viralQC
  executable: vqc
```

Virus and segment expectations are alias-aware. Built-in aliases live in
`flexpipe/data/viralqc/aliases.yaml`; build-local experiments can set
`viralqc.aliases_file`. Prefer operational keys such as `rsv_a`, `flu_a_h1n1`, or `ha`
when ViralQC output labels vary across Nextclade datasets, BLAST records, or segment naming
conventions. ICTV species names are stored as metadata in the registry but are not broad
matching shortcuts unless explicitly listed as aliases.

To re-download just the datasets without reinstalling the environment:

```bash
bash scripts/install_viralqc.sh --skip-tests
```

---

## Multi-build layout

Each build has its own directory under `builds/` with a self-contained `config.yaml`.
Run multiple builds independently by pointing `--workdir` to separate directories:

```bash
flexpipe-run --config builds/yfv-brazil/config.yaml  --workdir /workdir/yfv-brazil  --run-date 2026-06-06
flexpipe-run --config builds/rsv-global/config.yaml  --workdir /workdir/rsv-global  --run-date 2026-06-06
```

Build directories contain:
- `config.yaml` — all pipeline parameters for this build
- `subsample.yaml` — subsampling strategy
- `auspice_config.json` — Auspice display settings
- `reference.gb` — reference genome (GenBank format)
- `clades.tsv` — clade definitions for `augur clades`
- `keep.txt` / `ignore.txt` — strains to always include/exclude
- `cache_coordinates.tsv` — read-only geocoding seed (runtime cache lives in `--workdir`)

For unattended scheduled execution and future service integration, see
[`docs/service_contract.md`](docs/service_contract.md).

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
- Normalizes flexible date strings via `flexpipe-normalize-dates` and writes `results/ingest/date_normalization.tsv`
- Computes `clade_truncated` by trimming hierarchical clade names to `clade_levels` levels
- Assigns a `region` column from either country names (global builds) or state names (Brazil-only builds — see `region_source` below)
- Adds a `continent` column from `country`; for Brazil builds this is separate from `region`
- Optionally decomposes structured lineage strings into prefix-safe columns such as `serotype`, `genotype`, `major_lineage`, and `minor_lineage`
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

The YFV example uses `region_source: "division"`, so `region` is the Brazilian macro-region while
`continent` is still derived from `country` for phylogeographic traits.

### Lineage parser

Builds can keep the raw Nextclade/ViralQC lineage in `clade` and additionally expose derived,
prefix-safe lineage columns:

```yaml
curation:
  lineage_parser: "dengue"   # none | dengue | pango | generic_dot
```

For DENV, values such as `3III_B.3.2` become `serotype=3`, `genotype=3III`,
`major_lineage=3III_B`, and `minor_lineage=3III_B.3.2`. Prefixes are retained so lineage names do
not collide across genotypes. Set `lineage_parser: "none"` to preserve legacy behavior.

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
the output `<workdir>/config/latlongs.tsv` is consumed by `augur export`. Workdirs are seeded
from the bundled shared cache (`flexpipe/data/geo/cache_coordinates.tsv`) first, then the
build-specific `builds/<name>/cache_coordinates.tsv` so manual build entries win. Use
`coordinates.shared_cache` to point at a project-local shared seed cache.

**Colours**: `flexpipe-name2hue` assigns hues from the subsampled metadata. `flexpipe-colours`
produces `<workdir>/config/colour_scheme.tsv`. Both are configured via `colours` in `config.yaml`:

```yaml
colours:
  clade:    "serotype genotype major_lineage minor_lineage clade"
  geo:      "continent country division location"
  source:   "source"
  data_use: "data_use"
```

The order is most-general to most-specific. The first level gets a stable root hue; child levels
receive deterministic shades within that root hue family.

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
| `parameters.mask_5prime` | `142` | Bases masked at 5′ end (**reference-specific** — X03700.1) |
| `parameters.mask_3prime` | `548` | Bases masked at 3′ end (**reference-specific** — X03700.1) |
| `parameters.mask_sites_file` | `""` | Optional BED file of problematic sites (`augur mask --mask`) |
| `options.threads` | `4` | Threads for MAFFT and IQ-TREE |
| `traits.columns` | `continent country division location clade` | Columns for ancestral trait inference |
| `traits.max_states` | `200` | Maximum states per trait column before rare states are collapsed |
| `traits.rare_state_label` | `other` | Label used for collapsed rare trait states |

> **Terminal masking is reference-specific.** The values `mask_5prime: 142` and `mask_3prime: 548`
> are calibrated for the YFV reference X03700.1. When using a different reference, recalculate
> these values from a pilot alignment. Set both to `0` to disable terminal masking (safe default
> for new builds). Use `mask_sites_file` to point at a BED file of additional problematic sites.
> `flexpipe-reference-mask` can generate first-draft terminal BED masks from GenBank
> annotations, including explicit UTR features, UTR-like qualifiers on other feature types, or
> CDS/gene boundary fallback. Review generated BEDs before production surveillance use.

```bash
flexpipe-reference-mask \
  --reference builds/<name>/reference.gb \
  --output builds/<name>/masks/reference_terminal.bed
```

### Clade annotation

Clade labels are defined in `clades.tsv` and applied by `augur clades`. YFV genotypes are
single-level (`I`, `II`, `III`…), so `clade_levels: 1` keeps `clade_truncated` equal to `clade`.

### Trait state cap

Before `augur traits`, flexpipe writes `<workdir>/results/subsampled/metadata_traits.tsv` and
collapses rare states per configured trait column when a column exceeds `traits.max_states`. The
primary subsampled metadata used for export is not mutated; the collapsed sidecar is only for
TreeTime ancestral-state inference.

### Segmented viruses (out of scope for v0.x)

flexpipe uses a **single reference / single alignment / single tree** model. This works for
non-segmented or effectively-single-segment workflows (YFV, RSV-A, SARS-CoV-2). For segmented
viruses (Influenza, Arenaviruses, …), run **one build per segment** and set
`viralqc.expected_segment` in each build's `config.yaml` so ViralQC flags wrong-segment
sequences. Full per-segment fan-out, co-phylogeny, and reassortment handling are deferred to
a future version.

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
| `parameters.mask_5prime/3prime` | Terminal masking in bp; **reference-specific** — set 0 for new builds and calibrate |
| `parameters.mask_sites_file` | Optional BED file of additional problematic sites or generated terminal masks |
| `curation.clade_levels` | Hierarchy depth for `clade_truncated` |
| `curation.lineage_parser` | Optional parser for structured lineage strings (`none`, `dengue`, `pango`, `generic_dot`) |
| `curation.date_formats` | Optional override for flexible date-normalization policy |
| `qc.min_sequences` | Minimum subsampled sequences before phylogenetics (default 10; 0 disables) |
| `region_source` | `"country"` for global builds; `"division"` for Brazil-only |
| `coordinates.shared_cache` | Optional shared geocode seed cache override |
| `viralqc.expected_virus` | Expected virus alias key or literal label (ViralQC rejects mismatches) |
| `viralqc.expected_segment` | Expected segment alias key or literal label for single-segment builds |
| `viralqc.aliases_file` | Optional override for virus/segment alias registry |
| `viralqc.*` | ViralQC paths (or set `VIRALQC_DATASETS_DIR`) |
| `traits.columns` | Columns for ancestral trait reconstruction |
| `traits.max_states` | Per-trait state cap for TreeTime ancestral-state inference |

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
| `flexpipe-normalize-dates` | Normalize flexible metadata dates before Augur date curation |
| `flexpipe-coordinates` | Geocode locations via Nominatim with rate-limiting and caching |
| `flexpipe-update-cache` | Merge newly geocoded coordinates into the workdir cache |
| `flexpipe-name2hue` | Generate colour hue mapping from subsampled metadata |
| `flexpipe-colours` | Assign hex colours per metadata value |
| `flexpipe-collapse-traits` | Cap trait states into a TreeTime metadata sidecar |
| `flexpipe-reference-mask` | Generate first-draft terminal BED masks from GenBank annotations |
| `flexpipe-qc-summary` | Build per-run QC report (`qc_report.json` + `qc_summary.tsv`) from ingest outputs |

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
