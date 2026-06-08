# Add a Pathogen

Set up a new viral pathogen in flexpipe. This chapter shows both NCBI and Pathoplexus workflows.

## Time Estimate

~20 minutes (setup + dry-run validation)

## Choose Your Path

### Track A: NCBI (Zika Virus)

Use NCBI Entrez to fetch sequences by taxonomy ID.

### Track B: Pathoplexus (Dengue Virus 3)

Use Pathoplexus/LAPIS to fetch sequences by organism name.

Both paths follow the same core steps (copy template → edit config → validate → test).

---

## Track A: NCBI (Zika Virus)

### Step 1: Copy Template

```bash
cp -r builds/zikv-brazil builds/my-zikv
cd builds/my-zikv
```

`zikv-brazil` is the NCBI template (uses taxid-based fetching).

### Step 2: Edit config.yaml

Key edits:

**Data source** (already correct):
```yaml
data_source: ncbi
```

**Reference** (already set for ZIKV; optionally update):
```yaml
files:
  reference: "reference.gb"
  reference_name: "NC_012532.1"
```

The config is already tuned for ZIKV; no changes needed for this tutorial.

### Step 3: Validate

```bash
flexpipe-validate-build config.yaml
```

Should report: `Config validation passed.`

### Step 4: Dry-Run Test

```bash
flexpipe-run \
  --config config.yaml \
  --workdir /tmp/my-zikv-test \
  --stage ingest \
  --run-date 2025-06-01 \
  --cores 4 \
  --dry-run
```

Wait for "dry-run mode; no steps executed" message. This checks that the config wires correctly without fetching data.

---

## Track B: Pathoplexus (Dengue Virus 3)

### Step 1: Copy Template

```bash
cp -r builds/denv3-brazil builds/my-denv3
cd builds/my-denv3
```

`denv3-brazil` is the Pathoplexus template.

### Step 2: Edit config.yaml

Key edits:

**Data source** (already correct):
```yaml
data_source: pathoplexus
```

**Organism** (already set; for reference):
```yaml
pathoplexus:
  organism: "Dengue virus 3"
```

**ViralQC** (already set for DENV):
```yaml
viralqc:
  expected_virus: "dengue"
  expected_segment: "genome"
  mode: "run"
```

The config is already tuned for DENV3; no changes needed for this tutorial.

### Step 3: Validate

```bash
flexpipe-validate-build config.yaml
```

Should report: `Config validation passed.`

### Step 4: Dry-Run Test

```bash
flexpipe-run \
  --config config.yaml \
  --workdir /tmp/my-denv3-test \
  --stage ingest \
  --run-date 2025-06-01 \
  --cores 4 \
  --dry-run
```

Again: "dry-run mode; no steps executed."

---

## Optional: Full Run (Track A or B)

If you want to actually run one (not just validate), pick one track and run:

```bash
flexpipe-run \
  --config builds/my-zikv/config.yaml \
  --workdir /tmp/my-zikv \
  --run-date 2025-06-01 \
  --cores 4
```

This will take ~15 minutes. Results are in `/tmp/my-zikv/auspice/results.json`.

---

## Summary

You've now:
1. ✓ Copied a template build
2. ✓ Understood the data source config (NCBI vs Pathoplexus)
3. ✓ Validated the build
4. ✓ Dry-run tested the pipeline

For a real new pathogen, also:
- Get the reference genome (`.gb` file)
- Set terminal mask values (or generate with `flexpipe-reference-mask`)
- Define clades (or leave `clades.tsv` header-only)
- Adjust subsampling and QC thresholds

See [Adding a Pathogen](../builds/adding-a-pathogen.md) for the full guide.

## Next Step

Proceed to [Local Data](local-data.md) to analyze your own sequences.
