# Code Review — `700463e..be3f6e4`

**Branch:** `feat/major_code_review`
**Base:** `700463e` (Sprint 5 / Claude)
**Tip:** `be3f6e4` (Codex session)
**Reviewer:** Claude (Opus 4.8) — session 2026-06-07
**Status:** ✅ Passed all CI checks; targeted fixes applied in this review session.

---

## Scope

The range contains four commits:

| Commit | Theme |
|--------|-------|
| `d797553` | Harden flexpipe for scheduled builds (H1–H5, M1–M10) |
| `08da419` | DENV1–4 Brazil builds + pipeline adaptations |
| `2686073` | Remove in-repo review/planning docs |
| `be3f6e4` | Remove empirical DENV `NOTES.md` files |

**Context docs recovered from git history:** `docs/codex_review.md` (original findings) and
`docs/HARDENING_CHANGELOG.md` (implementation summary) are now tracked under `docs/`.
`CLAUDE.md` and `AGENTS.md` are re-staged (were deleted in `2686073`, regenerated on disk).

---

## Verification Baseline (before this review's fixes)

| Check | Result |
|-------|--------|
| `pytest` (unit) | **407 passed**, 32 deselected |
| `pytest -m integration` | **32 passed**, 407 deselected |
| `ruff check .` | ✅ clean |
| `black --check .` | ✅ clean |
| `mypy flexpipe/ --ignore-missing-imports` | ✅ clean |

After this review session's fixes: **410 unit + 35 integration passed**.

---

## Part 1 — Hardening Scorecard (H1–H5 / M1–M10)

All findings from `codex_review.md` are **substantially implemented**. Evidence by finding:

### High Priority

| Finding | Status | Evidence |
|---------|--------|----------|
| **H1** cwd-independent build paths | ✅ | `config.py:104-157` `resolve_config_paths()` resolves all `files.*`, `local_sequences.*`, `parameters.mask_sites_file`, `coordinates.force_file`, `regions.*`, `curation.host_rules`, `colours.hue_tables.*` relative to the build config directory; `config.py:171-187` `resolve_subsample_paths()` handles subsample include/exclude; `run.py:217` writes the fully resolved `snakemake_resolved.yaml`. |
| **H2** optional mask/BED flags not rendered when empty | ✅ | `phylogenetic/Snakefile:112-160` — `_mask_requested` guards the entire rule; mask/BED flags are conditional; empty mask → copy alignment. **This review added `_bed_has_content()` to guard empty-content BED files as well.** |
| **H3** coordinate cache keys include parent context | ✅ | `geo/cache.py:25,50` deduplicates on `["level", "query"]` (v2); `geo/coordinates.py:264-272` writes `query` column; `cache.py:67-109` migrates legacy 4-column caches. |
| **H4** stable hues | ✅ | `colors/hues.py:82-91` `stable_hash_hue()` uses SHA-256; `hues.py:94-131` `load/write_hue_cache()` persists per-build `name2hue.tsv`; cached hue wins before hashing, so categories are stable across additions. |
| **H5** Snakemake shell quoting + config validation | ✅ | Both Snakefiles use `{input:q}/{params:q}/{output:q}` throughout; `config.py:34-46` validates column-list fields; enum-typed fields use `Literal[...]`. |

### Medium Priority

| Finding | Status | Evidence |
|---------|--------|----------|
| **M1** `files.cache` used for seeding | ✅ | `run.py:222` `_seed_coordinate_cache(cfg.files.cache, paths)`; `config.py:122` resolves the path. |
| **M2** Override path resolution (part of H1) | ✅ | Covered by `resolve_config_paths()` in config.py. |
| **M3** Phylogenetic integration tests | ✅ | `tests/integration/test_phylo_wiring.py` added; covers YFV, RSV, DENV1–4 dry-runs from outside the repo. |
| **M4** CPU-heavy rules declare `threads:` | ✅ (partial) | `phylogenetic/Snakefile` `align`, `tree`, `refine` declare `threads: options.threads`; tools derive from `{threads}`. Ingest ViralQC reads `config.get("options", {}).get("threads", 4)` inline — inconsistent but functional. |
| **M5** ViralQC runner configurable | ✅ | `config.py:354-365` `viralqc.runner` (`conda`/`mamba`/`direct`) + `viralqc.executable`; `ingest/Snakefile:44-49` `_viralqc_command()`. |
| **M6** Manifest provenance | ✅ | `manifest.py:215-249` `record_provenance()` records resolved config digest, input fingerprints, git state, tool versions, ViralQC dataset fingerprint. |
| **M7** `qc_exclusion_reason` distinctions | ✅ | `viralqc_join.py:106,120,154,172` sets `missing_viralqc`, `viralqc_quality`, `wrong_virus`, `wrong_segment`; `qc_summary.py:125-130` counts contamination only from `wrong_virus`/`wrong_segment`. **This review fixed the reason-priority order (see below).** |
| **M8** `run_date` validation + upper bound | ✅ | `run.py:50-58` validates `YYYY-MM-DD`; `pathoplexus.py:76` passes `sampleCollectionDateRangeUpperTo`; `ncbi.py:121-123` passes `[PDAT]` upper bound. |
| **M9** Fail-fast guards | ✅ | `merge.py:212-221` exits on missing enabled local files; `viralqc_join.py:82-85` exits on missing `seqName`; `ingest/Snakefile:197-201` exits on zero-sequence FASTA before ViralQC. |
| **M10** NCBI real email required | ✅ | `config.py:438-443` validator; `ncbi.py:209,218-222` exits without email; placeholder default removed. |

---

## Part 2 — DENV / Multi-Build Scorecard

### Build configs (denv1–4-brazil)

The four builds are internally consistent. Correctly differing fields:

| Field | denv1 | denv2 | denv3 | denv4 |
|-------|-------|-------|-------|-------|
| `pathoplexus.query_params.serotype` | DENV-1 | DENV-2 | DENV-3 | DENV-4 |
| `ncbi.taxid` | 11053 | 11060 | 11069 | 11070 |
| `ncbi.genome_size` | 10735 | 10723 | 10707 | 10649 |
| `viralqc.expected_virus` | "Dengue virus type 1" | …type 2 | …type 3 | …type 4 |
| Reference | NC_001477 | NC_001474 | NC_001475 | NC_002640 |
| `ignore.txt` | NC_001477 | NC_001474 | NC_001475 | NC_002640 |

Shared first-pass profile: `model: JC`, `ufboot: 0`, `mask_5prime/3prime: 0`, `date_confidence: false`, `traits_confidence: false`. No copy-paste cross-references found.

### New pipeline modules

| Module | Assessment |
|--------|------------|
| `flexpipe/curate/lineage_parser.py` | Correct. Dengue parser is prefix-safe (`3III_B`, never bare `B`). `pango` is a valid alias for `generic_dot`. |
| `flexpipe/phylo/traits.py` | Correct. `collapse_trait_states()` uses `df.copy()` — primary metadata is never mutated. Sidecar is wired correctly in the Snakefile. |
| `flexpipe/colors/hues.py` + `scheme.py` | Correct. Top-level hues use SHA-256 stable hash + persistent cache. Child shades are deterministic `(root, level, member)` hashes. No instability on category additions (verified by test). |

### Integration tests

All four DENV builds have ingest and phylo dry-run coverage. DENV references are real NC_ accessions, so phylo tests execute (not skipped). Hierarchy assertion (`--levels serotype genotype major_lineage minor_lineage clade`) was previously parametrized over denv3/4 only; this review extended it to all four.

### Deleted docs (2686073, be3f6e4)

- `CLAUDE.md`, `AGENTS.md`: regenerated on disk; re-staged in this review session.
- `HARDENING_CHANGELOG.md`, `codex_review.md`: restored to `docs/` from git history.
- `builds/denv*/NOTES.md`: removed per `be3f6e4`; key content captured in `builds/GAPS_LOG.md` and `builds/PIPELINE_FIXES.md`.

---

## Part 3 — Findings by Severity

All remaining findings are **Minor** — none block production runs.

### Fixed in this session

| ID | Fix |
|----|-----|
| H2-residual | `phylogenetic/Snakefile`: `_bed_has_content()` helper guards against empty-content BED files rendering `--mask`. Covered by `test_empty_bed_mask_file_takes_copy_path_not_augur_mask`. |
| M7-residual | `viralqc_join.py:172`: `wrong_segment` now only writes when `qc_exclusion_reason` is blank, preserving a prior `wrong_virus` reason. Covered by `test_wrong_virus_reason_is_not_overwritten_by_wrong_segment`. |
| lineage_parser gaps | Added `test_pango_alias_delegates_to_generic_dot_lineage` and `test_apply_lineage_parser_parsed_serotype_wins_on_conflict`. |
| DENV hierarchy coverage | `test_denv_reference_builds_render_new_visual_hierarchies` extended to all four DENV builds. |
| Doc recovery | `docs/codex_review.md`, `docs/HARDENING_CHANGELOG.md` restored; `CLAUDE.md`, `AGENTS.md` re-staged. |

### Deferred (documented, no code change)

| ID | Note |
|----|------|
| H1-note | `_resolve_path_value()` in the Snakefile has a repo-root fallback that can silently resolve a same-named repo file when a build-relative file is missing. Intentional design tradeoff; add a warning log if confusion occurs in practice. |
| H5-note | `qc.genome_quality` and `qc.required_columns` lists are shell-safe via `:q` quoting but not enum-validated. No unsafe-value vector exists (values are quoted); add Literal validation if these lists are exposed via a web UI. |
| scheme.py | Child shade index has no anti-collision probing (SHA-256 mod 91 can produce identical colours for two members under the same root). Visual-only; the probability is low with typical category counts. |
| `spread_hues()` | Function is tested but not called in production (only `collect()` is used). Can be removed or documented as an alternative strategy. |
| M4 (ingest threads) | ViralQC ingest rule reads threads inline rather than using `options.threads` namespace. Functional; clean up when ingest Snakefile is next edited. |
| NCBI `run_date` semantic | `ncbi` uses publication date (`PDAT`) as the upper bound; Pathoplexus uses collection date. A sequence collected before `run_date` but published after will be excluded from NCBI builds. Document in `docs/service_contract.md`. |

---

## Recommended Next Steps

1. **Commit this session's changes** (6 source files + 5 test files + 4 doc files) on `feat/major_code_review`.
2. **Continue empirical builds** per `plan_builds_continuation.md` — next batch: ZIKV + CHIKV (NCBI, Brazil).
3. **Merge `feat/major_code_review` → `main`** after any final review; the codebase is production-leaning for unattended scheduled runs.
4. **Provide clade definitions** (mutation-based TSVs) for DENV1–4 to enable branch labelling; calibrate terminal masks once reference-specific values are known.
5. **Curate a shared Brazil geocode seed cache** from the runtime caches accumulated during DENV live runs to reduce Nominatim load on future builds.
