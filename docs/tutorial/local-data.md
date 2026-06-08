# Local Data Mode

Analyze your own sequences without fetching from Pathoplexus or NCBI.

## Time Estimate

~10 minutes (setup + run on small dataset)

## Overview

flexpipe includes a ready-made `local-example` build for bring-your-own-data workflows:

```bash
builds/local-example/
  config.yaml          # Pre-configured for local data
  subsample.yaml
  reference.gb
  clades.tsv
  ... (other files)
```

This chapter walks you through using it.

## Step 1: Prepare Your Data

You need two files (in Pathoplexus TSV format):

### metadata.tsv

```
accessionVersion	geoLocCountry	geoLocAdmin1	collectionDate
SEQ_001	Brazil	SP	2025-01-15
SEQ_002	Brazil	RJ	2025-02-10
```

Minimal required columns:
- `accessionVersion` → strain ID
- `geoLocCountry` → country
- `geoLocAdmin1` → state/region
- `collectionDate` → date (YYYY-MM-DD)

### sequences.fasta

```fasta
>SEQ_001
AGATGATGAT...
>SEQ_002
AGACGACGAC...
```

### Store Them

For this tutorial, use the example files:

```bash
export LOCAL_META=builds/local-example/example_metadata.tsv
export LOCAL_SEQ=builds/local-example/example_sequences.fasta
```

(Create real files if you have your own data.)

## Step 2: Update Config

Edit `builds/local-example/config.yaml`:

**Current**:
```yaml
local:
  metadata: "/absolute/path/to/metadata.tsv"
  sequences: "/absolute/path/to/sequences.fasta"
```

**Edit to** (use absolute paths):

```bash
cd builds/local-example
sed -i '' "s|/absolute/path/to/metadata.tsv|$(pwd)/example_metadata.tsv|" config.yaml
sed -i '' "s|/absolute/path/to/sequences.fasta|$(pwd)/example_sequences.fasta|" config.yaml
cd -
```

Or manually edit:
```yaml
local:
  metadata: "/Users/you/flexpipe/builds/local-example/example_metadata.tsv"
  sequences: "/Users/you/flexpipe/builds/local-example/example_sequences.fasta"
```

## Step 3: Run

```bash
flexpipe-run \
  --config builds/local-example/config.yaml \
  --workdir /tmp/local-example \
  --run-date 2025-06-01 \
  --cores 4
```

### ViralQC Integration

By default, ViralQC runs on local sequences. Control this with:

```yaml
viralqc:
  mode: "run"  # or: precomputed, skip
```

- `run`: ViralQC performs QC (recommended)
- `skip`: No QC (fast; use if data is already clean)
- `precomputed`: Use pre-generated QC results file

## Step 4: Visualize

```bash
auspice view --datasetDir /tmp/local-example/auspice/
```

Open `http://localhost:4000`.

---

## Tips for Your Own Data

### Column Mapping

Your metadata must use Pathoplexus column names:

| Your Column | Must Rename To |
|---|---|
| Accession | `accessionVersion` |
| Country | `geoLocCountry` |
| State | `geoLocAdmin1` |
| Date | `collectionDate` |

### Authority: FASTA File

Only sequences present in the FASTA file are included. Metadata rows without corresponding FASTA entries are dropped.

### Test Validation

Before running, validate the config:

```bash
flexpipe-validate-build builds/local-example/config.yaml
```

---

## Next Step

Proceed to [Inspect Outputs](inspect-outputs.md) to understand the results.
