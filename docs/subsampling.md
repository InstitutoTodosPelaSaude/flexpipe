# Subsampling Reference

Subsampling selects a balanced subset of quality-filtered sequences for phylogenetic analysis. Configuration is separate from `config.yaml` and lives in a per-build `subsample.yaml` file.

## Configuration File

**Path**: `builds/<name>/subsample.yaml`

**Purpose**: Define how sequences are stratified and selected. For example, the YFV Brazil build selects 5 sequences per state per year to keep phylogenetic analysis manageable.

## Augur Subsample Schema

The `subsample.yaml` format is defined by [Augur](https://docs.nextstrain.org/projects/augur/en/stable/usage/subsample.html).

### Basic Structure

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

defaults:
  max_date: 2025-12-31
```

### Sections

#### samples

Stratified sampling rules:

```yaml
samples:
  group_by:
    - division
    - year
  sequences_per_group: 5
```

| Key | Type | Purpose |
|-----|------|---------|
| `group_by` | list | Metadata columns to group by (e.g., state + year) |
| `sequences_per_group` | int | Max sequences selected per group |

**Example**: `group_by: [division, year]` creates groups like:
- `(SP, 2023)` → up to 5 sequences
- `(RJ, 2023)` → up to 5 sequences
- `(SP, 2024)` → up to 5 sequences

#### include

Force-include specific strains:

```yaml
include:
  - strains: keep.txt
```

**keep.txt** is a newline-separated list of strain names (one per line). These are guaranteed to be in the subsampled output, even if they'd normally be excluded by QC.

#### exclude

Force-exclude specific strains:

```yaml
exclude:
  - strains: ignore.txt
```

**ignore.txt** is a newline-separated list of strain names. These are always removed from the subsampled output, useful for known contaminants or artifacts.

#### defaults

Default values applied to all groups:

```yaml
defaults:
  max_date: 2025-12-31
```

| Key | Type | Purpose |
|-----|------|---------|
| `max_date` | date | Upper date bound for subsampling (YYYY-MM-DD format) |

```{note}
The `--run-date` flag to `flexpipe-run` **overrides** `defaults.max_date`. If you pass `--run-date 2025-01-01`, only sequences collected before 2025-01-01 are eligible for subsampling.
```

## YFV Brazil Example

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

defaults:
  max_date: 2025-12-31
```

This configuration:
- Stratifies sequences by Brazilian state (division) and collection year
- Selects up to 5 sequences per state per year
- Always includes reference sequences (keep.txt)
- Always excludes known contaminants (ignore.txt)
- Applies an upper date cutoff (overridden by `--run-date`)

## Schema Gotchas

### Samples (not subsamples)

The key is **`samples`** (plural), NOT `subsamples`. Augur renamed this in version 8+.

```yaml
# ✓ Correct
samples:
  group_by: [division, year]

# ✗ Wrong (older augur)
subsamples:
  group_by: [division, year]
```

### Group_by Format

The `group_by` field is a **list**:

```yaml
# ✓ Correct
samples:
  group_by:
    - division
    - year

# ✗ Wrong (deprecated string)
samples:
  group_by: "division year"
```

### Mutually Exclusive Parameters

Augur rejects configs with **both** `sequences_per_group` **and** `max_sequences`:

```yaml
# ✓ Correct (use one or the other)
samples:
  sequences_per_group: 5

# ✗ Wrong (augur error)
samples:
  sequences_per_group: 5
  max_sequences: 100
```

## Advanced Queries

Per-group custom filtering:

```yaml
samples:
  default:
    group_by: [division, year]
    sequences_per_group: 5

  early_2020:
    group_by: [division]
    query: --min-date 2020-01-01 --max-date 2020-12-31
    sequences_per_group: 2
```

This creates two sampling strategies: a default one and a special strategy for early 2020 with different date range and group size.

## Run-Date Semantics

When you run:

```bash
flexpipe-run --config ... --workdir ... --run-date 2025-06-01
```

The `--run-date` flag:
- Overrides `defaults.max_date` in subsample.yaml
- Passed to `augur subsample` as the upper date bound
- Affects ingest stage only (phylo receives it for forward-compatibility but ignores it)

**Effect**: only sequences collected before 2025-06-01 are eligible for subsampling.

Omitting `--run-date` defaults to today with a warning. For reproducible analyses, always pass an explicit `--run-date`.

## Output

`augur subsample` produces:

- `results/subsampled/metadata.tsv` — filtered + subsampled metadata
- `results/subsampled/sequences.fasta` — corresponding sequences

These are inputs to the phylogenetic stage.
