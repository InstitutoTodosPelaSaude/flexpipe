# Scaffold Checklist

Concise checklist for adding a new flexpipe build without repeating the multi-build
expansion footguns.

## All Builds

- Choose one data source: `pathoplexus` or `ncbi`.
- Add the standard files: `config.yaml`, `subsample.yaml`, `auspice_config.json`,
  `clades.tsv`, `reference.gb`, `keep.txt`, `ignore.txt`, `cache_coordinates.tsv`.
- Use a real public GenBank `reference.gb`; record accession and rationale in notes.
- Keep `clades.tsv` header-only only for first-pass analyses; mutation clade TSVs are
  manual pathogen inputs.
- Use the first-pass phylo profile unless production tuning is requested:
  `model: JC`, `ufboot: 0`, `date_confidence: false`, `traits_confidence: false`.
- Generate a first-draft terminal BED with:
  `flexpipe-reference-mask --reference builds/<name>/reference.gb --output builds/<name>/masks/reference_terminal.bed`
- Set `parameters.mask_sites_file: "builds/<name>/masks/reference_terminal.bed"` when
  the generated BED has reviewed terminal intervals.
- Set `traits.columns` to include `continent country` for Brazil-focal builds with
  global context, and keep `traits.max_states` / `traits.rare_state_label` explicit.
- Add or confirm build coverage in `tests/integration/test_ingest_wiring.py` and
  `tests/integration/test_phylo_wiring.py`.
- After live runs, update `builds/BUILD_ROSTER.md`, per-build notes, and
  `builds/GAPS_LOG.md` with stage, evidence, fix class, and remaining blockers.

## Pathoplexus Brazil Build

- Start from `builds/denv3-brazil` or `builds/rsv-a-brazil`.
- Set `pathoplexus.organism` to the LAPIS organism slug.
- Put public-data filters in `pathoplexus.query_params`; prefer
  `dataUseTerms: OPEN`.
- For shared organisms such as dengue, use query params for subtype/serotype instead
  of inventing per-serotype slugs.
- If LAPIS FASTA headers include metadata suffixes, set
  `pathoplexus.strip_fasta_id_suffix: true`.
- Use Brazil-focal subsampling:
  `samples.brazil.query: "country == 'Brazil'"` and context
  `query: "country != 'Brazil'"`.

## NCBI Genome Build

- Start from `builds/zikv-brazil` or `builds/chikv-brazil`.
- Set `ncbi.taxid`, `ncbi.genome_size`, and reference accession explicitly.
- Leave `ncbi.email: ""` and use `NCBI_EMAIL` / `NCBI_API_KEY` at runtime.
- Confirm `viralqc.expected_virus` against ViralQC `results.tsv`, not only
  `blast.tsv`; use an alias key when names vary.
- Expect date normalization to handle common sentinels and partial/slash dates, but
  inspect `results/ingest/date_normalization.tsv` after live runs.

## NCBI Single-Segment Build

- Start from `builds/orov-l-brazil` for L-segment or a flu HA build for HA.
- Keep one segment per build; flexpipe does not fan out segmented viruses.
- Use a segment-appropriate reference and `ncbi.genome_size`.
- Set `viralqc.expected_segment` to an alias key when labels vary, e.g. `ha`.
- Document explicitly that other segments are out of scope for the build.

## Alias-Sensitive ViralQC Build

- Prefer operational alias keys such as `rsv_a`, `flu_a_h1n1`, or `ha`.
- Add new aliases to `flexpipe/data/viralqc/aliases.yaml`; use
  `viralqc.aliases_file` only for build-local experiments.
- Store ICTV species names as metadata, but do not rely on broad ICTV species names as
  operational QC targets when subtypes/serotypes matter.
- Avoid broad substring matching; use exact aliases or explicit regex patterns.
- Keep `unclassified` as wrong when `expected_virus` is configured.

## Geocoding

- Put reusable country/division/city seeds in the shared cache when they apply broadly:
  `flexpipe/data/geo/cache_coordinates.tsv`.
- Put build-specific corrections in `builds/<name>/cache_coordinates.tsv`; these win
  over shared entries with the same `(level, query)`.
- Use the v2 cache schema:
  `level`, `name`, `query`, `latitude`, `longitude`.
