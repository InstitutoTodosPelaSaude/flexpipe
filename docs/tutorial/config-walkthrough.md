# Config Walkthrough

Learn how to modify configuration and re-run the pipeline. This chapter makes three safe edits.

## Your Variables

Copy the variables from [First Run](first-run.md):

```bash
export WORKDIR=/tmp/yfv-tutorial
export RUN_DATE=2025-06-01
```

## Edit 1: Change Subsampling Count

**What**: Increase samples per group to get more sequences in the tree.

**File**: `builds/yfv-brazil/subsample.yaml`

**Current**:
```yaml
samples:
  group_by:
    - division
    - year
  sequences_per_group: 5
```

**Edit to**:
```yaml
samples:
  group_by:
    - division
    - year
  sequences_per_group: 10
```

**Re-run ingest only** (faster than full pipeline):

```bash
flexpipe-run \
  --config builds/yfv-brazil/config.yaml \
  --workdir $WORKDIR \
  --stage ingest \
  --run-date $RUN_DATE
```

**Check**: More sequences in output?

```bash
wc -l $WORKDIR/results/subsampled/metadata.tsv
```

Should be ~201 now (200 sequences + header).

**Revert** for next edit:

```bash
git checkout builds/yfv-brazil/subsample.yaml
```

## Edit 2: Change QC Thresholds

**What**: Include lower-quality sequences (genome_quality C).

**File**: `builds/yfv-brazil/config.yaml`

**Find the `qc` section** (around line 40):

**Current**:
```yaml
qc:
  genome_quality:
    - A
    - B
  min_coverage: 0.70
```

**Edit to**:
```yaml
qc:
  genome_quality:
    - A
    - B
    - C
  min_coverage: 0.70
```

**Re-run ingest**:

```bash
flexpipe-run \
  --config builds/yfv-brazil/config.yaml \
  --workdir $WORKDIR \
  --stage ingest \
  --run-date $RUN_DATE
```

**Check**: More sequences post-QC?

```bash
cat $WORKDIR/results/ingest/qc_summary.tsv
```

Look at `genome_quality_c_count` (should be > 0 now) and `sequences_after_qc` (should increase).

**Revert**:

```bash
git checkout builds/yfv-brazil/config.yaml
```

## Edit 3: Enable UFBoot (Slow!)

**What**: Increase phylogenetic accuracy with bootstraps. **Warning: ~5x slower.**

**File**: `builds/yfv-brazil/config.yaml`

**Find the `parameters` section**:

**Current**:
```yaml
parameters:
  ufboot: 0
  model: "JC"
  ...
```

**Edit to**:
```yaml
parameters:
  ufboot: 100
  model: "JC"
  ...
```

**Run full pipeline** (will take ~30 minutes on 4 cores):

```bash
flexpipe-run \
  --config builds/yfv-brazil/config.yaml \
  --workdir $WORKDIR \
  --run-date $RUN_DATE \
  --cores 4
```

Or skip and just revert:

```bash
git checkout builds/yfv-brazil/config.yaml
```

**Check**: Bootstrap values appear in the tree (IQ-TREE log shows UFBoot replicates).

## Important Note

When you edit `config.yaml` or `subsample.yaml` and re-run with `--stage ingest`, only the ingest stage re-runs. Phylogenetics uses the already-subsampled sequences. To see phylo changes (e.g., ufboot), you must run the full pipeline or `--stage phylo` (which uses existing subsampled data).

## What We Learned

- `subsample.yaml` controls how many sequences make it to phylogenetics
- `config.yaml` `qc` section filters by genome quality
- `config.yaml` `parameters` section controls phylogenetic inference speed/accuracy
- Changes propagate automatically; re-run only affected stages

## Next Step

Move on to [Add Pathogen](add-pathogen.md) to set up a new virus.
