# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**flexpipe** is a flexible Nextstrain pipeline for genomic epidemiology of viral pathogens. It supports:
- Data ingestion from Pathoplexus, NCBI, or local surveillance sequences
- Automated quality control via ViralQC (BLAST + Nextclade)
- Complete phylogenetic workflow producing Auspice-compatible JSON for visualization

The pipeline is an **installable Python package** (`pip install -e .`) backed by two Snakemake workflows:
1. **Ingest** (`ingest/Snakefile`): fetches data, merges local sequences, performs QC/curation, subsampling, and generates colors/coordinates
2. **Phylogenetic** (`phylogenetic/Snakefile`): alignment, masking, tree building, temporal calibration, and export

All outputs go to a **per-build workdir** — the source tree is never modified at runtime.

Current example build: **Yellow Fever Virus (YFV) Brazil** (`builds/yfv-brazil/`)

## Common Commands

### Environment Setup
```bash
# Clone with the viralQC submodule (or run: git submodule update --init --recursive)
git clone --recurse-submodules https://github.com/InstitutoTodosPelaSaude/flexpipe.git

# Reproducible install (pinned versions — recommended for production/scheduled runs)
conda env create -f config/nextstrain.lock.yml
conda activate nextstrain

# Flexible/dev install (accepts newer versions — use during active development)
# conda env create -f config/nextstrain.yml

# Install the flexpipe package (editable, with dev + test extras)
pip install -e '.[test,dev]'

# Set up the bundled viralQC submodule (creates env, downloads datasets, runs tests)
bash scripts/install_viralqc.sh
```

### Running the Full Pipeline

```bash
# Run ingest + phylogenetics end-to-end for the YFV Brazil build.
# --run-date bounds the analysis window: sequences collected after this date
# are excluded from subsampling via augur subsample's defaults.max_date.
# Always pass --run-date explicitly for scheduled/reproducible reruns.
flexpipe-run \
    --config   builds/yfv-brazil/config.yaml \
    --workdir  /path/to/workdir/yfv-brazil \
    --run-date 2026-01-01

# Visualize results
auspice view --datasetDir /path/to/workdir/yfv-brazil/auspice/
# Open http://localhost:4000 in browser
```

**`--run-date` semantics:** format is `YYYY-MM-DD`; scope is subsample only (phylo receives it
for forward-compatibility but does not use it). Omitting it defaults to today with a warning; two
runs with the same `--run-date` and the same config produce the same `config_hash` and `run_id`
in the manifest. When not passed, `augur subsample` has no upper date bound.

**`--backbone-from` semantics:** opt-in stable backbone — pass the workdir of a previous run to
force-include its subsampled strain list in the new subsample.  The new subsample becomes the
union of *(stable backbone strains) + (freshly-selected new sequences)*, making results comparable
across runs (e.g. a 2-year-later rerun of an RSV build).

```bash
# Run A (initial build — e.g. June 2024)
flexpipe-run \
    --config   builds/rsv-a-brazil/config.yaml \
    --workdir  /path/to/workdir/rsv-A \
    --run-date 2024-06-01

# Run B (2 years later — backbone anchors the 2024 selection)
flexpipe-run \
    --config        builds/rsv-a-brazil/config.yaml \
    --workdir       /path/to/workdir/rsv-B \
    --run-date      2026-06-01 \
    --backbone-from /path/to/workdir/rsv-A
```

Key limitations of `--backbone-from`:
- **Best-effort retention:** strains dropped by upstream QC (`augur filter`) or
  `clade_filter` cannot be force-kept — `include` only applies within `augur subsample`.
  Backbone retention is bounded by the quality contract.
- **Runtime-only:** never put the backbone path in `builds/<name>/config.yaml` (it bakes a
  machine-specific absolute path into version control).  Always pass it via the CLI flag.
- **Self-reference guard:** pointing `--backbone-from` at the current workdir exits with code 2.
- **Missing previous run:** a warning is logged and the run proceeds without a backbone.

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

# Run integration dry-run wiring tests (requires nextstrain env + snakemake)
pytest -m integration

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
  curate/{regions,hosts,clades,columns,viralqc_join,pipeline}.py
  geo/{coordinates,cache}.py
  colors/{hues,scheme}.py
  data/                  # bundled defaults (shipped via hatchling force-include)
    regions/{country_to_continent.tsv, brazil_state_to_region.tsv, brazil_abbreviations.tsv}
    hosts/host_rules.yaml
    colors/{region_hues.tsv, host_hues.tsv, source_hues.tsv, data_use_hues.tsv}
    curation/date_formats.yaml
    geo/cache_coordinates.tsv
    phylo/reference_mask_profiles.yaml
    viralqc/aliases.yaml
builds/
  yfv-brazil/
    config.yaml          # all parameters for this build
    subsample.yaml
    auspice_config.json
    clades.tsv
    reference.gb
    keep.txt  ignore.txt
    cache_coordinates.tsv   # read-only seed; workdir copy updated at runtime
config/
  nextstrain.yml         # conda environment definition (shared)
ingest/Snakefile
phylogenetic/Snakefile
tests/{unit/, golden/, integration/, fixtures/}
  integration/test_ingest_wiring.py   # dry-run wiring tests (pytest -m integration)
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

The Snakefile reads `builds/yfv-brazil/config.yaml` as its configfile and accepts two keys via
`--config`:
- `workdir=<path>` — per-run output directory
- `build_config=<abs path>` — absolute path to the build `config.yaml`, injected by `flexpipe-run`

All output paths are prefixed with `{workdir}/results/...` or `{workdir}/config/...`; the source
tree is never written to.

**Config wiring**: `flexpipe-run` invokes Snakemake with a **single** `--configfile`:
- `<workdir>/config/snakemake_resolved.yaml` — written by `write_snakemake_config_overrides()`;
  contains the **full** build `config.yaml` content merged with pydantic-resolved ViralQC paths.
  Snakemake 9+ only loads the last `--configfile` when multiple are passed, so a single complete
  file is required (Snakefiles have no `configfile:` directive).

`flexpipe-*` CLI subprocesses (e.g. `flexpipe-curate`) need the original build `config.yaml`
path, not the workdir-local resolved snapshot. The Snakefile reads
`_config = config.get("build_config")` (injected via `--config build_config=<abs path>`) for all
`params.cfg` values. Direct `snakemake` invocations fall back to `workflow.configfiles[0]`.

**Data source switching** (controlled by `data_source` in `config.yaml`; only one active):
- `fetch_pathoplexus`: downloads from Pathoplexus/LAPIS (chunked pagination with rate-limiting)
- `fetch_ncbi`: downloads from NCBI Entrez by taxid

**Merge local sequences** (optional):
- `flexpipe-merge`: combines remote data with local surveillance sequences
- Supports two ITpS metadata formats (xlsx and TSV) with auto-detection
- Authority: FASTA file; only sequences present in FASTA are included

**Quality control via ViralQC**:
- Runs `vqc` in the `viralQC` conda environment; vendored as a git submodule at `viralQC/`
- Outputs genome quality grades (A–D) and Nextclade clade assignments
- ViralQC datasets resolution order: `viralqc.datasets_dir` config key → `$VIRALQC_DATASETS_DIR` → `viralQC/datasets/` (auto-discovered from submodule)
- `viralqc.expected_virus` and `viralqc.expected_segment` are alias-aware. Built-in aliases live
  in `flexpipe/data/viralqc/aliases.yaml`; use `viralqc.aliases_file` for overrides. Prefer
  operational keys (`rsv_a`, `flu_a_h1n1`, `ha`) when ViralQC labels vary. ICTV species names are
  metadata in the registry, not broad match keys unless explicitly listed as aliases.
- Set up with: `bash scripts/install_viralqc.sh` (creates env, downloads datasets, runs tests)

**Curation** (`flexpipe-curate` / `flexpipe.curate.pipeline`):
- Renames fields via `augur curate rename` (accessionVersion→strain, geoLocCountry→country, etc.)
- Normalizes flexible dates with `flexpipe-normalize-dates` before `augur curate format-dates`;
  failures and ambiguous slash dates are logged to `<workdir>/results/ingest/date_normalization.tsv`.
- Joins ViralQC results (genome_quality, coverage, clade)
- Computes `clade_truncated` by truncating hierarchical clades to `clade_levels` levels (config)
- Assigns `region` from either country→continent (global) or division→Brazilian macro-region (Brazil-only)
- Marks sequence `source` (Pathoplexus, NCBI, or ITpS)
- Deduplicates, preferring local ITpS records

**Subsampling** (`augur subsample`):
- Reads `builds/<name>/subsample.yaml`
- For YFV Brazil: subsamples by division (state) and year
- Generates subsampled metadata and sequences in `<workdir>/results/subsampled/`
- **Backbone support** (`--backbone-from`): when enabled, `resolve_subsample_config` injects a
  synthetic `samples.__backbone__: {include: <workdir>/config/backbone_strains.txt}` entry so
  `augur subsample` force-keeps the previous run's strains regardless of group caps.
  The `backbone_strains.txt` file is written by `_materialize_backbone()` in `run.py` before
  Snakemake is invoked; `SubsamplingConfig.backbone_strains` carries the path through the
  resolved config to the Snakefile.  Feature is a complete no-op when `backbone_strains` is
  `None` (the default).

**Colors and coordinates** (can be run in parallel):
- `flexpipe-name2hue`: deterministic hue assignment from subsampled metadata
- `flexpipe-colours`: produces hex colors for all metadata values
- `flexpipe-coordinates`: geocodes metadata locations via Nominatim with:
  - Rate-limiting (1 req/sec compliance)
  - Persistent cache (`<workdir>/cache/cache_coordinates.tsv`) seeded from the bundled shared
    cache (`flexpipe/data/geo/cache_coordinates.tsv`) first and `builds/<name>/cache_coordinates.tsv`
    second, so build-specific manual entries win
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
| `flexpipe-normalize-dates` | `flexpipe.curate.dates.main` |
| `flexpipe-qc-summary` | `flexpipe.curate.qc_summary.main` |
| `flexpipe-coordinates` | `flexpipe.geo.coordinates.main` |
| `flexpipe-update-cache` | inline argparse → `flexpipe.geo.cache.merge_coordinate_cache` |
| `flexpipe-name2hue` | `flexpipe.colors.hues.main` |
| `flexpipe-colours` | `flexpipe.colors.scheme.main` |
| `flexpipe-collapse-traits` | `flexpipe.phylo.traits.main` |
| `flexpipe-reference-mask` | `flexpipe.phylo.reference_mask.main` |
| `flexpipe-reference-slice` | `flexpipe.phylo.reference_slice.main` |

### Configuration Patterns

**Region source** (controls how `region` column is derived):
- `"country"`: country → continent mapping (global builds); loaded from `flexpipe/data/regions/country_to_continent.tsv`
- `"division"`: Brazilian state → macro-region (Norte, Nordeste, Centro-Oeste, Sudeste, Sul); loaded from `flexpipe/data/regions/brazil_state_to_region.tsv`
- `continent` is always derived separately from `country` when possible. For Brazil builds,
  `region` remains the Brazilian macro-region while `continent` is the geographic continent.

**Clade truncation**:
- `clade_levels: N` in config → `clade_truncated` column (e.g., A.B.C.D with `clade_levels: 2` → A.B)
- YFV uses `clade_levels: 1` (single-level genotypes: I, II, III, etc.)

**Colour hierarchy** (`colours` in config):
- Configure levels from most-general to most-specific, e.g. `continent country division location`
  or `serotype genotype major_lineage minor_lineage clade`.
- Top-level categories get fixed hues when available (`region_hues.tsv` also contains continents)
  or stable hash hues persisted in the workdir `name2hue.tsv` cache.
- Sub-levels derive deterministic shades within the top-level hue family.
- Raw lineage stays in `clade`; optional parsers add prefix-safe lineage columns for filters/colors.

**Trait state cap** (`traits` in config):
- `traits.columns` drives `augur traits`, but flexpipe first writes
  `<workdir>/results/subsampled/metadata_traits.tsv`.
- If a trait has more than `traits.max_states` non-empty states, rare states are collapsed to
  `traits.rare_state_label` in that sidecar only; primary subsampled metadata is not mutated.

**Reference-derived masks**:
- `flexpipe-reference-mask` can generate first-draft terminal BED masks from `reference.gb`.
- The default profile (`flexpipe/data/phylo/reference_mask_profiles.yaml`) checks explicit UTR
  features, UTR-like qualifiers on features such as `gene`/`misc_feature`, then CDS/gene boundary
  fallback. It emits terminal masks only by default and refuses excessive mask fractions.
- Generated BEDs should be reviewed before production surveillance use, then referenced via
  `parameters.mask_sites_file`.

**Gene / fragment analysis mode** (`mode` in config):
- Default `mode: "whole-genome"` — standard pipeline; QC gates on `genome_quality` / `coverage`.
- `mode: "fragment"` — opt-in gene/region mode:
  - Requires `viralqc.mode: run` (skip/precomputed forbidden in v1).
  - Requires a Nextclade dataset declaring `target_gene` for the virus; `flexpipe-validate-build`
    errors if none is found (`_check_fragment_dataset` in `flexpipe/validate.py`).
  - ViralQC's `sequences_target_regions.fasta` is used as the sequence source in `curate_qc`.
  - `join_viralqc` adds `target_gene_coverage`, `target_gene_quality`, `target_gene` columns.
  - `augur filter` thresholds on `target_gene_coverage ≥ fragment.min_target_coverage` and
    `target_gene_quality` in `fragment.target_quality`.
  - `reference.gb` must be a gene-only slice produced by `flexpipe-reference-slice`.
  - All phylo pipeline steps are unchanged; `augur align` reframes to gene coordinates.
  - Reference build: `builds/measles-b3-n450-global/` (measles N450, 450 nt).
  - `flexpipe-reference-slice` extracts a gene window from a whole-genome `reference.gb`:
    `--region 1233..1682 --gene N` → 450-nt GenBank + gene-relative terminal mask BED.

**PPX column contract**: Pathoplexus-style column names (`accessionVersion`, `geoLocCountry`, `geoLocAdmin1`, `geoLocAdmin2`, `dataUseTerms`, `lineage`) flow through the pipeline without modification until renamed by `augur curate rename` in the `curate_qc` rule. Never change these column names in ingest/merge logic.

**Workdir isolation**: All generated artifacts (results, latlongs, colour_scheme, logs, manifest, coordinate cache) go to `<workdir>/`. The build directory (`builds/<name>/`) is read-only. The source tree is never modified during a run.

## Adapting for a New Pathogen

```bash
cp -r builds/yfv-brazil builds/my-pathogen
# edit: config.yaml, subsample.yaml, reference.gb, clades.tsv, auspice_config.json
flexpipe-run --config builds/my-pathogen/config.yaml --workdir /tmp/my-run
```

Key fields to update in `config.yaml`:
- `data_source` (pathoplexus or ncbi)
- `pathoplexus.organism` / `ncbi.taxid`
- `parameters.mask_5prime/3prime` (terminal masking in bp; 0 for full-genome) — **these values
  are per-reference**: YFV uses 142/548 (X03700.1); you must re-derive them for any new reference
- `parameters.mask_sites_file` (optional BED file path for generated terminal masks or
  problematic-site masking; leave blank if unused)
- `curation.clade_levels` (hierarchy depth for `clade_truncated`)
- `curation.lineage_parser` (`none`, `dengue`, `pango`, `generic_dot`) for optional derived lineage
  columns; DENV outputs are prefix-safe (e.g. `3III_B.3.2`, not bare `B`)
- `curation.date_formats` (optional override for date-normalization policy)
- `region_source` (country for global, division for Brazil-only builds)
- `qc.min_sequences` (minimum subsampled sequences required before phylogenetics; default 10)
- `coordinates.shared_cache` (optional shared geocode seed cache override)
- `viralqc.expected_virus` / `viralqc.expected_segment` (alias keys or literal labels)
- `viralqc.aliases_file` (optional override for ViralQC label aliases)
- `viralqc.*` (or set `VIRALQC_DATASETS_DIR`)
- `traits.columns` (which metadata fields to infer ancestral states for)
- `traits.max_states` / `traits.rare_state_label` (TreeTime-safe categorical cap)
- `mode` (`"whole-genome"` default; `"fragment"` for gene/region builds — see Gene/Fragment Analysis
  Mode section above)
- `fragment.target_gene` (required when `mode: fragment`; `/gene` qualifier in the ViralQC dataset)
- `fragment.min_target_coverage` (default 0.70; minimum fraction of target gene covered)
- `fragment.target_quality` (default `["A","B"]`; passing `targetGeneQuality` grades)

## Dependencies

- **Conda environments**:
  - `nextstrain` (flexible install): `conda env create -f config/nextstrain.yml` — floor versions; accepts newer packages
  - `nextstrain` (reproducible install): `conda env create -f config/nextstrain.lock.yml` — version-pinned, cross-platform spec; preferred for production/scheduled runs
  - `viralQC`: bundled as a git submodule (`viralQC/`); set up via `bash scripts/install_viralqc.sh` (not a conda package)
- **Pip-installable** (in `pyproject.toml` `[project.dependencies]`): pandas, pyyaml, biopython, geopy, requests, matplotlib ≥3.9, colour, openpyxl, beautifulsoup4, pydantic ≥2
  - Pinned versions for production: `requirements.lock.txt` (regenerate via `pip freeze` when bumping `pyproject.toml` deps)
- **External APIs**:
  - Pathoplexus/LAPIS (HTTP)
  - NCBI Entrez (HTTP; email + optional API key recommended)
  - Nominatim/OpenStreetMap (HTTP; 1 req/sec rate limit enforced)

## Versioning

Package version is managed via **hatch-vcs** (`dynamic = ["version"]` in `pyproject.toml`). The version is derived from git tags:
- `git tag v0.2.0 && git push --tags` — tag the release; hatch-vcs resolves `0.2.0` at install time
- Without a tag, the installed version is a dev string (e.g. `0.1.dev65+g50db586`)
- In environments without `.git` (e.g. Docker), set `SETUPTOOLS_SCM_PRETEND_VERSION=0.2.0` before `pip install`

## Segmented viruses (out of scope for v0.x)

The ViralQC join supports per-segment contamination filtering via `viralqc.expected_segment`
(e.g. `"L"` for Lassa virus L segment) — sequences with a non-matching segment are flagged
`genome_quality="D"` and excluded. However, the rest of the pipeline (single reference, single
MAFFT alignment, single IQ-TREE tree) has **no per-segment fan-out or reassortment handling**.
Multi-segment builds must be run as **separate single-segment builds** (one per segment, each
with its own reference, clades, and workdir).

## Workdir locking

`flexpipe-run` acquires a workdir-level lock (`<workdir>/.flexpipe.lock`) using `filelock` before
running Snakemake. A second `flexpipe-run` targeting the same workdir exits with code 2 immediately
rather than corrupting the ongoing run. Snakemake's native `--nolock` flag is still passed
because its own lock is scoped to the process invocation directory, not the workdir.

## Lock file maintenance

```bash
# Regenerate nextstrain.lock.yml after bumping nextstrain.yml
conda env create -f config/nextstrain.yml -n nextstrain-fresh
conda list -n nextstrain-fresh --no-pip | awk 'NR>3 {print $1, $2}'
# Update pinned versions in config/nextstrain.lock.yml from the output above
conda env remove -n nextstrain-fresh

# Regenerate requirements.lock.txt after bumping pyproject.toml deps
pip freeze | grep -E "^(pandas|PyYAML|biopython|geopy|requests|matplotlib|colour|openpyxl|beautifulsoup4|pydantic)==" | sort > requirements.lock.txt
# Append dev/test deps manually
```
