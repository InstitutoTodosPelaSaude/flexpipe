# Troubleshooting

## Symptom: augur subsample fails with "subsamples" error

**Error**: `KeyError: 'subsamples'` or `Invalid key 'subsamples'`

**Cause**: Your `subsample.yaml` uses the old Augur 7 key name `subsamples` instead of `samples`.

**Fix**: Update your `subsample.yaml` to use `samples`:

```yaml
# ✗ Old (Augur 7)
subsamples:
  group_by: [division, year]

# ✓ New (Augur 8+)
samples:
  group_by:
    - division
    - year
```

---

## Symptom: ViralQC reports "wrong virus" or "wrong segment"

**Error**: Sequences marked with `genome_quality: "D"` (contamination)

**Cause**: ViralQC alias mismatch or expected virus/segment doesn't match your data.

**Diagnosis**:
1. Check ViralQC output: `results/viralqc/outputs/results.tsv` column `virus` and `segment`
2. Compare against your config: `viralqc.expected_virus` and `viralqc.expected_segment`

**Fix**:
- Update your config to match the actual virus/segment labels in ViralQC output, or
- Create a custom alias file and set `viralqc.aliases_file` to map your labels to ViralQC labels

See [ViralQC Integration](viralqc-integration.md) for alias resolution details.

---

## Symptom: Dates fail to parse ("unknown" or invalid)

**Error**: Sequences with unparseable dates are excluded. Check `results/ingest/date_normalization.tsv` for details.

**Cause**: Date format not recognized by `flexpipe-normalize-dates`.

**Diagnosis**: Review `date_normalization.tsv`:
```
strain	original_date	reason
SEQ_001	2020/01-05	Ambiguous (slash date: could be 2020-01-05 or 2020-05-01?)
SEQ_002	unknown	Unknown literal
```

**Fix**:
1. Manually correct problematic dates in your source data (if possible)
2. Or, customize the date parser by editing `curation.date_formats` in config.yaml (YAML format; see Augur documentation)

---

## Symptom: Alignment fails due to reference version mismatch

**Error**: `MAFFT alignment error` or `sequence too divergent`

**Cause**: Your sequences don't match the reference genome (wrong species, old/new variant, etc.).

**Diagnosis**: Manually check 1–2 sequences against your `reference.gb` in a sequence editor.

**Fix**:
- Update `files.reference` to point to the correct reference, or
- Use ViralQC to identify and filter out contaminated/misidentified sequences (ensure `viralqc.mode: run`)

---

## Symptom: Terminal mask values result in empty alignment

**Error**: `augur mask` produces all-masked sequences or empty regions

**Cause**: Terminal mask values (e.g., `parameters.mask_5prime: 500` on a 3 kb genome) are too large for your reference.

**Diagnosis**: Check your reference genome size. YFV is ~11 kb; mask values are 142/548 bp.

**Fix**:
1. Verify `parameters.mask_5prime` and `parameters.mask_3prime` are reasonable for your reference
2. Use `flexpipe-reference-mask` to auto-generate appropriate values:
   ```bash
   flexpipe-reference-mask --reference builds/my-build/reference.gb --output builds/my-build/masks/reference_terminal.bed
   ```
3. Review the BED file and reference it via `parameters.mask_sites_file`

---

## Symptom: Clades not assigned (empty clades.json)

**Error**: All sequences are marked with no clade; Auspice shows no clade coloring

**Cause**: Your `clades.tsv` is header-only (no mutation rows) or file is missing.

**Diagnosis**: Check `builds/<name>/clades.tsv`:
```
# ✗ Header only
clade	gene	site	alt

# ✓ Has content
clade	gene	site	alt
Clade_A	ORF1ab	100	T
```

**Fix**:
- If you don't have mutation-based clades, populate `clades.tsv` with actual defining mutations
- Or, if header-only is intentional (no clade definitions), that's OK; Auspice will just have no clade coloring

---

## Symptom: Pathoplexus fetch hangs or times out

**Error**: Rule `fetch_pathoplexus` times out after hours

**Cause**: Large query result set (e.g., SARS-CoV-2 with billions of sequences) or rate-limiting.

**Fix**:
1. Add `query_params` to limit the dataset:
   ```yaml
   pathoplexus:
     query_params:
       dataUseTerms: OPEN
       locationRegion: South America
   ```
2. Reduce expected sequence count (filter by date, region, etc.)
3. Use a smaller pathogen or a known-good query

---

## Symptom: NCBI fetch fails with "email not provided"

**Error**: `EmailNotProvidedError` or `NCBI_EMAIL not set`

**Cause**: NCBI requires an email for rate-limiting. It's not configured.

**Fix**: Provide email via one of:
1. Config file: `ncbi.email: user@example.com`
2. Environment variable: `export NCBI_EMAIL=user@example.com`

---

## Symptom: Coordinate geocoding is very slow

**Error**: Pipeline runs for hours on `flexpipe-coordinates` rule

**Cause**: Nominatim API is being hit for every unique location. No caching.

**Fix**:
1. Pre-seed the cache with known locations:
   ```bash
   flexpipe-update-cache --new-cache builds/<name>/cache_coordinates.tsv --existing-cache shared_cache.tsv
   ```
2. Or, set `coordinates.shared_cache` to a pre-built shared cache file to reuse across builds
3. Manaully add entries to `builds/<name>/cache_coordinates.tsv` for frequently-used locations

---

## Symptom: Build is empty — all sequences dropped, tree has 0 sequences

**Error**: `augur filter` exits with `ERROR No sequences remain after filtering` or
subsample fails with fewer than `qc.min_sequences`.

**Most common cause for skip-mode builds**: `clade` is in `qc.required_columns`
while `viralqc.mode: skip` produces no clade column.  `augur filter
--exclude-where clade=` silently drops every sequence with an empty clade field
(which is all of them).

**Diagnosis**:
```bash
# Does the validator catch it?
flexpipe-validate-build builds/<name>/config.yaml
# → FAIL with: "viralqc.mode='skip' produces no 'clade' column, but 'clade' is
#   in qc.required_columns — augur filter will drop ALL sequences."

# Confirm clade is empty in curated metadata
head -1 <workdir>/results/ingest/curated_metadata.tsv | tr '\t' '\n' | grep -n clade
cut -f<clade_col> <workdir>/results/ingest/curated_metadata.tsv | sort | uniq -c | head
```

**Fix**: Remove `clade` from `qc.required_columns`:
```yaml
# ✗ Wrong for skip mode (drops everything)
qc:
  required_columns: [strain, date, country, clade]

# ✓ Correct for skip mode
qc:
  required_columns: [strain, date, country]
```

Also check `traits.columns` (warning) and `clade_filter.column` (warning).
See [ViralQC Integration — Builds Without a Dataset](viralqc-integration.md).

---

## Symptom: Empty or unexpectedly small tree after clade filter

**Symptom**: The final `auspice/results.json` is missing or has far fewer sequences than expected.

**Cause**: `clade_filter` dropped most or all sequences.

**Diagnosis**:
```bash
# Check how many sequences the filter kept/dropped
cat <workdir>/results/ingest/clade_filter_log.tsv | head -20
wc -l <workdir>/results/ingest/clade_filter_log.tsv

# Check what clade values exist in the curated metadata
cut -f <clade_col_number> <workdir>/results/ingest/curated_metadata.tsv | sort | uniq -c | sort -rn | head
```

**Common causes and fixes**:

1. **Wrong column name**: check the actual column names in the curated metadata (`head -1 <workdir>/results/ingest/final_metadata.tsv`). The correct column for top-level genotypes is usually `clade_truncated`, not `clade`.
2. **Wrong match mode**: `match: exact` won't match sub-genotypes. If genotypes appear as `B3.1` instead of `B3`, either use `match: prefix` with `column: clade`, or keep `clade_levels: 1` in `curation:` (so `clade_truncated` is always the first token).
3. **No B3 sequences in the date window**: expand `defaults.min_date` in `subsample.yaml`, check `qc.min_sequences` threshold.

---

## Symptom: clade_filter "column not present" warning — filtering not applied

**Warning**: `clade_filter column 'clade_truncated' not present in metadata; passing through N rows`

**Cause**: `clade_truncated` (or whichever column) was not produced during curation.

**Common causes**:
- ViralQC ran in `skip` or `precomputed` mode and the precomputed file has no `clade` column → `clade_truncated` is never derived.
- `viralqc.expected_virus` is misconfigured and all sequences are flagged contamination grade D, getting empty clades.
- `curation.lineage_parser: "none"` (default) — `genotype`/`major_lineage` columns don't exist unless a parser is configured.

**Fix**: Verify the clade column exists in the curated metadata:
```bash
head -1 <workdir>/results/ingest/curated_metadata.tsv | tr '\t' '\n' | grep -n clade
```

If missing, check ViralQC output:
```bash
head -3 <workdir>/results/viralqc/outputs/results.tsv
```

---

## Symptom: Config validation fails with unknown keys

**Error**: `pydantic.ValidationError: ... extra fields not permitted`

**Cause**: Typo or unsupported key in `config.yaml`.

**Diagnosis**: Check the error message for the offending key (e.g., `viraalqc` instead of `viralqc`).

**Fix**: Correct the typo or remove unsupported keys. See [Configuration Reference](configuration.md) for all valid keys.

---

## Symptom: Workdir is locked but nothing is running

**Error**: `FileExistsError: <workdir>/.flexpipe.lock` and `flexpipe-run` exits with code 2

**Cause**: A previous run crashed or hung, leaving the lock file.

**Fix**:
```bash
rm <workdir>/.flexpipe.lock
```

Then re-run `flexpipe-run`.

---

## Symptom: Integration tests fail with "build not found"

**Error**: `pytest` with `-m integration` fails to discover a build

**Cause**: Build is not registered in `tests/integration/conftest.py`.

**Fix**: Add your build to the integration test configuration. See [Developer Guide](developer-guide.md).

---

## Getting Help

- Check [Configuration Reference](configuration.md) for all available options
- Review [ViralQC Integration](viralqc-integration.md) for data source specific issues
- Check the Snakemake logs: `<workdir>/logs/{ingest,phylo}.log`
- File an issue on [GitHub](https://github.com/InstitutoTodosPelaSaude/flexpipe)
