# Console Commands

flexpipe provides 16 console-line tools for running the pipeline and working with individual processing steps. Most are called automatically by `flexpipe-run`, but you can invoke them directly for debugging, testing, or custom workflows.

## Main Orchestrator

### flexpipe-run

Runs the full pipeline (ingest + phylogenetics) end-to-end with workdir locking.

```bash
flexpipe-run \
  --config builds/yfv-brazil/config.yaml \
  --workdir /tmp/yfv-run \
  --run-date 2026-01-01 \
  --stage all \
  --cores 4 \
  --log-level INFO
```

| Flag | Type | Default | Purpose |
|------|------|---------|---------|
| `--config` | PATH | (required) | Build config file (e.g., `builds/yfv-brazil/config.yaml`) |
| `--workdir` | PATH | (required) | Output directory |
| `--run-date` | YYYY-MM-DD | today | Upper date bound for subsampling (subsample only) |
| `--stage` | {ingest,phylo,all} | `all` | Which stage(s) to run |
| `--cores` | INT | auto | Number of CPU cores for Snakemake |
| `--log-level` | {DEBUG,INFO,WARNING,ERROR} | `INFO` | Logging verbosity |

**Workdir lock**: Acquires exclusive lock at `<workdir>/.flexpipe.lock`. Second invocation exits with code 2.

## Ingest Sub-Commands

These commands are called by the ingest Snakefile but can be invoked standalone for testing:

### flexpipe-fetch-pathoplexus

Fetch sequences from Pathoplexus/LAPIS:

```bash
flexpipe-fetch-pathoplexus \
  --config builds/yfv-brazil/config.yaml \
  --metadata-output results/metadata.tsv \
  --sequences-output results/sequences.fasta
```

### flexpipe-fetch-ncbi

Fetch sequences from NCBI Entrez by taxid:

```bash
flexpipe-fetch-ncbi \
  --config builds/yfv-brazil/config.yaml \
  --metadata-output results/metadata.tsv \
  --sequences-output results/sequences.fasta
```

Requires `NCBI_EMAIL` environment variable. Optional: `NCBI_API_KEY` for higher rate limits.

### flexpipe-merge

Merge local surveillance sequences (ITpS format) with remote data:

```bash
flexpipe-merge \
  --config builds/yfv-brazil/config.yaml \
  --remote-metadata results/metadata.tsv \
  --remote-sequences results/sequences.fasta \
  --metadata-output merged_metadata.tsv \
  --sequences-output merged_sequences.fasta
```

Supports ITpS Excel (`.xlsx`) and TSV formats; auto-detects format.

### flexpipe-curate

Normalize metadata, join ViralQC results, assign regions, parse lineages, and deduplicate:

```bash
flexpipe-curate \
  --config builds/yfv-brazil/config.yaml \
  --metadata raw_metadata.tsv \
  --nextclade viralqc_results.tsv \
  --output curated_metadata.tsv
```

### flexpipe-normalize-dates

Parse flexible date formats and normalize to YYYY-MM-DD:

```bash
flexpipe-normalize-dates \
  --metadata metadata.tsv \
  --date-column collectionDate \
  --date-formats dates.yaml \
  --output normalized.tsv
```

Logs ambiguous/unparseable dates to a separate file.

### flexpipe-qc-summary

Generate QC statistics summary from curation output:

### flexpipe-filter-clade

Keep or drop sequences by a metadata-column value, upstream of subsampling:

```bash
flexpipe-filter-clade \
  --config builds/measles-b3-global/config.yaml \
  --metadata results/ingest/final_metadata.tsv \
  --sequences results/ingest/final_sequences.fasta \
  --output-metadata results/ingest/clade_filtered_metadata.tsv \
  --output-sequences results/ingest/clade_filtered_sequences.fasta \
  --log results/ingest/clade_filter_log.tsv
```

| Flag | Purpose |
|------|---------|
| `--config` | Build config.yaml (reads `clade_filter` section) |
| `--metadata` | Input metadata TSV (curated + QC-filtered) |
| `--sequences` | Input FASTA |
| `--output-metadata` | Filtered metadata output |
| `--output-sequences` | Filtered FASTA output |
| `--log` | Per-strain drop log TSV (`strain`, `group_value`, `drop_reason`; header-only when nothing dropped) |

When `clade_filter.column` is empty or absent from the config, all sequences pass through unchanged.

```{note}
`flexpipe-filter-clade` is called automatically by the `clade_filter` rule in `ingest/Snakefile` for every build. Direct invocation is useful for debugging filter behavior on a curated metadata file before a full run.
```

```bash
flexpipe-qc-summary \
  --metadata curated_metadata.tsv \
  --output qc_summary.tsv
```

## Visualization Helpers

### flexpipe-coordinates

Geocode locations (country, division, location) via Nominatim with rate-limiting and caching:

```bash
flexpipe-coordinates \
  --metadata metadata.tsv \
  --latitude-column latitude \
  --longitude-column longitude \
  --output latlongs.tsv
```

**Caching**: Reads seed cache from `flexpipe/data/geo/cache_coordinates.tsv`, then `builds/<name>/cache_coordinates.tsv`, then Nominatim API. Updates cache at runtime.

### flexpipe-update-cache

Merge coordinate caches from multiple runs:

```bash
flexpipe-update-cache \
  --new-cache cache_from_run1.tsv \
  --existing-cache shared_cache.tsv \
  --output merged_cache.tsv
```

### flexpipe-name2hue

Assign deterministic hues to metadata values for consistent coloring:

```bash
flexpipe-name2hue \
  --metadata metadata.tsv \
  --output name2hue.tsv
```

### flexpipe-colours

Generate hex colors for all metadata values based on hierarchy and hue assignments:

```bash
flexpipe-colours \
  --metadata metadata.tsv \
  --hues name2hue.tsv \
  --color-scheme colours \
  --output colour_scheme.tsv
```

## Phylogenetic Helpers

### flexpipe-collapse-traits

Collapse rare states in a traits column before TreeTime inference:

```bash
flexpipe-collapse-traits \
  --metadata metadata.tsv \
  --trait-column division \
  --max-states 10 \
  --rare-state-label "Other" \
  --output metadata_traits.tsv
```

### flexpipe-reference-slice

Extract a gene or coordinate window from a whole-genome `reference.gb`, producing a
gene-only GenBank record and an optional gene-relative terminal mask BED.  Used to
prepare the `reference.gb` for a fragment-mode build.

```bash
flexpipe-reference-slice \
    --reference  builds/measles-b3-global/reference.gb \
    --region     1233..1682 \
    --gene       N  --feature-type CDS \
    --new-id     NC_001498.1 \
    --output-reference  builds/measles-b3-n450-global/reference.gb \
    --output-bed        builds/measles-b3-n450-global/masks/reference_terminal.bed
```

| Flag | Default | Purpose |
|------|---------|---------|
| `--reference` | (required) | Source whole-genome GenBank file |
| `--region` | `""` | 1-based inclusive coordinates `START..END` (e.g. `1233..1682`); overrides `--gene` |
| `--gene` | `""` | `/gene` qualifier to locate the slice automatically |
| `--feature-type` | `CDS` | Feature type searched when using `--gene` |
| `--new-id` | source ID | Record ID for the output |
| `--output-reference` | (required) | Path to write the gene-only GenBank |
| `--output-bed` | `""` | Optional: path to write a gene-relative terminal mask BED |
| `--profile` | `default` | Mask profile for `--output-bed` |
| `--profile-file` | `""` | Override mask profiles YAML path |

The output record is in **gene-relative coordinates** (position 1 = `START` in the
source).  A CDS spanning the full slice is synthesized if no CDS survives Biopython's
slice (required by `augur translate`).

For a tight coding window (no UTR flanks), the BED written by `--output-bed` will be
empty — this is correct and harmless.

See [Fragment Analysis](pipeline/fragment-analysis.md) for the full workflow.

### flexpipe-reference-mask

Generate terminal masking BED file from a reference genome (GenBank):

```bash
flexpipe-reference-mask \
  --reference reference.gb \
  --profile default \
  --output masks/reference_terminal.bed
```

Uses default reference-mask profile (`flexpipe/data/phylo/reference_mask_profiles.yaml`) to identify UTRs and compute terminal regions.

```{warning}
Generated masks should be reviewed manually before use in production. Profile heuristics may not match all genome structures.
```

## Validation

### flexpipe-validate-build

Validate a build config and verify that all referenced files exist:

```bash
flexpipe-validate-build builds/yfv-brazil/config.yaml
```

Checks:
- Config syntax and types
- Required files (reference, clades, subsample.yaml, auspice_config.json)
- Metadata column names (post-curation)
- Data source prerequisites (taxid for NCBI, organism for Pathoplexus, etc.)

Useful before adding a new pathogen.
