# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

**flexpipe** is a flexible Nextstrain pipeline for genomic epidemiology of viral pathogens. It supports:
- Data ingestion from Pathoplexus, NCBI, or local surveillance sequences
- Automated quality control via ViralQC (BLAST + Nextclade)
- Complete phylogenetic workflow producing Auspice-compatible JSON for visualization

The pipeline is an **installable Python package** (`pip install -e .`) backed by two Snakemake workflows:
1. **Ingest** (`ingest/Snakefile`): fetches data, merges local sequences, performs QC/curation, subsampling, and generates colors/coordinates
2. **Phylogenetic** (`phylogenetic/Snakefile`): alignment, masking, tree building, temporal calibration, and export

All outputs go to a **per-build workdir** — the source tree is never modified at runtime.

Example builds: **Yellow Fever Virus (YFV) Brazil** (`builds/yfv-brazil/`) and **RSV-A global** (`builds/rsv-global/` — scaffold, see NOTES.md).

## Common Commands

### Environment Setup
```bash
# Clone with the viralQC submodule (or run: git submodule update --init --recursive)
git clone --recurse-submodules https://github.com/InstitutoTodosPelaSaude/flexpipe.git

# Create and activate the nextstrain conda environment
conda env create -f config/nextstrain.yml
conda activate nextstrain

# Install the flexpipe package (editable, with dev + test extras)
pip install -e '.[test,dev]'

# Set up the bundled viralQC submodule (creates env, downloads datasets, runs tests)
bash scripts/install_viralqc.sh
```

### Running the Full Pipeline

```bash
# Run ingest + phylogenetics end-to-end for the YFV Brazil build
flexpipe-run \
    --config  builds/yfv-brazil/config.yaml \
    --workdir /path/to/workdir/yfv-brazil

# Visualize results
auspice view --datasetDir /path/to/workdir/yfv-brazil/auspice/
# Open http://localhost:4000 in browser
```

### Workflow Control
```bash
# Run ingest only
flexpipe-run --config builds/yfv-brazil/config.yaml --workdir /tmp/run --stage ingest

# Run phylogenetics only (after ingest completes)
flexpipe-run --config builds/yfv-brazil/config.yaml --workdir /tmp/run --stage phylo

# Dry run (preview steps without executing)
snakemake --snakefile ingest/Snakefile \
    --configfile builds/yfv-brazil/config.yaml \
    --config workdir=/tmp/run \
    --dry-run --cores 4

# Clean subsampled outputs (keep ViralQC results)
snakemake --snakefile ingest/Snakefile \
    --configfile builds/yfv-brazil/config.yaml \
    --config workdir=/tmp/run clean

# Full reset of workdir
snakemake --snakefile ingest/Snakefile \
    --configfile builds/yfv-brazil/config.yaml \
    --config workdir=/tmp/run reset
```

### Development & Testing
```bash
# Run all unit tests (default: excludes integration and network tests)
pytest

# Run with coverage
pytest --cov=flexpipe

# Lint
ruff check .
black --check .

# Test an individual entry point directly
flexpipe-fetch-pathoplexus --config builds/yfv-brazil/config.yaml \
    --metadata-output /tmp/test_meta.tsv \
    --sequences-output /tmp/test_seq.fasta

flexpipe-curate \
    --config   builds/yfv-brazil/config.yaml \
    --metadata results/ingest/dated_metadata.tsv \
    --nextclade results/viralqc/outputs/results.tsv \
    --output   /tmp/curated.tsv
```

## Architecture

### Package Layout

```
flexpipe/
  config.py              # pydantic FlexpipeConfig; load_config()
  paths.py               # WorkdirPaths — all output paths under workdir
  manifest.py            # run provenance; ingest→phylo boundary validation
  run.py                 # orchestrator: flexpipe-run
  cli.py                 # console-script entry-point dispatch
  io.py                  # shared load_table(), FASTA helpers
  ingest/{pathoplexus,ncbi,merge}.py
  curate/{regions,hosts,clades,columns,viralqc_join,pipeline,qc_summary}.py
  geo/{coordinates,cache}.py
  colors/{hues,scheme}.py
  data/                  # bundled defaults (shipped via hatchling force-include)
    regions/{country_to_continent.tsv, brazil_state_to_region.tsv, brazil_abbreviations.tsv}
    hosts/host_rules.yaml
    colors/{region_hues.tsv, host_hues.tsv, source_hues.tsv, data_use_hues.tsv}
builds/
  yfv-brazil/            # Pathoplexus, division region, fully runnable
    config.yaml          # all parameters for this build
    subsample.yaml
    auspice_config.json
    clades.tsv
    reference.gb
    keep.txt  ignore.txt
    cache_coordinates.tsv   # read-only seed; workdir copy updated at runtime
  rsv-global/            # NCBI, country region, scaffold (see NOTES.md)
config/
  nextstrain.yml         # conda environment definition (shared)
ingest/Snakefile
phylogenetic/Snakefile
tests/{unit/, golden/, integration/, fixtures/}
```

### Data Flow

```
Pathoplexus/NCBI fetch
    ↓
(merge local sequences)
    ↓
ViralQC (BLAST + Nextclade)
    ↓
flexpipe-curate (metadata normalization, clade_truncated, region assignment, dedup)
    ↓
augur filter (QC: genome quality A/B, min coverage)
    ↓
augur subsample (by state/year for Brazil build)
    ↓
flexpipe-name2hue → flexpipe-colours (color assignments)
flexpipe-coordinates (Nominatim geocoding with cache)
    ↓
[phylogenetic/Snakefile]
augur align → mask → iqtree3 tree → augur refine (time-calibration)
→ ancestral → translate → traits → clades → augur export
    ↓
<workdir>/auspice/results.json (ready for visualization)
```

### Key Build Configuration Files (`builds/<name>/`)

- **`config.yaml`**: All pipeline parameters (data source, Pathoplexus/NCBI settings, QC thresholds, phylogenetic parameters, masking regions, coalescent model, trait columns)
- **`subsample.yaml`**: Subsampling strategy (group by division/year, sequences per group, include/exclude lists)
- **`auspice_config.json`**: Auspice display settings (colorings, filters, panels, geo resolutions)
- **`clades.tsv`**: Clade definitions for `augur clades` (mutation-based branch labels)
- **`reference.gb`**: Reference genome (GenBank format; YFV uses X03700.1)
- **`cache_coordinates.tsv`**: Read-only geocoding seed; copied to `<workdir>/cache/` on first run
- **`keep.txt`**: Strains to always include in subsampling
- **`ignore.txt`**: Strains to always exclude (e.g., reference accession)

### Ingest Pipeline (`ingest/Snakefile`)

The Snakefile reads the **resolved config** (`<workdir>/config/snakemake_resolved.yaml`, written by
`write_snakemake_config_overrides`) as its sole `--configfile`.  `flexpipe-run` also injects via
`--config`:
- `workdir=<path>` — per-run output directory
- `build_config=<abs path>` — path to the original build `config.yaml` (passed to all `flexpipe-*`
  CLI subprocesses so they can load the full config)
- `run_date=<YYYY-MM-DD>` — reference date; used by the `resolve_subsample_config` rule to inject
  `defaults.max_date` into the workdir-local subsample config before `augur subsample` runs

All output paths are prefixed with `{workdir}/results/...` or `{workdir}/config/...`; the source
tree is never written to.

**Data source switching** (controlled by `data_source` in `config.yaml`; only one active):
- `fetch_pathoplexus`: downloads from Pathoplexus/LAPIS (chunked pagination with rate-limiting)
- `fetch_ncbi`: downloads from NCBI Entrez by taxid

Each rule calls the corresponding `flexpipe-*` console script (e.g. `flexpipe-fetch-pathoplexus`,
`flexpipe-curate`, `flexpipe-coordinates`). The config file path is passed via `params.cfg = _config`
(which is the `build_config` injected by `flexpipe-run`, or `workflow.configfiles[0]` for direct
`snakemake` invocations).

**Merge local sequences** (optional):
- `flexpipe-merge`: combines remote data with local surveillance sequences
- Supports two ITpS metadata formats (xlsx and TSV) with auto-detection
- Authority: FASTA file; only sequences present in FASTA are included

**Quality control via ViralQC**:
- Runs `vqc` in the `viralQC` conda environment; vendored as a git submodule at `viralQC/`
- Outputs genome quality grades (A–D) and Nextclade clade assignments
- ViralQC datasets resolution order: `viralqc.datasets_dir` config key → `$VIRALQC_DATASETS_DIR` → `viralQC/datasets/` (auto-discovered from submodule)
- Set up with: `bash scripts/install_viralqc.sh` (creates env, downloads datasets, runs tests)

**Curation** (`flexpipe-curate` / `flexpipe.curate.pipeline`):
- Renames fields via `augur curate rename` (accessionVersion→strain, geoLocCountry→country, etc.)
- Formats dates via `augur curate format-dates`
- Joins ViralQC results (genome_quality, coverage, clade)
- Computes `clade_truncated` by truncating hierarchical clades to `clade_levels` levels (config)
- Assigns `region` from either country→continent (global) or division→Brazilian macro-region (Brazil-only)
- Marks sequence `source` (Pathoplexus, NCBI, or ITpS)
- Deduplicates, preferring local ITpS records

**Subsampling** (`augur subsample`):
- The `resolve_subsample_config` rule writes a workdir-local copy of `builds/<name>/subsample.yaml`
  to `<workdir>/config/subsample_resolved.yaml`, injecting `defaults.max_date = run_date` when
  `run_date` is provided.  This bounds the analysis window without modifying the source tree.
- The `prepare` rule reads the resolved subsample config (not the original build file).
- For YFV Brazil: subsamples by division (state) and year
- Generates subsampled metadata and sequences in `<workdir>/results/subsampled/`

**Colors and coordinates** (can be run in parallel):
- `flexpipe-name2hue`: deterministic hue assignment from subsampled metadata
- `flexpipe-colours`: produces hex colors for all metadata values
- `flexpipe-coordinates`: geocodes metadata locations via Nominatim with:
  - Rate-limiting (1 req/sec compliance)
  - Persistent cache (`<workdir>/cache/cache_coordinates.tsv`) with incremental updates seeded from `builds/<name>/cache_coordinates.tsv`
  - Featuretype hints (division→state, location→city) to reduce ambiguity
  - Fallback to cached or manual entries

### Phylogenetic Pipeline (`phylogenetic/Snakefile`)

**Inputs** (produced by ingest; treated as static):
- `<workdir>/results/subsampled/sequences.fasta`
- `<workdir>/results/subsampled/metadata.tsv`

**Workflow steps**:
1. **align**: MAFFT alignment to reference
2. **mask**: mask terminal regions (e.g., YFV: 142bp 5′, 548bp 3′; configurable per pathogen)
3. **tree**: IQ-TREE 3 with UFBoot (model, bootstrap replicates from config)
4. **refine**: TreeTime temporal calibration (root method, coalescent model, date inference, clock outlier filtering)
5. **ancestral**: nucleotide mutation reconstruction
6. **translate**: amino acid mutations
7. **traits**: ancestral state inference for geographic/clade traits
8. **clades**: branch label assignment via `augur clades` (mutation-based)
9. **export**: `augur export v2` → `<workdir>/auspice/results.json`

All parameters are in `builds/<name>/config.yaml` under `parameters` and `options`.

### Entry Points (`flexpipe/cli.py`)

| Command | Module |
|---------|--------|
| `flexpipe-run` | `flexpipe.run.main` |
| `flexpipe-fetch-pathoplexus` | `flexpipe.ingest.pathoplexus.main` |
| `flexpipe-fetch-ncbi` | `flexpipe.ingest.ncbi.main` |
| `flexpipe-merge` | `flexpipe.ingest.merge.main` |
| `flexpipe-curate` | `flexpipe.curate.pipeline.main` |
| `flexpipe-qc-summary` | `flexpipe.curate.qc_summary.main` |
| `flexpipe-coordinates` | `flexpipe.geo.coordinates.main` |
| `flexpipe-update-cache` | inline argparse → `flexpipe.geo.cache.merge_coordinate_cache` |
| `flexpipe-name2hue` | `flexpipe.colors.hues.main` |
| `flexpipe-colours` | `flexpipe.colors.scheme.main` |

### Configuration Patterns

**Region source** (controls how `region` column is derived):
- `"country"`: country → continent mapping (global builds); loaded from `flexpipe/data/regions/country_to_continent.tsv`
- `"division"`: Brazilian state → macro-region (Norte, Nordeste, Centro-Oeste, Sudeste, Sul); loaded from `flexpipe/data/regions/brazil_state_to_region.tsv`

**Clade truncation**:
- `clade_levels: N` in config → `clade_truncated` column (e.g., A.B.C.D with `clade_levels: 2` → A.B)
- YFV uses `clade_levels: 1` (single-level genotypes: I, II, III, etc.)

**Colour hierarchy** (`colours` in config):
- Top-level categories get manual hues (loaded from `flexpipe/data/colors/*_hues.tsv`)
- Sub-levels derive colors as gradients
- Lineage/clade use hash-based deterministic hues (same name → same hue across runs)

**PPX column contract**: Pathoplexus-style column names (`accessionVersion`, `geoLocCountry`, `geoLocAdmin1`, `geoLocAdmin2`, `dataUseTerms`, `lineage`) flow through the pipeline without modification until renamed by `augur curate rename` in the `curate_qc` rule. Never change these column names in ingest/merge logic.

**Workdir isolation**: All generated artifacts (results, latlongs, colour_scheme, logs, manifest, coordinate cache) go to `<workdir>/`. The build directory (`builds/<name>/`) is read-only. The source tree is never modified during a run.

**Workdir locking**: `flexpipe-run` acquires `<workdir>/.flexpipe.lock` (via `filelock.FileLock`, timeout=0) before invoking Snakemake. A second concurrent `flexpipe-run` on the same workdir exits immediately with code 2. `--nolock` is passed to Snakemake because its native lock is scoped to the invocation directory, not the workdir.

**Segmented viruses (out of scope for v0.x)**: The pipeline uses a single reference / single alignment / single tree. For segmented viruses, run one build per segment. Set `viralqc.expected_segment` to flag wrong-segment reads via ViralQC; the rest of the pipeline has no per-segment fan-out or reassortment handling.

**QC summary artifact**: After `augur filter`, the `qc_summary` rule runs `flexpipe-qc-summary` to produce `<workdir>/results/qc_report.json` (grade counts, coverage stats, filter-reason breakdown) and `<workdir>/results/qc_summary.tsv` (flat per-grade table). Always generated as part of `rule all`.

## Adapting for a New Pathogen

```bash
cp -r builds/yfv-brazil builds/my-pathogen
# edit: config.yaml, subsample.yaml, reference.gb, clades.tsv, auspice_config.json
flexpipe-run --config builds/my-pathogen/config.yaml --workdir /tmp/my-run
```

Key fields to update in `config.yaml`:
- `data_source` (pathoplexus or ncbi)
- `pathoplexus.organism` / `ncbi.taxid`
- `parameters.mask_5prime/3prime` (terminal masking in bp; **reference-specific** — set 0 and calibrate for each new reference)
- `parameters.mask_sites_file` (optional BED file of problematic sites; leave blank if unused)
- `curation.clade_levels` (hierarchy depth for `clade_truncated`)
- `qc.min_sequences` (minimum subsampled sequences before phylogenetics; default 10; 0 disables)
- `region_source` (country for global, division for Brazil-only builds)
- `viralqc.expected_virus` (ViralQC rejects sequences not matching this virus)
- `viralqc.expected_segment` (single segment label for single-segment builds; leave blank for non-segmented viruses)
- `viralqc.*` (or set `VIRALQC_DATASETS_DIR`)
- `traits.columns` (which metadata fields to infer ancestral states for)

## Dependencies

- **Conda environments**:
  - `nextstrain`: augur ≥13, snakemake, iqtree3, mafft, python ≥3.9, plus all deps in `config/nextstrain.yml`
  - `viralQC`: bundled as a git submodule (`viralQC/`); set up via `bash scripts/install_viralqc.sh` (not a conda package)
- **Pip-installable** (in `pyproject.toml` `[project.dependencies]`): pandas, pyyaml, biopython, geopy, requests, matplotlib ≥3.9, colour, openpyxl, beautifulsoup4, pydantic ≥2, filelock
- **External APIs**:
  - Pathoplexus/LAPIS (HTTP)
  - NCBI Entrez (HTTP; email + optional API key recommended)
  - Nominatim/OpenStreetMap (HTTP; 1 req/sec rate limit enforced)

