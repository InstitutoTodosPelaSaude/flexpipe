# Gene / Fragment Analysis Mode

flexpipe supports phylogenetic analysis against a **gene or genomic fragment** rather
than a whole genome.  The canonical example is **measles genotype B3**, where the
standard genotyping marker is the **N450** nucleoprotein window
(NC_001498.1:1233–1682, 450 nt).  Fragment mode is opt-in and virus-agnostic:
the same path serves any pathogen with a Nextclade dataset that declares a
`target_gene` or `target_regions`.

## When to Use Fragment Mode

| Scenario | Recommendation |
|----------|----------------|
| Most sequences are **partial** (gene-length), full genomes rare | Fragment mode: threshold on gene coverage, use extracted FASTA |
| Standard epidemiological marker is a **sub-genomic window** (N450, E gene, HA1, VP1) | Fragment mode: gene-relative coordinates, gene-only reference |
| Sequences are full-genome and the full-genome phylogeny is appropriate | Whole-genome mode (default) |
| Virus has **no Nextclade dataset** | Use `viralqc.mode: skip` — fragment mode requires a dataset |

## How It Works

### ViralQC Target-Region Extraction

ViralQC runs Nextclade internally.  When a Nextclade dataset declares a
`target_gene` (e.g. `N` in `measles-N450-WHO-2012`), ViralQC reports:

| ViralQC column | Meaning |
|----------------|---------|
| `targetGeneCoverage` | Fraction of the target gene covered (0–1) |
| `targetGeneQuality` | Quality grade for the target region (A, B, C, D) |
| `targetGene` | Name of the target gene |

It also writes `sequences_target_regions.fasta` — an extracted FASTA containing
the target-region sequence for each input record.

### Fragment Mode Data Flow

```
ViralQC (run)
    ↓  results.tsv (targetGeneCoverage, targetGeneQuality, targetGene)
    ↓  sequences_target_regions.fasta
flexpipe-curate
    ↓  adds target_gene_coverage / target_gene_quality / target_gene columns
augur filter (fragment gate)
    ↓  keeps: target_gene_coverage ≥ min_target_coverage
    ↓  keeps: target_gene_quality in [A, B]
augur subsample
    ↓
[phylogenetic/Snakefile] — unchanged; gene-only reference handles coordinates
augur align (against 450-nt reference)
    ↓  insertions stripped → all sequences collapse to 450-nt window
augur tree / refine / clades / export
    ↓
auspice/results.json
```

### Why `augur align` Handles Mixed Lengths

`augur align --reference-sequence <gene-only.gb>` produces a **reference-coordinate**
alignment: insertions relative to the reference are stripped, deletions are preserved
as gaps.  Whether a sequence is a 450-nt fragment or a 15,910-nt full measles genome,
the output is always 450 columns.  This is the same mechanism used by the bundled
flu-HA builds, which align full HA gene records against a 1,701-nt reference.

## Configuration

Enable fragment mode by adding two top-level keys to `config.yaml`:

```yaml
mode: "fragment"

fragment:
  target_gene: "N"           # /gene qualifier in the ViralQC dataset
  min_target_coverage: 0.25  # minimum targetGeneCoverage — see note below
  target_quality: ["A", "B"] # passing targetGeneQuality grades
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `mode` | `"whole-genome"` \| `"fragment"` | `"whole-genome"` | Analysis mode |
| `fragment.target_gene` | string | `""` (required in fragment mode) | Target gene name (matches ViralQC dataset) |
| `fragment.min_target_coverage` | float 0–1 | `0.70` | Minimum fraction of **target gene** covered |
| `fragment.target_quality` | list | `["A","B"]` | Passing targetGeneQuality grades |

> **Important:** `min_target_coverage` is measured against the **full length of the target
> gene**, not the fragment window.  A 450-nt N450 fragment covers ~28.5 % of the 1,578-nt
> measles N gene, so setting `min_target_coverage: 0.70` would drop every valid N450 sequence.
> For sub-gene fragments like N450, set this value below the fraction of the gene your window
> covers (e.g. `0.25`).  The default of `0.70` is appropriate only when your sequences cover
> ≥ 70 % of the full target gene (e.g. a near-complete E gene fragment).

### Required Companion Settings

Fragment mode requires `viralqc.mode: run` (ViralQC must execute to produce
`sequences_target_regions.fasta`):

```yaml
viralqc:
  mode: "run"          # fragment mode forbids "skip" and "precomputed"
  expected_virus: "measles"  # alias key for contamination filtering
```

The `reference.gb` must be the **gene-only** slice (e.g. 450 nt for N450), not the
whole genome.  Terminal masking is typically `mask_5prime: 0` / `mask_3prime: 0`
because there are no UTR flanks in a tight coding window:

```yaml
parameters:
  mask_5prime: 0
  mask_3prime: 0
  mask_sites_file: "builds/measles-b3-n450-global/masks/reference_terminal.bed"
```

## Dataset Guardrail

Fragment mode is only meaningful when ViralQC can sort the virus to a Nextclade dataset
that extracts the target gene.  **`flexpipe-validate-build` errors** if no dataset
matching `viralqc.expected_virus` + `fragment.target_gene` is found in the ViralQC
registry (`viralQC/viralqc/config/datasets.yml`).

The error message lists all available virus/target-gene pairs.  If your virus has no
Nextclade dataset, use `viralqc.mode: skip` (whole-genome mode only).

## Producing a Gene-Only Reference

Use `flexpipe-reference-slice` to extract the gene window from a whole-genome
`reference.gb`:

```bash
flexpipe-reference-slice \
    --reference  builds/measles-b3-global/reference.gb \
    --region     1233..1682 \
    --gene       N  --feature-type CDS \
    --new-id     NC_001498.1 \
    --output-reference  builds/measles-b3-n450-global/reference.gb \
    --output-bed        builds/measles-b3-n450-global/masks/reference_terminal.bed
```

- `--region START..END`: 1-based inclusive coordinates in the source reference
- `--gene`: `/gene` qualifier to locate the slice automatically (overridden by `--region`)
- `--output-bed`: writes a gene-relative terminal mask BED (empty for tight CDS windows)

The output record is in **gene-relative coordinates** (position 1 in the output
= `START` in the source).  All GenBank features whose intervals overlap the window
are rewritten by Biopython's slicing.  A CDS spanning the full slice is synthesized
if no CDS survives the slice (required by `augur translate`).

Commit the generated `reference.gb` to `builds/<name>/` — it is a small, reviewable
static artifact.  Regeneration from source is always reproducible via the CLI.

## Clades and Coordinate System

`clades.tsv` site coordinates must be in **gene-relative** space.  For N450:
position 1 in `clades.tsv` = position 1233 in the full measles genome.

For measles specifically, genotype/genotype-group assignments come from Nextclade's
clade output (`clade`, `clade_truncated`), so `clades.tsv` can be left header-only
and node data populated solely from Nextclade.

## QC Notes

In fragment mode the `qc.min_coverage` and `qc.genome_quality` gates are
**inert** for sequences that only cover the target gene (whole-genome `coverage`
will be NaN or very low).  The active gate is
`fragment.min_target_coverage` / `fragment.target_quality`.

`genome_quality` is still annotated in the metadata (for reference), but
`augur filter` in the `curate_qc` rule keys on `target_gene_coverage` and
`target_gene_quality` when `mode: fragment`.

## Example: Measles N450 Genotype B3 — Global

`builds/measles-b3-n450-global/` is the reference fragment build:

- **Reference**: 450-nt N450 slice, single CDS `/gene=N`, id `NC_001498.1`
- **Data source**: Pathoplexus (`measles`)
- **Clade filter**: `clade_truncated` = `B3` (upstream of subsampling)
- **Fragment config**: `target_gene: N`, `min_target_coverage: 0.25` (N450 covers ~28.5 % of the N gene)
- **ViralQC dataset**: `measles-N450-WHO-2012` (declares `target_gene: N`)

### Quick Start

```bash
flexpipe-run \
    --config   builds/measles-b3-n450-global/config.yaml \
    --workdir  /tmp/measles-n450 \
    --run-date 2026-01-01
```

Expected outputs after a full run:

- `<workdir>/results/viralqc/outputs/sequences_target_regions.fasta` — extracted N450 fragments
- `<workdir>/results/subsampled/sequences.fasta` — subsampled N450 sequences
- `<workdir>/auspice/results.json` — N450 tree (450-column alignment)

### Validation

```bash
# Verify the build config before running
flexpipe-validate-build builds/measles-b3-n450-global/config.yaml

# Expected output includes:
#   ✓  mode=fragment: target_gene='N' set
#   ✓  Dataset found: measles-N450-WHO-2012 (target_gene=N, virus=measles)
```

## Extending to Other Viruses

Fragment mode is virus-agnostic.  Examples of Nextclade datasets with `target_gene`:

| Virus | Dataset example | Target gene |
|-------|----------------|-------------|
| Measles | `measles-N450-WHO-2012` | `N` (N450 window) |
| Influenza A H1N1 | `flu_seasonal_h1n1pdm_ha` | `HA` |
| Influenza A H3N2 | `flu_seasonal_h3n2_ha` | `HA` |
| RSV A | `rsv_a` | multiple target regions |

To add a new fragment build:

1. Run `flexpipe-reference-slice` to extract the gene from your whole-genome
   `reference.gb`.
2. Copy an existing fragment build as template (`builds/measles-b3-n450-global/`).
3. Set `mode: fragment`, `fragment.target_gene`, and `viralqc.expected_virus`.
4. Verify: `flexpipe-validate-build builds/my-fragment-build/config.yaml`

## Limitations

- **`viralqc.mode: skip` and `precomputed` are not supported** in v1 fragment mode.
  The extracted `sequences_target_regions.fasta` can only be produced by a live
  `vqc run`.
- **Backbone retention**: backbone strains that fail `targetGeneQuality` cannot be
  force-kept (`--backbone-from` applies only within `augur subsample`).
- **Multi-target datasets**: if a dataset defines multiple `target_regions` (e.g. RSV),
  `target_gene_coverage` covers all regions collectively.  Filtering on a specific
  sub-region is not yet supported.
- **Amino-acid mutations**: `augur translate` uses the single synthesized CDS; complex
  splice junctions or overlapping ORFs in the source genome are not preserved in the
  gene-only reference.
