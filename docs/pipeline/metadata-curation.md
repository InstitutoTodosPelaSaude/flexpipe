# Manual Metadata Curation and Partial Re-runs

Sequence metadata from public databases — including Pathoplexus — sometimes contains
inconsistent or malformed values that cannot be caught automatically. Common examples:

- Geographic fields conflating multiple administrative levels: `geoLocAdmin1 = "Tocantins state (Colinas do Tocantins)"` instead of `geoLocAdmin1 = "Tocantins"` and `geoLocAdmin2 = "Colinas do Tocantins"`.
- Inconsistent accents or spacing in location names: `"São Paulo"` vs `"Sao Paulo"`.
- Partial or ambiguous collection dates that survive normalization.

This page explains how to find these issues, fix them in the source metadata, and
re-run only the affected pipeline steps — without repeating the expensive ViralQC stage.

---

## Step 1 — Identify problematic rows

After an ingest run the following workdir files expose metadata quality issues:

| File | What it shows |
|---|---|
| `results/ingest/date_normalization.tsv` | Rows where date parsing failed or produced an ambiguous result |
| `results/ingest/clade_filter_log.tsv` | All sequences dropped by `clade_filter` (reason: `not_in_include`) |
| Log output during `flexpipe-coordinates` | Nominatim lookup failures (often caused by malformed or unknown location strings) |

To find division values that may contain embedded city names (the Tocantins pattern):

```bash
# Any division value that contains parentheses or "state"
awk -F'\t' 'NR==1{for(i=1;i<=NF;i++) if($i=="division") col=i}
            NR>1 && col && ($col ~ /\(/ || tolower($col) ~ /state/) {print NR, $col}' \
    <workdir>/results/subsampled/metadata.tsv | head -30
```

To inspect a specific accession:

```bash
grep "PP_006BC7E.1" <workdir>/results/ingest/merged_metadata.tsv | \
    cut -f1,3,4,5,6   # accessionVersion, geoLocCountry, geoLocAdmin1, geoLocAdmin2, geoLocCity
```

---

## Step 2 — Fix the source metadata

Edit `data/metadata.tsv` (or whichever file is set in `local.metadata`) directly.
The columns to correct are the **Pathoplexus-convention names** (before rename):

| Column | Renamed to | Notes |
|---|---|---|
| `geoLocAdmin1` | `division` | Brazilian state, or country-level admin region |
| `geoLocAdmin2` | `location` | Municipality / city |
| `geoLocCity` | dropped | Not used after rename; correct `geoLocAdmin2` instead |

**Example fix — Tocantins:**

```
# Before (wrong)
geoLocAdmin1: "Tocantins state (Colinas do Tocantins)"
geoLocAdmin2: ""

# After (correct)
geoLocAdmin1: "Tocantins"
geoLocAdmin2: "Colinas do Tocantins"
```

Use a text editor, a Python/pandas script, or `sed`/`awk` for bulk corrections.
If many rows share the same malformed pattern, a one-liner is enough:

```bash
sed -i '' 's/Tocantins state (Colinas do Tocantins)/Tocantins/g' data/metadata.tsv
```

For more targeted corrections (e.g., split a field), a short Python script is cleaner:

```python
import pandas as pd, re

df = pd.read_csv("data/metadata.tsv", sep="\t", dtype=str).fillna("")

# Pattern: "Tocantins state (CityName)" → division=Tocantins, location=CityName
mask = df["geoLocAdmin1"].str.contains(r"Tocantins state \(", na=False)
df.loc[mask, "geoLocAdmin2"] = df.loc[mask, "geoLocAdmin1"].str.extract(r"\((.+)\)")[0]
df.loc[mask, "geoLocAdmin1"] = "Tocantins"

df.to_csv("data/metadata.tsv", sep="\t", index=False)
```

---

## Step 3 — Re-run ingest without repeating ViralQC

ViralQC (BLAST + Nextclade) is the most time-consuming ingest step. Since a metadata
correction does not change sequences, its results remain valid. Point the pipeline to the
existing ViralQC output using `viralqc.mode: precomputed`:

```yaml
# In builds/<name>/config.yaml — add or update the viralqc section:
viralqc:
  mode: precomputed
  precomputed: "/path/to/workdir/results/viralqc/outputs/results.tsv"
  # All other viralqc keys are ignored in precomputed mode.
  conda_env: "viralQC"
  clade_column: "clade"
  expected_virus: "Dengue virus type 1"
  expected_segment: ""
  datasets_dir: ""
  blast_database: ""
  blast_database_metadata: ""
```

The `results.tsv` path is always `<workdir>/results/viralqc/outputs/results.tsv`.

Then re-run ingest only:

```bash
flexpipe-run \
    --config  builds/<name>/config.yaml \
    --workdir /path/to/workdir \
    --run-date YYYY-MM-DD \
    --stage ingest
```

Snakemake detects that `local_metadata.tsv` is newer than the downstream outputs
and re-runs everything from `merge_local_sequences` onwards, skipping ViralQC.

---

## Step 4 — Re-run phylogenetics if subsampling changed

If the metadata fix altered geographic assignments (division, location) the subsampling
result may differ. Check whether `subsampled/metadata.tsv` changed:

```bash
wc -l <workdir>/results/subsampled/metadata.tsv
# compare against the previous run's count
```

If it changed, run the phylogenetic stage:

```bash
flexpipe-run \
    --config  builds/<name>/config.yaml \
    --workdir /path/to/workdir \
    --run-date YYYY-MM-DD \
    --stage phylo
```

---

## Step 5 — Restore ViralQC to run mode

After validating the corrected build, reset `viralqc.mode` so future full re-runs
(e.g., with updated sequences) execute ViralQC properly:

```yaml
viralqc:
  # mode: precomputed   ← remove or comment out
  conda_env: "viralQC"
  ...
```

---

## Adding corrections to the build's coordinate cache

If the fix changed location strings that were previously geocoded, the old cache entries
are now stale (they're keyed on the wrong name). Add the corrected entries to
`builds/<name>/cache_coordinates.tsv` using the v2 schema:

```tsv
level	name	query	latitude	longitude
location	Colinas do Tocantins	Colinas do Tocantins, Tocantins, Brazil	-8.0530	-48.4761
```

Build-specific cache entries override the shared `flexpipe/data/geo/cache_coordinates.tsv`,
so corrections here are applied immediately on the next ingest run without Nominatim lookups.

---

## Preventing recurrence

For Pathoplexus builds, known malformed patterns can be caught at fetch time by
inspecting the `query_params` to narrow the corpus, or post-fetch by a pre-processing
script applied before `local.metadata` is written. There is currently no built-in
guardrail for free-text geographic fields from external databases; manual correction
and cache seeding remain the recommended workflow.
