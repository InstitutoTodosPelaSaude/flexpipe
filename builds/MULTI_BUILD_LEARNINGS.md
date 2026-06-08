# Multi-Build Learnings

> Synthesis from empirical flexpipe runs across DENV1-4 and continuation builds
> (ZIKV, CHIKV, RSV-A/B, OROV-L, Flu HA). Last updated: 2026-06-08.

## Executive synthesis

The multi-build expansion moved flexpipe from a YFV/DENV-centered workflow toward a
genuinely reusable first-pass pathogen pipeline. The strongest evidence is that
Pathoplexus whole-genome builds, NCBI whole-genome builds, one NCBI L-segment build,
and three influenza HA builds all reached Auspice export with the same Snakemake
boundary, workdir layout, QC summary, coordinate generation, trait sidecar, and
first-pass phylogenetic profile.

Most failures were not tree-building failures. They clustered earlier: source-specific
metadata quirks, ViralQC naming contracts, Pathoplexus identifier shapes, Augur sample
schema details, and NCBI date sentinels. Dry-runs were valuable for DAG wiring, but
live runs were the only way to expose many real blockers, especially INSDC missing
values, flu segment names, RSV Nextclade naming, geocoding runtime, and high-volume
NCBI records with inconsistent date formats.

The successful pattern was conservative: scaffold a minimal build, keep biological
parameters explicit and documented, run with a cheap first-pass phylo profile, classify
failures as config-only versus pipeline bug, and only harden the pipeline when a gap
blocked multiple builds or represented a general contract mismatch.

The remaining limitations are mostly not hidden bugs. They are known product choices:
header-only mutation clade TSVs, reference-derived masks that still need biological
review, no segmented fan-out, uncapped context sampling, and Nominatim-bound geocoding.
Those are acceptable for first-pass empirical builds, but they should be resolved
before production surveillance or very high-volume SARS-CoV-2-style runs.

## Pathogen coverage matrix

| Build | Source | Segment | Live E2E | Key friction | Fix class |
|-------|--------|---------|----------|--------------|-----------|
| `denv1-brazil` | Pathoplexus | genome | Yes | Shared dengue organism, FASTA suffixes, no-mask path, cheap tree profile | Pipeline + config |
| `denv2-brazil` | Pathoplexus | genome | Yes | Runtime-heavy tree and trait confidence; geocoding volume | Pipeline + config |
| `denv3-brazil` | Pathoplexus | genome | Yes | Lineage/trait/color reference build; header-only clades | Pipeline + config |
| `denv4-brazil` | Pathoplexus | genome | Yes | Smaller reference build; header-only clades | Pipeline + config |
| `zikv-brazil` | NCBI | genome | Yes | INSDC sentinel dates such as `missing: synthetic construct` | Pipeline |
| `chikv-brazil` | NCBI | genome | Yes | Slow geocoding for many locations | Operational / deferred |
| `rsv-a-brazil` | Pathoplexus | genome | Yes | RSV ViralQC `results.tsv` names differ from BLAST metadata; bad subsample schema in first scaffold | Config |
| `rsv-b-brazil` | Pathoplexus | genome | Yes | Same RSV naming/schema pattern as RSV-A | Config |
| `orov-l-brazil` | NCBI | L | Yes | Single-segment scope; NCBI credentials fields added | Config |
| `flu-h1n1-ha-brazil` | NCBI | HA | Yes | Flu virus names are strain-specific; segment labels are `HA`/numeric mixed; INSDC `unknown` dates | Pipeline + config |
| `flu-h3n2-ha-brazil` | NCBI | HA | Yes | MM/DD/YYYY dates and flu segment-name mismatch | Pipeline + config |
| `flu-b-ha-brazil` | NCBI | HA | Yes | Flu B segment labels use names, not RefSeq numbers | Config |

## Learnings by pipeline stage

### Ingest (fetch, merge, ViralQC)

- Pathoplexus is flexible enough for multiple Brazil-focused builds when `organism`
  plus `query_params` can express subtypes, serotypes, and open-data filters. DENV
  needed `organism: dengue` with `serotype=DENV-N`; RSV needed `organism: rsv-a` or
  `rsv-b` with `dataUseTerms=OPEN`.
- NCBI is the broadest data source but the messiest. GenBank records surfaced INSDC
  sentinel values (`missing:*`, `unknown`, `none`, `null`), slash-delimited dates, and
  high-volume fetches where live evidence mattered more than dry-run planning.
- ViralQC is a useful cross-pathogen filter, but its output contract is not a simple
  mirror of `blast.tsv`. RSV and flu showed that `results.tsv` names can be Nextclade
  dataset names or strain-specific BLAST names rather than stable organism labels.
- Exact `expected_virus` / `expected_segment` checks work well for DENV, ZIKV, CHIKV,
  and OROV-L, but RSV and flu need alias/regex matching because ViralQC labels can be
  Nextclade dataset names, strain-specific BLAST names, or segment synonyms.

### Curation & QC

- Normalizing ViralQC sequence IDs is essential. DENV Pathoplexus FASTA IDs contained
  pipe suffixes that did not match metadata accessions until the join accepted
  pipe-normalized names.
- Missing ViralQC join rows must remain missing, not be reclassified as wrong-virus
  contamination. That distinction preserves useful QC counts and avoids false
  exclusion cascades.
- The explicit `continent` column solved a real semantic split: `region` can remain a
  Brazil macro-region for `region_source: division`, while `continent` supports global
  context and TreeTime traits.
- DENV lineage decomposition is useful only when labels are prefix-safe. Derived
  `genotype`, `major_lineage`, and `minor_lineage` must keep their parent prefixes
  (`3III_B`, not bare `B`) to avoid conflicts across serotypes or genotypes.

### Subsampling & geography

- The working Brazil-focal template is `samples: brazil/context`, with Brazil grouped
  by `division, year, month` and context grouped by `country, year, month`. This is now
  the safest scaffold pattern.
- Augur does not allow `sequences_per_group` and `max_sequences` in the same sample
  block, so exact monthly context sampling cannot also be capped in one step. This is a
  known tradeoff, not an implementation bug.
- Geocoding is a real runtime bottleneck. Location-rich builds such as DENV and CHIKV
  spend substantial time on Nominatim unless runtime caches are seeded or source cache
  files are curated.

### Phylogenetics & export

- The first-pass phylo profile (`model: JC`, `ufboot: 0`, `date_confidence: false`,
  `traits_confidence: false`, reviewed terminal BED masks) is the right empirical
  default on limited hardware. It turns build validation into a bounded workflow
  instead of a production inference exercise.
- Header-only `clades.tsv` files are workable for first-pass metadata coloring when
  ViralQC/Nextclade supplies a `clade` column, but mutation-based branch labels remain
  absent until real clade TSVs are provided.
- The explicit no-mask branch matters. `augur mask` fails when every mask input is
  empty or zero, so copying the alignment is the correct behavior for uncalibrated
  first-pass builds.
- Trait state capping via `metadata_traits.tsv` keeps TreeTime tractable without
  mutating exported subsampled metadata.

### Visualization (colors, coordinates, Auspice)

- Hierarchical color configuration is now reusable: geography can be
  `continent country division location`, and DENV lineages can be
  `serotype genotype major_lineage minor_lineage clade`.
- Root hues should be stable and cached; child shades should stay inside parent hue
  families. This is much more interpretable for Brazil-focal builds with global
  context than flat hash colors.
- Auspice configs should keep raw `clade` available even when derived lineage filters
  are added. The raw lineage is still the user's "lineage" filter.

## Code adjustments compendium

### Pathoplexus query filters and FASTA suffix handling

- **Problem:** DENV is one Pathoplexus organism with serotype filters, and DENV FASTA
  IDs can include suffixes such as `|DENV-1`.
- **Root cause:** The original fetcher had no generic LAPIS query-param map and assumed
  FASTA IDs matched metadata accessions exactly.
- **Change:** Added `pathoplexus.query_params` and `pathoplexus.strip_fasta_id_suffix`
  support in `flexpipe/ingest/pathoplexus.py`; DENV configs use `serotype` and
  `dataUseTerms=OPEN`.
- **Tests:** `tests/unit/test_pathoplexus.py`; ingest dry-run coverage for DENV1-4.
- **Status:** Implemented.

### ViralQC join hardening

- **Problem:** Missing ViralQC rows and pipe-suffixed IDs caused false wrong-virus
  exclusions.
- **Root cause:** Joins were too literal, and missing `_nc_virus` values were compared
  as if they were observed contamination.
- **Change:** Hardened `flexpipe/curate/viralqc_join.py` to normalize IDs and apply
  virus/segment checks only to present values.
- **Tests:** `tests/unit/test_viralqc_join.py`.
- **Status:** Implemented.

### Optional phylogenetic paths

- **Problem:** First-pass builds with zero masks, header-only clades, and no support
  measures hit hardcoded phylo assumptions.
- **Root cause:** `augur mask`, `augur clades`, IQ-TREE UFBoot, `augur refine`, and
  `augur traits` flags were rendered unconditionally.
- **Change:** Added no-mask copy path, empty-clade JSON fallback, `ufboot: 0`,
  `date_confidence`, and `traits_confidence` behavior in `phylogenetic/Snakefile`.
- **Tests:** `tests/integration/test_phylo_wiring.py`.
- **Status:** Implemented.

### First-pass profile convention

- **Problem:** Production-style model search and support were too slow for empirical
  multi-build validation.
- **Root cause:** Original template defaults were optimized for production YFV-style
  analysis, not exploratory scaling.
- **Change:** New builds use `model: JC`, `ufboot: 0`, `date_confidence: false`, and
  `traits_confidence: false`.
- **Tests:** Phylo dry-runs assert the rendered IQ-TREE/refine/traits flags.
- **Status:** Implemented as a config convention.

### NCBI INSDC sentinel normalization

- **Problem:** ZIKV and flu live runs hit unparseable metadata values such as
  `missing: synthetic construct` and `unknown`.
- **Root cause:** GenBank qualifiers used INSDC sentinel strings that Augur date
  formatting treats as literal dates or locations.
- **Change:** Added `_normalize_insdc()` in `flexpipe/ingest/ncbi.py` and applied it to
  `collection_date` and `geo_loc_name` / `country`.
- **Tests:** `tests/unit/test_ncbi.py`.
- **Status:** Implemented.

### Flexible date normalization

- **Problem:** H3N2 records included MM/DD/YYYY dates, and other NCBI records use
  partial dates or sentinels that should be normalized before Augur.
- **Root cause:** The ingest Snakefile treated all date flexibility as Augur's job,
  making unexpected formats a hard runtime failure.
- **Change:** Added `flexpipe-normalize-dates`, `curation.date_formats`, and
  `flexpipe/data/curation/date_formats.yaml`. The ingest workflow now writes
  `results/ingest/date_normalization.tsv` before `augur curate format-dates`.
- **Tests:** `tests/unit/test_dates.py` plus ingest dry-run rendering.
- **Status:** Implemented.

### Subsample schema correction

- **Problem:** Several continuation scaffolds used `subsamples:` and inline command
  syntax, which Augur rejected.
- **Root cause:** Template drift from the accepted Augur `samples:` schema.
- **Change:** RSV-A/B, OROV-L, and flu subsample files now use `samples:`, plain
  `query`, list-form `group_by`, and `sequences_per_group`.
- **Tests:** `test_all_scaffold_builds_dry_run` covers all scaffold builds.
- **Status:** Implemented.

### ViralQC alias registry

- **Problem:** RSV Pathoplexus live runs and flu HA builds could not be represented
  reliably with one exact virus/segment string.
- **Root cause:** ViralQC `results.tsv` names can differ from BLAST metadata names,
  flu virus names are strain-specific, and flu segments mix values such as `4` and
  `HA`.
- **Change:** Added `flexpipe/data/viralqc/aliases.yaml`, `viralqc.aliases_file`, and
  alias/regex matching in `flexpipe/curate/viralqc_join.py`. RSV and flu configs now
  use operational alias keys instead of blank workarounds.
- **Tests:** `tests/unit/test_viralqc_aliases.py` and `tests/unit/test_viralqc_join.py`.
- **Status:** Implemented.

### Reference-derived terminal masks

- **Problem:** New first-pass builds had no terminal mask files and relied on zero
  terminal masks.
- **Root cause:** Reference-specific masking had been treated as a manual production
  calibration step, leaving no first-draft mask aid for new pathogens.
- **Change:** Added `flexpipe-reference-mask` and
  `flexpipe/data/phylo/reference_mask_profiles.yaml`. Per-build
  `masks/reference_terminal.bed` files now derive terminal masks from UTR annotations
  or CDS/gene boundaries with guardrails.
- **Tests:** `tests/unit/test_reference_mask.py` and phylo dry-run assertions for
  configured BED masks.
- **Status:** Implemented as first-draft production aid; biological review still
  required before surveillance use.

### Shared geocode seed cache

- **Problem:** Location-rich builds repeatedly paid Nominatim runtime costs from empty
  source caches.
- **Root cause:** Runtime caches were per-workdir and build seeds were isolated; there
  was no shared seed layer.
- **Change:** Added bundled `flexpipe/data/geo/cache_coordinates.tsv` and
  `coordinates.shared_cache`; workdirs seed from shared cache first and build-specific
  cache second.
- **Tests:** `tests/unit/test_coordinate_cache.py`.
- **Status:** Partially implemented; high-uncached-count warnings remain deferred.

### Trait, lineage, and color hardening

- **Problem:** TreeTime trait inference could explode on many states, and geography /
  lineage colors were too flat for Brazil-focal context builds.
- **Root cause:** Traits used primary metadata directly, `region` had overloaded
  semantics, and DENV lineages were not decomposed into prefix-safe hierarchy columns.
- **Change:** Added `continent`, `flexpipe-collapse-traits`, lineage parsers, and
  hierarchy-aware hue/color behavior.
- **Tests:** `tests/unit/test_traits.py`, `tests/unit/test_lineage_parser.py`,
  `tests/unit/test_colour_scheme.py`, integration phylo dry-runs.
- **Status:** Implemented; production visual review still recommended.

## Config conventions established

- Use the first-pass phylo profile for new empirical builds unless production tuning is
  explicitly requested: `JC`, `ufboot: 0`, confidence flags disabled, and
  reference-derived terminal BED masks reviewed before surveillance use.
- Keep `clades.tsv` present even when header-only. Raw metadata `clade` can still power
  filters/colors, but mutation branch labels require real TSV rows later.
- For Brazil-focal builds with global context, use `region_source: division`,
  `coordinates.columns: "country division location"`, and traits/colors that include
  `continent` and `country`.
- For NCBI builds, include `email: ""` and `api_key: ""` in config and rely on
  `NCBI_EMAIL` / `NCBI_API_KEY` at runtime.
- For Pathoplexus builds, prefer source-side open-data filtering with
  `query_params.dataUseTerms: OPEN`.
- For segmented first-pass builds, keep one segment per build. Use alias-backed
  `expected_segment` keys when ViralQC emits multiple synonymous labels.
- Treat `builds/denv3-brazil` / `builds/denv4-brazil` as the visualization and DENV
  lineage references; treat `zikv-brazil` or `chikv-brazil` as the NCBI genome
  template; treat `orov-l-brazil` as the NCBI single-segment template.

## Known limitations (deferred)

- **P1:** Mutation clade TSVs remain manual per pathogen.
- **P1:** Reference-derived terminal BED masks should be reviewed and, where needed,
  calibrated against pilot alignments before production surveillance use.
- **P2:** Geocoding still needs warning/reporting for large uncached batches and more
  curated shared city seeds.
- **P2:** Brazil-focal context sampling cannot cap global context while preserving exact
  monthly `sequences_per_group` in a single Augur sample block.
- **P2:** Production profiles still need support policy and clade TSVs per pathogen.
- **P3:** Segmented-virus fan-out, reassortment logic, and multi-segment outputs remain
  out of scope.

## Implications for next batches

- **SARS-CoV-2:** Expect volume, fetch, and subsampling limits to dominate. Start with
  a tighter query/date window and avoid uncapped context until a two-stage sampler or
  explicit context cap exists.
- **Production phylo profiles:** Do not promote first-pass outputs to surveillance
  defaults without masks, clades, model/support policy, and review of trait confidence.
- **Flu live runs:** First-pass E2E succeeded and alias-backed segment validation now
  handles `HA`/`4`; production flu still needs reference-strain policy per
  subtype/lineage.
- **Build templates:** The most reusable unit is not a copied directory; it is a small
  checklist: source contract, ViralQC naming contract, sample schema, reference, first
  phylo profile, then live-run notes.

## Appendix: open biological inputs

- Mutation-based clade definitions for DENV1-4, ZIKV, CHIKV, RSV-A/B, OROV-L, and flu
  HA builds.
- Review of generated reference-terminal BED masks for every new build.
- Production phylogenetic model/support policy for each pathogen family.
- Flu HA reference-strain policy and whether vaccine-strain or representative-reference
  choices should vary by season/subtype.
- RSV clade nomenclature depth and whether RSV-A/B Brazil builds should adopt a parser
  analogous to DENV once a stable lineage grammar is approved.
- OROV-L confirmation that single L-segment scope remains sufficient for first-pass
  analysis and that M/S fan-out remains out of scope.
