# ViralQC Integration

flexpipe integrates [ViralQC](https://github.com/InstitutoTodosPelaSaude/viralQC) for automated genome quality control and viral classification via BLAST and [Nextclade](https://docs.nextstrain.org/projects/nextclade/en/stable/).

## Configuration

ViralQC settings live in the `viralqc` section of `config.yaml`:

```yaml
viralqc:
  expected_virus: "dengue"
  expected_segment: "genome"
  conda_env: "viralqc"
  clade_column: "clade"
  aliases_file: ""
  datasets_dir: ""
  blast_database: "nt"
  blast_database_metadata: ""
  executable: "vqc"
  runner: "conda"
  mode: "run"
  precomputed: ""
```

### Mode Options

| Mode | Behavior | When to Use |
|------|----------|-------------|
| `run` | Execute ViralQC | First-pass analysis; typical use case |
| `precomputed` | Use pre-generated results file | Reanalysis with existing QC |
| `skip` | Skip ViralQC entirely | Data already QC'd; rapid turnaround |

## Clade Column Selection

`viralqc.clade_column` (default `"clade"`) selects which column of ViralQC's
`results.tsv` becomes the pipeline's `clade` metadata field (joined in
`flexpipe/curate/viralqc_join.py`). This matters because ViralQC v1.1.0 retains
several alternative clade columns per dataset, and Nextclade's naming has drifted
over time — for some viruses the default `clade` column is now a sparse new
nomenclature that leaves most sequences `unassigned`.

Choose `clade_column` per virus:

| Virus / dataset | `clade_column` | Notes |
|-----------------|----------------|-------|
| Seasonal influenza A HA; flu-B Victoria (per-lineage dataset) | `legacy-clade` | Yields the classic clade (e.g. `6B.1A.5a.2a`). The default `clade` is the new sparse subclade system and returns mostly `unassigned` for older sequences. |
| Combined flu-B dataset | `legacy-clade-vic` | Lineage-suffixed variant of `legacy-clade`. |
| hMPV | `legacy_clade` | Underscore (not hyphen); gives classic names such as `A2b1` / `A2b2`. |
| measles, RSV, dengue, YFV, Zika, mumps, SARS-CoV-2 (pango) | `clade` (default) | Keep the default. |

Background: Nextclade's 2025-10-22 influenza update moved the classic clade to
`legacy-clade`. On a broad flu reference set, leaving `clade_column` at the
default `clade` gives roughly 0% clade assignment.

Two robustness behaviors in the join:

- **`<int>.0` normalization**: pure-integer legacy clades that an older
  `results.tsv` coerced to float text (e.g. `1.0`) are collapsed back to `1`, so
  a clade does not split into separate `1` and `1.0` categories.
- **Missing-column warning**: if the configured `clade_column` is absent from the
  ViralQC output, a warning is logged and `clade` is left blank (previously it was
  silently blank with no signal).

## Alias Resolution

### Why Aliases?

ViralQC labels viruses and segments based on ICTV taxonomy. However, abbreviations and aliases vary:

- DENV is labeled `Dengue virus` in ViralQC, not `DENV` or `Dengue`
- Flu HA segment is `H1`, `H3`, or `HA` depending on context
- RSV segments are `L`, `G`, `N`, etc.

To avoid manual label mapping, flexpipe uses **alias lookup**: you specify operational names, and the pipeline resolves them to ViralQC labels.

### Alias Files

**Built-in aliases**: `flexpipe/data/viralqc/aliases.yaml`

```yaml
dengue:
  - "Dengue virus"
  - "dengue"
  - "DENV"

rsv:
  - "Respiratory syncytial virus"
  - "RSV"
  - "rsv"

flu_a_h1n1:
  - "Influenza A virus"
  - "Influenza A (H1N1)"
  - "A/H1N1"
```

**Custom aliases**: Create your own YAML and set `viralqc.aliases_file` in config:

```yaml
viralqc:
  aliases_file: "/path/to/my_aliases.yaml"
```

Custom aliases override built-in ones.

### Usage Example

YFV build config:

```yaml
viralqc:
  expected_virus: "yfv"
  expected_segment: "genome"
```

ViralQC outputs include a `virus` column. If it matches "Yellow fever virus" (the ViralQC label) through the alias chain (`yfv` → "Yellow fever virus"`), sequences are accepted.

## Datasets

ViralQC uses genome datasets for classification. Resolution order:

1. **Config**: `viralqc.datasets_dir` (if specified)
2. **Environment**: `$VIRALQC_DATASETS_DIR` (if set)
3. **Auto-discover**: `viralQC/datasets/` (submodule path; if present)

Datasets are large (~5–10 GB) and downloaded via `bash scripts/install_viralqc.sh`.

## Output Integration

ViralQC outputs a TSV with columns:
- `strain` — sequence ID
- `virus` — ICTV species name (matched against aliases)
- `segment` — viral segment (matched against expected)
- `clade` — Nextclade-assigned clade (or an alternative column selected via `clade_column`; see above)
- `genome_quality` — grade (A, B, C, D)
- `coverage` — aligned fraction (0.0–1.0)

The `curate_qc` rule joins these results into the main metadata:

```yaml
curate_qc:
  input:
    metadata: <fetched metadata>
    viralqc: <viralqc results.tsv>
  output:
    metadata: <curated_metadata.tsv with genome_quality, coverage, clade columns>
```

## Quality Grades

ViralQC assigns genome quality grades:

| Grade | Meaning |
|-------|---------|
| `A` | High-quality, full genome |
| `B` | Good-quality, near-full genome |
| `C` | Partial or low-coverage genome |
| `D` | Contamination, wrong organism, or wrong segment |

Filter by grade in `config.yaml`:

```yaml
qc:
  genome_quality:
    - A
    - B
```

Sequences with grades C or D are excluded.

## Builds Without a ViralQC/Nextclade Dataset

Some viruses are absent from the ViralQC BLAST reference set or have no
Nextclade dataset. The canonical example is **Mayaro virus**: the BLAST set
(`viralQC/datasets/blast.tsv`) covers many sibling alphaviruses (Chikungunya,
Una, Madariaga, VEEV, Ross River) but not Mayaro, and no Nextclade dataset
exists for it.

### How to detect a missing dataset

1. Check the BLAST reference set:
   ```bash
   grep -i "mayaro" viralQC/datasets/blast.tsv   # empty → absent
   grep -i "chikungunya" viralQC/datasets/blast.tsv  # present → covered
   ```
2. Check the Nextclade datasets directory:
   ```bash
   ls viralQC/datasets/ | grep -i mayaro   # empty → no dataset
   ```
3. If both checks return empty, use `viralqc.mode: skip`.

### The `skip` recipe for no-dataset viruses

```yaml
viralqc:
  mode: "skip"        # synthesize grade-A results; no BLAST/Nextclade
  expected_virus: ""  # no contamination filter (no reference to compare against)
  expected_segment: ""
```

When `genome_size` is set (from `ncbi.genome_size` or `pathoplexus.genome_size`),
`coverage` is computed as `min(seq_len / genome_size, 1.0)`. This means
`qc.min_coverage` acts as a real **sequence-length filter** even in skip mode:

```yaml
ncbi:
  genome_size: 11411     # bp — enables length-based coverage
qc:
  min_coverage: 0.70     # drops sequences shorter than ~8 kb (70% of 11,411)
```

Without `genome_size`, all sequences get `coverage = 1.0` and no length
filtering is applied.

### Required config changes for skip mode

Three sections must be adjusted to avoid silent failures when there is no clade
column. `flexpipe-validate-build` will **error** on the first issue and warn on
the others:

| Section | What to change | Why |
|---------|---------------|-----|
| `qc.required_columns` | **Remove `clade`** | skip mode produces no clade; `augur filter --exclude-where clade=` drops ALL sequences |
| `traits.columns` | Remove `clade` | skip mode produces no clade; augur traits infers an empty column |
| `clade_filter` | Don't filter on `clade`/`clade_truncated` | no clade column → filter is always a no-op |

Example clean skip-mode config:
```yaml
qc:
  required_columns:
    - strain
    - date
    - country          # never 'clade' in skip mode

traits:
  columns: "continent country"   # never 'clade' in skip mode
```

### Limitations

- **No contamination detection**: skip mode accepts all sequences as grade A;
  cross-organism contamination is not flagged. NCBI taxid-scoped queries and
  length filtering are the only guards.
- **No clade/genotype coloring**: the `clade` and `clade_truncated` metadata
  columns remain empty. Remove clade from `colours.clade` and `auspice_config`
  colorings, or they will display empty values.
- **Production use**: switch to `viralqc.mode: run` once a Nextclade dataset
  becomes available. Check <https://github.com/nextstrain/nextclade_data> for
  new pathogen additions.

---

## Fragment Mode: Target-Gene Columns

When `mode: fragment` is set in `config.yaml`, flexpipe additionally reads three
ViralQC output columns that are ignored in whole-genome mode:

| ViralQC column | Mapped to | Type | Meaning |
|----------------|-----------|------|---------|
| `targetGeneCoverage` | `target_gene_coverage` | float 0–1 | Fraction of the target gene covered |
| `targetGeneQuality` | `target_gene_quality` | str (A/B/C/D) | Quality grade for the target region |
| `targetGene` | `target_gene` | str | Name of the target gene |

These are joined into the curated metadata and exposed as filters in `augur filter`
(replacing the whole-genome `coverage` / `genome_quality` gate).

### Sequence Source

In fragment mode, the `curate_qc` rule uses ViralQC's extracted sequence file as its
`--sequences` input instead of the merged raw FASTA:

```
<workdir>/results/viralqc/outputs/sequences_target_regions.fasta
```

This file contains each record trimmed to the target region.  Length-heterogeneous
inputs (mix of 450-nt fragments + full 15,910-nt genomes) are all reframed to the
gene window by `augur align` against the gene-only reference.

### Dataset Requirement

Fragment mode requires a Nextclade dataset that declares `target_gene` (or
`target_regions`) for your virus.  `flexpipe-validate-build` reads the ViralQC
datasets registry and errors if no matching dataset is found.

```bash
# Check available datasets + target genes
cat viralQC/viralqc/config/datasets.yml | grep -A3 "target_gene"
```

### Mode Restrictions

| ViralQC mode | Whole-genome | Fragment |
|--------------|:---:|:---:|
| `run` | ✓ | ✓ |
| `precomputed` | ✓ | ✗ (v1) |
| `skip` | ✓ | ✗ |

`precomputed` and `skip` are forbidden in fragment mode because neither produces
`sequences_target_regions.fasta` or the target-gene columns.

---

## Troubleshooting

### ViralQC Runs but Reports Wrong Virus

**Cause**: Alias mismatch or typo

**Solution**: Check your `expected_virus` against the ViralQC output. List available viruses:

```bash
vqc --list-viruses
```

Update `aliases_file` to map your label to the ViralQC label.

### ViralQC Times Out

**Cause**: BLAST database download or Nextclade inference on large dataset

**Solution**:
- Run ingest with `--cores 1` to reduce I/O
- Use `viralqc.mode: precomputed` if QC is already done elsewhere
- Check disk space (datasets + temp BLAST files can be large)

### Precomputed Mode Won't Load

**Cause**: File format mismatch or missing columns

**Solution**:
- Verify your precomputed TSV has `strain`, `genome_quality`, `coverage`, and clade columns
- Ensure strain IDs match your sequence identifiers exactly

### Skip Mode Causes Alignment Failures

**Cause**: Unfiltered sequences are too divergent for alignment

**Solution**:
- Run ViralQC to filter contaminants and wrong organisms
- Or manually filter sequences before local mode
