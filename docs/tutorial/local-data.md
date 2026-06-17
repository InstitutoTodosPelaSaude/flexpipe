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
accessionVersion	geoLocCountry	geoLocAdmin1	sampleCollectionDate
SEQ_001	Brazil	SP	2025-01-15
SEQ_002	Brazil	RJ	2025-02-10
```

Minimal required columns:
- `accessionVersion` → strain ID
- `geoLocCountry` → country
- `geoLocAdmin1` → state/region
- `sampleCollectionDate` → date (YYYY-MM-DD)

### sequences.fasta

```fasta
>SEQ_001
AGATGATGAT...
>SEQ_002
AGACGACGAC...
```

### Store Them

For this tutorial, the checked-in example build already points at these files:

```bash
builds/local-example/local_data/metadata.tsv
builds/local-example/local_data/sequences.fasta
```

Replace those files, or update the config paths below, when you have your own data.

## Step 2: Check Config

`builds/local-example/config.yaml` is ready to run with the bundled tutorial files:

```yaml
data_source: "local"

local:
  metadata:  "builds/local-example/local_data/metadata.tsv"
  sequences: "builds/local-example/local_data/sequences.fasta"
```

For your own data, edit the `local` paths. Relative paths are resolved from the build config directory, and existing repo-root-relative paths are still accepted:

```yaml
local:
  metadata: "local_data/my_metadata.tsv"
  sequences: "local_data/my_sequences.fasta"
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
| Date | `sampleCollectionDate` |

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
