# Ingest Pipeline

The ingest stage (`ingest/Snakefile`) fetches raw sequence data, performs quality control, and prepares balanced subsamples for phylogenetic analysis.

## Data Fetching

The first step depends on `data_source` in your config:

### Pathoplexus (LAPIS API)

**Config keys**: `pathoplexus.organism`, `pathoplexus.base_url`, `pathoplexus.query_params`, `pathoplexus.strip_fasta_id_suffix`

Fetches sequences from a [LAPIS](https://docs.nextstrain.org/projects/lapis/en/latest/) instance (e.g., Pathoplexus). Implements:
- Chunked pagination with configurable request size
- Rate-limiting to respect API quotas
- Optional FASTA ID suffix stripping (e.g., remove `|EPI_ISL_123456` after strain name)

**Output**: `results/ingest/{metadata.tsv, sequences.fasta}`

### NCBI Entrez

**Config keys**: `ncbi.taxid`, `ncbi.email`, `ncbi.api_key`, `ncbi.min_date`, `ncbi.extra_search_term`

Fetches sequences by taxonomic ID. Email is required (provide via `ncbi.email` config or `NCBI_EMAIL` env var). API key (via `NCBI_API_KEY` env var) improves rate limits but is optional.

**Output**: `results/ingest/{metadata.tsv, sequences.fasta}`

### Local Data

**Config keys**: `local.metadata`, `local.sequences`

Uses provided TSV (metadata) and FASTA (sequences) files. Authority: FASTA file (only sequences present in FASTA are included).

**Column requirement**: metadata must follow Pathoplexus (ITpS) conventions for column names, as they are renamed by `augur curate rename`:
- `accessionVersion` → `strain`
- `geoLocCountry` → `country`
- `geoLocAdmin1` → `division`
- `geoLocAdmin2` → `location`
- `collectionDate` → `date`

**Output**: files are referenced in-place; no copy rule.

## Merge Local Sequences (Optional)

If you have local surveillance sequences to combine with remote data:

**Rule**: `merge_local_sequences`

**Input**: 
- Remote metadata + sequences (from fetch step)
- Local sequences: ITpS Excel (`.xlsx`) or TSV format
- `config.local_sequences.samples_per_file` (optional, default 200)

The merge tool auto-detects xlsx vs TSV and extracts both sequence counts and metadata, preferring local ITpS records over remote duplicates.

**Output**: `results/ingest/{merged_metadata.tsv, sequences.fasta}`

## ViralQC (Quality Control)

**Config keys**: `viralqc.*` (expected_virus, expected_segment, datasets_dir, mode, executable, etc.)

Runs BLAST and Nextclade on all sequences. Outputs include:
- Genome quality grades (A, B, C, D)
- Nextclade clade assignment
- Genome coverage

### ViralQC Modes

| Mode | Behavior |
|------|----------|
| `run` | Execute ViralQC (most common); requires ViralQC environment and datasets |
| `precomputed` | Skip ViralQC; use pre-generated results from file (via `viralqc.precomputed`) |
| `skip` | Skip ViralQC entirely; no QC results joined |

```{warning}
`precomputed` and `skip` modes bypass QC checks. Ensure your upstream QC is reliable before using these.
```

### Alias Resolution

`expected_virus` and `expected_segment` are alias-aware. Examples:
- `expected_virus: "dengue"` matches ViralQC outputs labeled `Dengue virus` or any registered alias
- `expected_segment: "ha"` matches `HA`, `H1`, `H3` (flu segments)

Built-in aliases live in `flexpipe/data/viralqc/aliases.yaml`. Override with `viralqc.aliases_file`.

**Output**: `results/viralqc/outputs/results.tsv`

## Curation

**Rule**: `curate_qc`

Normalizes and enriches metadata:

1. **Field renaming** via `augur curate rename` (accessionVersion → strain, etc.)
2. **Date normalization** with `flexpipe-normalize-dates` (flexible date parser; logs ambiguous dates)
3. **ViralQC join** (genome_quality, coverage, clade columns)
4. **Lineage parsing** (e.g., DENV `3III_B.3.2` → prefix-safe derived columns)
5. **Geographic assignment** (country → continent, or division → Brazilian macro-region)
6. **Source annotation** (Pathoplexus, NCBI, ITpS)
7. **Deduplication** (prefer local ITpS over remote)

**Lineage parser** (`curation.lineage_parser`):
- `none` — raw lineage only
- `dengue` — DENV-specific parsing (e.g., `3III_B.3.2` → serotype, genotype, major, minor columns)
- `pango` — Pango lineage parsing (COV-Lineages)
- `generic_dot` — dot-delimited hierarchies (e.g., `A.B.C` → A, A.B, A.B.C columns)

**Geographic source** (`region_source`):
- `country` — country → continent mapping (global builds)
- `division` — Brazilian state → macro-region (Norte, Nordeste, etc.)

**Clade truncation** (`curation.clade_levels`):
- Hierarchical clades are truncated to N levels for `clade_truncated` column
- YFV uses `clade_levels: 1` (single genotype level)

**Output**: `results/ingest/dated_metadata.tsv`

## Quality Filtering

**Rule**: `augur filter`

Applies thresholds to exclude low-quality sequences:

| Parameter | Default | Effect |
|-----------|---------|--------|
| `qc.genome_quality` | `["A","B"]` | Include only genomes with grades A or B |
| `qc.min_coverage` | `0.70` | Minimum aligned fraction of reference |
| `qc.min_sequences` | `10` | Minimum subsampled output (error if below) |

**Output**: `results/ingest/filter_log.tsv` (exclusion reasons), filtered metadata and sequences

## Clade Filter

**Rule**: `clade_filter`

Restricts the analysis to a specific genetic group **before** subsampling. This step always runs; when `clade_filter.column` is empty (the default for builds that don't configure it), all sequences pass through unchanged.

**Config keys**: `clade_filter.*`

| Parameter | Default | Effect |
|-----------|---------|--------|
| `clade_filter.column` | `""` (disabled) | Metadata column to filter on (`clade`, `clade_truncated`, `genotype`, etc.) |
| `clade_filter.include` | `[]` | If non-empty, keep only sequences whose column value matches. Empty = keep all. |
| `clade_filter.exclude` | `[]` | Drop sequences whose column value matches. Applied after include. |
| `clade_filter.match` | `"exact"` | `"exact"` (equality) or `"prefix"` (dot-boundary; `B3` matches `B3` and `B3.1` but not `B30`) |

**Outputs**:
- `results/ingest/clade_filtered_metadata.tsv`
- `results/ingest/clade_filtered_sequences.fasta`
- `results/ingest/clade_filter_log.tsv` — per-strain drop log (`strain`, `group_value`, `drop_reason`)

**Examples**:

```yaml
# Measles genotype B3 only
clade_filter:
  column: clade_truncated
  include: [B3]
  match: exact

# Chikungunya ECSA-II and all sub-lineages (ECSA-II.1, ECSA-II.2, …)
clade_filter:
  column: clade
  include: [ECSA-II]
  match: prefix
```

```{note}
The filter column must be produced by the curation step. `clade` and `clade_truncated` require a ViralQC clade assignment; `genotype`/`major_lineage`/`minor_lineage` require `curation.lineage_parser != "none"`. If the column is absent at runtime, a warning is emitted and all sequences pass through.
```

## Subsampling

**Rule**: `augur subsample`

Selects a balanced subset of sequences for phylogenetic analysis. Configured via `subsample.yaml` with:

- `samples: { group_by: [division, year], sequences_per_group: N }`
- Per-group query filters (e.g., include specific strains, exclude others)
- `defaults.max_date` (updated by `--run-date` flag)

**Example config** (YFV Brazil):
```yaml
samples:
  group_by:
    - division
    - year
  sequences_per_group: 5

include:
  - strains: keep.txt

exclude:
  - strains: ignore.txt
```

**Output**: `results/subsampled/{metadata.tsv, sequences.fasta}` (e.g., ~100 representative strains from ~500 input)

## Colors & Coordinates

Run in parallel after subsampling:

### Colors (`flexpipe-colours`)

Assigns hex colors to metadata values hierarchically. Configured via `colours` in config:

```yaml
colours:
  - continent
  - country
  - division
```

Top-level categories (continent) get fixed hues from `flexpipe/data/colors/region_hues.tsv` or deterministic hashes. Sub-levels derive shades within the parent hue.

**Output**: `config/colour_scheme.tsv`

### Coordinates (`flexpipe-coordinates`)

Geocodes metadata locations (country, division, location) via Nominatim with:
- 1 req/sec rate-limiting (compliance)
- Persistent cache: seed from `flexpipe/data/geo/cache_coordinates.tsv`, then `builds/<name>/cache_coordinates.tsv`
- Fallback to cache if API fails
- Feature-type hints (e.g., division → state, location → city)

**Output**: `config/latlongs.tsv`

## File Outputs

Ingest completes with:
- `results/subsampled/{metadata.tsv, sequences.fasta}` — inputs to phylogenetics
- `results/ingest/{dated_metadata.tsv, filter_log.tsv, qc_summary.tsv}` — provenance
- `config/{colour_scheme.tsv, latlongs.tsv, name2hue.tsv}` — visualization config
- `cache/cache_coordinates.tsv` — coordinate cache (updated from Nominatim)
