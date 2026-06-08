# Architecture

## Overview

flexpipe uses a two-stage, **workdir-isolated** design:

1. **Build directory** (`builds/<name>/`): read-only configuration and static data (reference genome, clade definitions, subsampling rules)
2. **Workdir** (`<workdir>/`): per-run outputs (results, logs, coordinate cache, resolved config)

The source tree is never modified at runtime. Each run creates a fresh workdir with its own outputs and an isolated lock file.

## Two-Stage Pipeline

```{mermaid}
graph LR
    A["Ingest Stage<br/>(data_source → QC → curation)"] -->|subsampled metadata<br/>+ sequences| B["Phylogenetic Stage<br/>(align → tree → refine)"]
    B -->|auspice/results.json| C["Visualization<br/>(auspice view)"]
```

### Ingest Stage

Fetches data, performs quality control, normalizes metadata, and subsamples sequences for phylogenetic analysis.

**Rules** (in `ingest/Snakefile`):
- `fetch_pathoplexus` or `fetch_ncbi` or `fetch_local` — data ingestion
- `merge_local_sequences` (optional) — combines remote + local surveillance data
- `viralqc` — ViralQC BLAST + Nextclade classification
- `curate_qc` — metadata normalization, lineage parsing, geographic assignment
- `augur filter` + `qc_summary` — genome quality filtering
- `augur subsample` — balanced sampling by geography/time
- `flexpipe-colours` + `flexpipe-coordinates` — color and geocoding (parallel)

**Output**: `<workdir>/results/subsampled/{metadata.tsv,sequences.fasta}`

### Phylogenetic Stage

Builds and calibrates a phylogenetic tree from subsampled sequences.

**Rules** (in `phylogenetic/Snakefile`):
- `augur align` — MAFFT multiple alignment
- `augur mask` — mask terminal + ambiguous regions (or copy if masking is disabled)
- `iqtree3` — maximum-likelihood tree with UFBoot
- `augur refine` — TreeTime temporal calibration
- `augur ancestral` + `augur translate` — mutation reconstruction
- `augur traits` — ancestral state inference for geographic/clade traits
- `augur clades` — clade assignment via mutation criteria
- `augur export v2` — Auspice JSON export

**Output**: `<workdir>/auspice/results.json` (ready for visualization)

## Configuration Resolution

When you run `flexpipe-run --config builds/my-pathogen/config.yaml --workdir /tmp/run`:

1. Load the build config from `builds/my-pathogen/config.yaml`
2. Validate and resolve ViralQC paths (datasets, aliases, env, executable)
3. Write `<workdir>/config/snakemake_resolved.yaml` with the **full** merged config (used by Snakemake)
4. Write `<workdir>/manifest.json` with provenance (config hash, run ID, timestamp)
5. Invoke Snakemake with `--configfile <workdir>/config/snakemake_resolved.yaml`

Snakemake reads `config.get("build_config")` (injected via `--config build_config=<abs path>`) for values like `parameters.mask_5prime` and `viralqc.expected_virus`.

## Workdir Lock

`flexpipe-run` acquires an exclusive lock (`<workdir>/.flexpipe.lock`) using `filelock` before starting. A second invocation targeting the same workdir exits immediately with code 2. This prevents race conditions on ingest/phylo boundaries and manifest updates.

## Data Flow

```{mermaid}
graph TD
    A["Remote API<br/>(Pathoplexus/NCBI)"]
    B["Local Sequences<br/>(ITpS xlsx/TSV)"]
    A -->|fetch| C["Fetch Results"]
    B -->|merge| C
    C -->|viralQC| D["QC Results<br/>(genome_quality, clade)"]
    D -->|curate| E["Normalized Metadata"]
    E -->|augur filter| F["QC Summary"]
    F -->|augur subsample| G["Subsampled Seqs"]
    G -->|align/mask| H["Alignment"]
    H -->|iqtree3| I["Tree"]
    I -->|refine| J["Time-Calibrated Tree"]
    J -->|ancestral/traits| K["Node Data"]
    K -->|export| L["auspice/results.json"]
    L -->|auspice view| M["Interactive Visualization"]
```

## Per-Build Configuration Model

Each build (`builds/<name>/`) is independent and defines:

- **config.yaml** — pipeline parameters (data source, QC thresholds, phylo settings, masking, trait columns)
- **subsample.yaml** — subsampling strategy (group by division/year, sequences per group, include/exclude lists)
- **auspice_config.json** — Auspice display settings (colorings, filters, panels)
- **reference.gb** — reference genome (GenBank format)
- **clades.tsv** — clade definitions (mutation-based branch labels)
- **cache_coordinates.tsv** — geocoding seed cache
- Optional: **masks/reference_terminal.bed** — terminal masking regions (in bp)
- Optional: **keep.txt, ignore.txt** — strain inclusion/exclusion lists

## Run Date Semantics

The `--run-date YYYY-MM-DD` flag controls subsampling window:

- Ingest: `augur subsample` reads `defaults.max_date` from resolved config and uses it to exclude sequences collected after `--run-date`
- Phylo: receives `--run-date` for forward-compatibility but does not use it
- Manifest: `config_hash` and `run_id` are deterministic for the same config + `--run-date`

Omitting `--run-date` defaults to today with a warning.
