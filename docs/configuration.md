# Configuration Reference

All pipeline parameters are defined in a per-build `config.yaml` file (e.g., `builds/yfv-brazil/config.yaml`). This page documents every configuration section and key.

## Data Source Selection

Choose one data source for the analysis:

```yaml
data_source: pathoplexus  # pathoplexus | ncbi | local
```

Then configure the corresponding section below.

## Core Sections

### data_source

```yaml
data_source: pathoplexus  # or: ncbi, local
region_source: country    # country (global) or division (Brazil-only)
```

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `data_source` | Literal | (required) | `pathoplexus`, `ncbi`, or `local` |
| `region_source` | Literal | (required) | `country` (global) or `division` (Brazil state) |

### mode

Controls whether the analysis targets the whole genome or a specific gene/fragment:

```yaml
mode: "whole-genome"  # or: "fragment"
```

| Value | Behavior |
|-------|----------|
| `"whole-genome"` (default) | Standard pipeline; QC gates on `genome_quality` and `coverage` |
| `"fragment"` | Uses ViralQC's extracted target-region FASTA; QC gates on `target_gene_coverage` and `target_gene_quality` |

Fragment mode requires `viralqc.mode: run` and a Nextclade dataset that declares a
`target_gene` for the virus.  See [Fragment Analysis](pipeline/fragment-analysis.md)
for the full guide.

### fragment

Settings for gene/fragment analysis mode (`mode: "fragment"` only):

```yaml
fragment:
  target_gene: "N"           # /gene qualifier in the ViralQC dataset (required)
  min_target_coverage: 0.70  # minimum targetGeneCoverage (0.0–1.0)
  target_quality: ["A", "B"] # passing targetGeneQuality grades
```

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `target_gene` | string | `""` | Name of the target gene (e.g. `"N"`, `"HA"`, `"E"`); **required** when `mode: fragment` |
| `min_target_coverage` | float 0–1 | `0.70` | Minimum fraction of target gene covered; sequences below this are excluded |
| `target_quality` | list | `["A","B"]` | Accepted targetGeneQuality grades; grades not in this list are excluded |

The `fragment:` section is inert when `mode: "whole-genome"` (the default).  Existing
whole-genome builds that do not set `mode` are completely unaffected.

**Validation rules:**
- `target_gene` is required when `mode: "fragment"` (validator error if empty).
- `viralqc.mode: skip` and `viralqc.mode: precomputed` are rejected in fragment mode (v1).
- `flexpipe-validate-build` additionally checks that a ViralQC/Nextclade dataset
  matching `viralqc.expected_virus` + `fragment.target_gene` exists in the registry.

### files

```yaml
files:
  reference: "reference.gb"
  reference_name: "X03700.1"
  clades: "clades.tsv"
```

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `reference` | string | "reference.gb" | GenBank reference (build-relative) |
| `reference_name` | string | (auto-detected) | Name of reference sequence in GenBank |
| `clades` | string | "clades.tsv" | Clade definitions (build-relative) |

### parameters

Phylogenetic and masking parameters:

```yaml
parameters:
  mask_5prime: 142
  mask_3prime: 548
  mask_sites: ""
  mask_sites_file: ""
  ufboot: 1000
  model: "MFP"
  root: "least-squares"
  coalescent: "skyline"
  date_inference: "marginal"
  divergence_units: "mutations-per-site"
  clock_filter_iqd: 3
  date_confidence: true
  traits_confidence: true
  ancestral_inference: "joint"
```

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `mask_5prime` | int | 0 | Terminal 5′ masking (bp) |
| `mask_3prime` | int | 0 | Terminal 3′ masking (bp) |
| `mask_sites` | string | "" | Comma-separated sites to mask |
| `mask_sites_file` | string | "" | BED file of regions to mask |
| `ufboot` | int | 0 | UFBoot replicates (0 = disabled) |
| `model` | string | (required) | Substitution model (MFP, JC, GTR+G, etc.) |
| `root` | Literal | "least-squares" | `least-squares`, `min_dev`, `oldest`, `best` |
| `coalescent` | Literal | "skyline" | `skyline`, `opt`, `const`, `fixed` |
| `date_inference` | Literal | "marginal" | `marginal`, `joint` |
| `divergence_units` | Literal | "mutations" | `mutations`, `mutations-per-site` |
| `clock_filter_iqd` | float | 3.0 | Outlier threshold (interquartile distances) |
| `date_confidence` | bool | false | Compute date confidence intervals |
| `traits_confidence` | bool | false | Compute trait confidence intervals |
| `ancestral_inference` | Literal | "joint" | `joint`, `marginal` |

### options

Additional pipeline flags:

```yaml
options:
  threads: 4
```

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `threads` | int | 4 | Threads requested by Snakemake rules; capped by `--cores` |

### Curation

Metadata normalization and lineage handling:

```yaml
curation:
  clade_levels: 1
  clade_separator: "."
  lineage_parser: "dengue"
  lineage_columns:
    - serotype
    - genotype
    - major_lineage
    - minor_lineage
```

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `clade_levels` | int | (required) | Number of hierarchy levels for `clade_truncated` |
| `clade_separator` | string | "." | Delimiter in hierarchical clades |
| `lineage_parser` | Literal | "none" | `none`, `dengue`, `pango`, `generic_dot` |
| `lineage_columns` | list | [] | Output columns from lineage parsing |

### regions

Geographic assignments:

```yaml
regions:
  country_map: "flexpipe/data/regions/country_to_continent.tsv"
  division_map: "flexpipe/data/regions/brazil_state_to_region.tsv"
  division_abbreviations: "flexpipe/data/regions/brazil_abbreviations.tsv"
  division_parser: "brazil"
```

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `country_map` | string | (bundled) | Country → continent mapping (TSV) |
| `division_map` | string | (bundled) | Division → region mapping (TSV) |
| `division_abbreviations` | string | (bundled) | Division abbreviation mapping (TSV) |
| `division_parser` | Literal | "brazil" | Custom division parser (e.g., `brazil` for states) |

### colours

Metadata fields for coloring hierarchy (general to specific):

```yaml
colours:
  host: "host"
  clade: "clade_truncated clade"
  geo: "continent country division location"
  source: "source"
  data_use: "data_use"
  clade_root_level: ""
```

Determines the color hierarchy in Auspice. Each value is a space-separated list of metadata columns from general to specific. Top-level categories get fixed hues from bundled or build-specific hue tables; sub-levels derive shades.

### traits

Ancestral state inference:

```yaml
traits:
  columns: "region country division clade_truncated"
  max_states: 200
  rare_state_label: "other"
```

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `columns` | string | `"division location clade"` | Space-separated metadata fields for ancestral inference |
| `max_states` | int | 200 | Max unique states per column (rarer ones collapsed) |
| `rare_state_label` | string | "other" | Label for collapsed rare states |

### coordinates

Geocoding configuration:

```yaml
coordinates:
  columns: "country division location"
  force_file: ""
  shared_cache: ""
```

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `columns` | string | `"country"` | Space-separated metadata columns to geocode |
| `force_file` | string | "" | Optional manual coordinate overrides (`place TAB lat TAB lon`) |
| `shared_cache` | string | "" | Optional shared cache file (alternative to build cache) |

### qc

Quality control thresholds:

```yaml
qc:
  genome_quality:
    - A
    - B
  min_coverage: 0.70
  required_columns:
    - strain
    - date
    - clade
  min_sequences: 10
```

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `genome_quality` | list | `["A","B"]` | Accepted ViralQC grades |
| `min_coverage` | float | 0.70 | Minimum aligned fraction (0.0–1.0) |
| `required_columns` | list | `["strain","date","clade"]` | Mandatory metadata columns post-curation |
| `min_sequences` | int | 10 | Minimum output after subsampling (error if below) |

### clade_filter

Restricts the analysis to a specific genetic group **upstream of subsampling**. Disabled by default (empty `column`); existing builds that omit this section are completely unaffected.

```yaml
clade_filter:
  column:  "clade_truncated"   # metadata column to filter on
  include: ["B3"]              # keep only matching rows; empty = keep all
  exclude: []                  # drop matching rows (applied after include)
  match:   "exact"             # "exact" or "prefix"
```

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `column` | string | `""` (disabled) | Metadata column to filter on |
| `include` | list | `[]` | Keep only rows whose column value matches |
| `exclude` | list | `[]` | Drop rows whose column value matches (after include) |
| `match` | Literal | `"exact"` | `"exact"` (equality) or `"prefix"` (dot-boundary) |

**`match` semantics**:
- `"exact"`: equality. `include: ["B3"]` keeps rows where `clade_truncated == "B3"`. A row with value `B3.1` is **not** matched.
- `"prefix"`: dot-boundary prefix. `include: ["B3"]` matches `B3` and `B3.1` (and `B3.2`, etc.) but **not** `B30` (no dot separator). Similarly `include: ["ECSA-II"]` matches `ECSA-II.1` but not `ECSA-IIb`.

**Column availability**:
The column must exist in the curated metadata output. Column availability depends on the build:

| Column | Requires |
|--------|----------|
| `clade`, `clade_truncated` | ViralQC to assign a clade (Nextclade dataset has this pathogen) |
| `genotype`, `major_lineage`, `minor_lineage`, `serotype` | `curation.lineage_parser != "none"` |
| Any other column | Must be in the input metadata or generated during curation |

There is **no** column literally named `lineage` — use `clade` (raw from ViralQC), `clade_truncated` (top-N levels), or one of the lineage_parser-derived columns.

If the column is absent at runtime, a warning is emitted and all sequences pass through (no filtering). Inspect `results/ingest/clade_filter_log.tsv` to verify the filter was applied.

**Examples**:

```yaml
# Measles genotype B3 only (global build)
clade_filter:
  column:  clade_truncated
  include: [B3]
  match:   exact

# Chikungunya ECSA-II and sub-lineages
clade_filter:
  column:  clade
  include: [ECSA-II]
  match:   prefix

# Exclude two dengue serotypes from a multi-serotype build
clade_filter:
  column:  serotype
  exclude: ["3", "4"]
  match:   exact
```

### coordinates

Same as [coordinates](#coordinates) above.

### subsampling

*(Configured via `subsample.yaml`, not config.yaml)*

See [Subsampling Reference](subsampling.md).

## Data Source Sections

### pathoplexus

Pathoplexus/LAPIS API configuration:

```yaml
pathoplexus:
  organism: "Dengue virus 3"
  base_url: "https://lapis.cov-spectrum.org"
  metadata_endpoint: "/metadata"
  sequences_endpoint: "/sequences"
  min_completeness: 0.9
  query_params:
    dataUseTerms: OPEN
  strip_fasta_id_suffix: true
```

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `organism` | string | (required) | LAPIS organism name |
| `base_url` | string | (required) | LAPIS API base URL |
| `metadata_endpoint` | string | "/metadata" | Metadata endpoint |
| `sequences_endpoint` | string | "/sequences" | Sequences endpoint |
| `min_completeness` | float | (optional) | Filter by genome completeness (0.0–1.0) |
| `query_params` | dict | {} | Additional LAPIS query parameters (e.g., `dataUseTerms: OPEN`) |
| `strip_fasta_id_suffix` | bool | false | Remove FASTA ID suffix (e.g., `\|EPI_ISL_123456`) |

### ncbi

NCBI Entrez API configuration:

```yaml
ncbi:
  taxid: 11082
  genome_size: 11000
  min_length: 8000
  max_length: 12000
  email: ""  # required before running, or set NCBI_EMAIL
  api_key: ""  # optional, or set NCBI_API_KEY
  min_date: 2020-01-01
  extra_search_term: ""
```

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `taxid` | int | (required) | NCBI taxonomy ID |
| `genome_size` | int | (required) | Approximate genome size (bp) |
| `min_length` | int | 0 | Minimum sequence length filter |
| `max_length` | int | (required) | Maximum sequence length filter |
| `email` | string | (env: `NCBI_EMAIL`) | Email for NCBI (required) |
| `api_key` | string | (env: `NCBI_API_KEY`) | API key (optional; improves rate limits) |
| `min_date` | date | (optional) | Exclude older sequences |
| `extra_search_term` | string | "" | Additional Entrez search filter |

### local

Local data file paths:

```yaml
local:
  metadata: "/path/to/metadata.tsv"
  sequences: "/path/to/sequences.fasta"
```

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `metadata` | string | (required) | Path to metadata TSV (Pathoplexus format) |
| `sequences` | string | (required) | Path to sequences FASTA |

### local_sequences

Merge local surveillance data with remote:

```yaml
local_sequences:
  enabled: false
  metadata: "data/metadata.xlsx"
  sequences: "data/new_sequences.fasta"
```

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `enabled` | bool | false | Merge local surveillance records into remote Pathoplexus/NCBI data |
| `metadata` | string | `"data/metadata.xlsx"` | Local ITpS xlsx/TSV/PPX metadata file |
| `sequences` | string | `"data/new_sequences.fasta"` | Local FASTA file; FASTA IDs are authoritative |

## ViralQC Integration

```yaml
viralqc:
  expected_virus: "dengue"
  expected_segment: "genome"
  conda_env: "viralQC"
  clade_column: "clade"
  aliases_file: ""
  datasets_dir: ""
  blast_database: ""
  blast_database_metadata: ""
  executable: "vqc"
  runner: "conda"
  mode: "run"
  precomputed: ""
```

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `expected_virus` | string | "" | Virus name for cross-contamination filtering (alias-aware; see [ViralQC Integration](viralqc-integration.md)) |
| `expected_segment` | string | "" | Segment (e.g., `genome`, `ha`, `l`) |
| `conda_env` | string | "viralQC" | Conda environment name |
| `clade_column` | string | "clade" | ViralQC output column for clade |
| `aliases_file` | string | "" | Override aliases (YAML) |
| `datasets_dir` | string | (auto-discovered) | ViralQC datasets directory |
| `runner` | Literal | "conda" | `conda`, `mamba`, `micromamba`, `direct` |
| `executable` | string | "vqc" | ViralQC executable name |
| `mode` | Literal | "run" | `run`, `precomputed`, `skip` |
| `precomputed` | string | "" | Path to precomputed results (required if `mode=precomputed`) |

**`skip` mode and length-based coverage**: When `viralqc.mode: skip`, coverage is computed as
`min(seq_len / genome_size, 1.0)` when `genome_size > 0` (from `ncbi.genome_size` or
`pathoplexus.genome_size`). This makes `qc.min_coverage` a real length gate. Without
`genome_size`, all sequences get `coverage = 1.0` (no length filtering).
See [Builds Without a Dataset](viralqc-integration.md#builds-without-a-viralqcnextclade-dataset).

## Path Resolution

Configuration keys with file paths are resolved relative to:

- **Build-relative** (e.g., `reference: "reference.gb"`): relative to `builds/<name>/`
- **Repo-root relative** (e.g., `pathoplexus.base_url`): URLs and absolute paths stay absolute
- **Workdir paths**: created at runtime in `<workdir>/config/`, `<workdir>/results/`, etc.

## Validation & Defaults

flexpipe validates the configuration at startup:

- Required keys are enforced (`data_source`, `taxid` for NCBI, etc.)
- Unknown keys are rejected
- Type mismatches are reported (int vs string, list vs dict, etc.)
- Enum values (`data_source`, `region_source`, `lineage_parser`, etc.) are validated

## Example Builds

See [example-builds.md](builds/example-builds.md) for complete config.yaml examples for each pathogen.
