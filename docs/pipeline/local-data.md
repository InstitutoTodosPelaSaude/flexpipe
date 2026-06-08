# Local Data Mode

**Local data mode** allows you to analyze sequences without fetching from Pathoplexus or NCBI. You provide metadata and sequences directly, and flexpipe skips the remote fetch step.

## When to Use Local Mode

- Analyzing surveillance sequences not yet in public databases
- Testing the pipeline on small datasets
- Analyzing sequences from a private or restricted database
- Rapid turnaround without network delays

## Configuration

Set `data_source: local` in your build config:

```yaml
data_source: local

local:
  metadata: path/to/metadata.tsv
  sequences: path/to/sequences.fasta
```

Both `metadata` and `sequences` are **required** when using `data_source: local`. Paths are relative to the repository root.

## Metadata Format

Your TSV file must use **Pathoplexus (ITpS) column names**. These are mapped to flexpipe-internal names by `augur curate rename`:

| Required Column | Maps to | Purpose |
|-----------------|---------|---------|
| `accessionVersion` | `strain` | Unique sequence identifier |
| `geoLocCountry` | `country` | Country of origin |
| `geoLocAdmin1` | `division` | State/province (if applicable) |
| `geoLocAdmin2` | `location` | City/region (optional) |
| `collectionDate` | `date` | Collection date (YYYY-MM-DD or flexible) |

**Optional columns**:
- `dataUseTerms` — data use policy (affects filtering/coloring)
- `lineage` — clade/lineage annotation
- Any other columns are preserved and available for coloring/filtering

**Example**:
```tsv
accessionVersion	geoLocCountry	geoLocAdmin1	collectionDate	dataUseTerms	lineage
SEQ_001	Brazil	SP	2025-06-01	OPEN	DENV-3_III_B
SEQ_002	Brazil	RJ	2025-06-10	OPEN	DENV-3_III_B
```

## Sequences File

A standard FASTA file with headers matching the `accessionVersion` column:

```fasta
>SEQ_001
AGATGATGAT...
>SEQ_002
AGACGACGAC...
```

**Authority**: FASTA file. Only sequences present in the FASTA are included; metadata rows without corresponding sequences are dropped.

## Ingest Behavior

With `data_source: local`:

1. `fetch_local` rule copies metadata/sequences file paths (no download)
2. `merge_local_sequences` rule is skipped (no merging with remote data)
3. ViralQC runs normally (unless disabled via `viralqc.mode: skip`)
4. Curation, filtering, and subsampling proceed as usual

**Outputs**: same as remote-fetched data (subsampled metadata + sequences ready for phylogenetics)

## ViralQC Integration

By default, ViralQC runs on local sequences. You can control this:

### Option 1: Run ViralQC (Recommended)

```yaml
viralqc:
  mode: run
  expected_virus: "dengue"  # or your pathogen
  expected_segment: "genome"
```

ViralQC performs genome quality checks and clade assignment.

### Option 2: Provide Precomputed ViralQC Results

If you've already run ViralQC elsewhere:

```yaml
viralqc:
  mode: precomputed
  precomputed: /path/to/viralqc_results.tsv
```

The file should have columns matching ViralQC output: `strain`, `genome_quality`, `coverage`, `clade`, etc.

### Option 3: Skip ViralQC Entirely

For data you've already QC'd:

```yaml
viralqc:
  mode: skip
```

```{warning}
`skip` mode assumes your data is already high-quality. No QC checks are applied. The pipeline will fail if sequences are too short or too divergent for alignment.
```

## Example: Bring-Your-Own Data

Setup:

1. Create metadata.tsv with your surveillance data
2. Create sequences.fasta with corresponding sequences
3. Copy a build template: `cp -r builds/yfv-brazil builds/my-local-analysis`
4. Edit config.yaml:

```yaml
data_source: local

local:
  metadata: /absolute/path/to/metadata.tsv
  sequences: /absolute/path/to/sequences.fasta

viralqc:
  mode: skip  # or: run

parameters:
  mask_5prime: 0
  mask_3prime: 0
  # other params...
```

5. Run:

```bash
flexpipe-run \
  --config builds/my-local-analysis/config.yaml \
  --workdir /tmp/local-run \
  --run-date 2026-01-01
```

## Integration Test

Local-data builds are tested via the integration test suite. See [developer-guide.md](../developer-guide.md) for registration steps.
