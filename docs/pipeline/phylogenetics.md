# Phylogenetics Pipeline

The phylogenetics stage (`phylogenetic/Snakefile`) builds and calibrates a phylogenetic tree from subsampled sequences produced by the ingest stage.

## Input

- `results/subsampled/metadata.tsv` — sequence metadata (strain, date, region, etc.)
- `results/subsampled/sequences.fasta` — aligned or unaligned sequences
- `reference.gb` — reference genome (GenBank format; e.g., YFV: X03700.1)
- Build config (`parameters.*`, `options.*`, `traits.*`)

## Alignment

**Rule**: `augur align`

Aligns sequences to reference using MAFFT:

```bash
mafft --add {sequences} {reference} → {alignments.fasta}
```

**Output**: `results/alignments/sequences.fasta`

## Masking

**Rule**: `augur mask`

Masks problematic regions of the alignment. Two modes:

### Terminal Masking

Masks terminal X bp from 5′ and 3′ ends of the alignment. Reference-specific:

| Virus | Reference | 5′ mask | 3′ mask |
|-------|-----------|---------|---------|
| YFV | X03700.1 | 142 bp | 548 bp |
| New build | (unknown) | 0 | 0 |

These values come from `parameters.mask_5prime` and `parameters.mask_3prime`. If both are 0, masking is skipped and sequences are copied.

```{warning}
Terminal mask values are **per-reference** and specific to the genome structure. When adding a new pathogen, mask values must be derived from the new reference (UTR length, etc.). See [flexpipe-reference-mask](../commands.md) for automated suggestions.
```

### Additional Site Masking

Optional file-based masking via BED (Browser Extensible Data):

- `parameters.mask_sites_file` — path to BED file with additional sites to mask
- Example: problematic polyA tracts, high-homoplasy regions

**Output**: `results/alignments/masked.fasta`

## Tree Building

**Rule**: `iqtree3`

Builds a maximum-likelihood tree using IQ-TREE 3:

```bash
iqtree3 -s {masked.fasta} -m {parameters.model} -B {parameters.ufboot} -T AUTO
```

### Parameters

| Parameter | Type | Default | Example |
|-----------|------|---------|---------|
| `parameters.model` | string | (required) | `MFP` (auto), `JC`, `GTR+G` |
| `parameters.ufboot` | int | 0 | 1000 (enable), 0 (disable) |

**First-pass profile**: `ufboot: 0` (fast, no bootstrap)

**Production profile**: `ufboot: 1000` (slower, high-confidence)

**Output**: `results/trees/tree.nwk` (Newick format)

## Temporal Calibration (Refine)

**Rule**: `augur refine`

Calibrates the tree in time using TreeTime. Estimates dates for internal nodes based on sequence collection dates.

### Parameters

| Parameter | Options | Example |
|-----------|---------|---------|
| `parameters.root` | least-squares, min_dev, oldest, best | `least-squares` |
| `parameters.coalescent` | skyline, opt, const, fixed | `skyline` |
| `parameters.date_inference` | marginal, joint | `marginal` |
| `parameters.clock_filter_iqd` | float | 3.0 |
| `parameters.date_confidence` | boolean | true |

**Output**: 
- `results/refine/tree.nwk` — refined branch lengths (time)
- `results/node_data/branch_lengths.json` — JSON node data

## Mutation Reconstruction

### Nucleotide Mutations

**Rule**: `augur ancestral`

Reconstructs nucleotide mutations on the tree:

```bash
augur ancestral --tree {tree} --alignment {alignment} --output {nt_muts.json}
```

**Output**: `results/node_data/nt_muts.json`

### Amino Acid Mutations

**Rule**: `augur translate`

Translates nucleotide mutations to amino acid level:

```bash
augur translate --tree {tree} --alignment-input-format fasta --reference-sequence {reference.gb} --output {aa_muts.json}
```

**Output**: `results/node_data/aa_muts.json`

## Ancestral State Inference

**Rule**: `augur traits`

Infers ancestral states for discrete metadata traits (geographic, clade-based) using TreeTime's maximum-parsimony method.

### Configuration

```yaml
traits:
  columns:
    - region
    - country
    - division
    - clade_truncated
  max_states: 15
  rare_state_label: "Other"
```

**Behavior**:
- For each column, infer ancestral states at internal nodes
- If a trait has > `max_states` unique values, rare states are collapsed to `rare_state_label` in the output JSON only (primary metadata is unchanged)
- Required for coloring and filtering in Auspice

**Output**: `results/node_data/traits.json`

## Clade Assignment

**Rule**: `augur clades`

Assigns clade labels to branches based on mutation patterns. Reads from `clades.tsv` in the build directory.

**clades.tsv format** (tab-separated):
```
clade	gene	site	alt
Clade_A	ORF1ab	100	T
Clade_A	S	501	Y
Clade_B	ORF1ab	100	A
```

If the file is header-only (no data rows), no clade assignments are made; the output is an empty JSON object.

**Output**: `results/node_data/clades.json`

## Export

**Rule**: `augur export v2`

Combines all node data, tree, metadata, and config into Auspice-compatible JSON:

```bash
augur export v2 --tree {tree} --metadata {metadata} --node-data {all json files} \
  --auspice-config {auspice_config.json} --output {auspice/results.json}
```

**Inputs**:
- Tree (time-calibrated)
- Subsampled metadata
- All node data files (nt_muts, aa_muts, traits, clades, branch_lengths)
- `auspice_config.json` (colorings, filters, panels)

**Output**: `auspice/results.json` (ready for visualization)

## Auspice Configuration

The `auspice_config.json` file (in your build directory) defines:

- **colorings**: metadata fields available for coloring the tree (with custom color schemes if desired)
- **filters**: metadata fields available as interactive filters
- **panels**: which panels are shown in the sidebar (tree, map, clock, etc.)
- **geo_resolutions**: geographic hierarchy (country, division, location)

**Example**:
```json
{
  "colorings": [
    {
      "key": "region",
      "title": "Region",
      "type": "categorical"
    },
    {
      "key": "clade_truncated",
      "title": "Genotype",
      "type": "categorical"
    }
  ],
  "filters": ["region", "country", "division"]
}
```

## Outputs Summary

Phylogenetics completes with:
- `auspice/results.json` — visualization-ready JSON (open with `auspice view`)
- `results/node_data/*.json` — intermediate data (mutations, traits, clades)
- `results/refine/tree.nwk` — time-calibrated tree (Newick)
