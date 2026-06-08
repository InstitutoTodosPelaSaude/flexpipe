# ViralQC Integration

flexpipe integrates [ViralQC](https://github.com/InstitutoTodosPelaSaude/viralQC) for automated genome quality control and viral classification via BLAST and [Nextclade](https://docs.nextstrain.org/projects/nextclade/en/stable/).

## Configuration

ViralQC settings live in the `viralqc` section of `config.yaml`:

```yaml
viralqc:
  expected_virus: "dengue"
  expected_segment: "genome"
  conda_env: "viralqc"
  clade_column: "nextclade_clade"
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
- `nextclade_clade` — Nextclade-assigned clade
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
