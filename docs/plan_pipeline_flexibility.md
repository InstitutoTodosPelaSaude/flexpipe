# Pipeline Flexibility & Local-Data Analysis Mode
## Design document and implementation plan

> **Status:** approved for implementation — 2026-06-08  
> **Branch:** `feat/major_code_review`  
> **Scope:** targeted externalization + local ingest path + validator.  No rewrite.

---

## 1. Executive summary

flexpipe now runs end-to-end for 14 pathogen builds across Pathoplexus whole-genome, NCBI
whole-genome, and NCBI single-segment sources.  A Phase-0 audit shows the curation, QC, colour,
geo, and date layers are **already ~80% config/data-driven**.  Two behaviours still require
editing Python to extend: the lineage-parser enum dispatch and the hard-coded Brazil division
parser.  The remote-fetch assumption is baked into the `data_source` enum and Snakemake DAG.

After the work described here:
- **All four "add a pathogen" axes** — data source, lineage scheme, geography parsing, QC source —
  are reachable via config + in-tree registration with no enum edits.
- **A local-data analysis mode** (`data_source: local`) lets users skip remote fetch entirely.
- **A build validator** (`flexpipe-validate-build`) catches the live-run blockers from `GAPS_LOG.md`
  before a run starts.
- **Integration-test auto-discovery** removes the duplicated hardcoded build lists from both test
  files.

**What stays out of scope:** multi-segment fan-out/reassortment, auto-derived clade TSVs,
SARS-CoV-2-scale subsampling, external entry-point plugins, the `flexpipe-scaffold` generator
(deferred).

---

## 2. Definitions

| Term | Definition after this work |
|---|---|
| **Add a pathogen** | Copy an archetype build directory, edit `config.yaml`/`subsample.yaml`/`reference.gb`/`clades.tsv`; register a new lineage or division parser if needed (in-tree only); run `flexpipe-validate-build` to catch mistakes before a live run. |
| **No new Python for most pathogens** | Data source, ViralQC aliases, host rules, date formats, clade truncation, region maps, drop columns — all reachable from YAML/TSV without touching Python. Lineage + division parsers are the exception and are handled by the in-tree registry. |
| **Information model** | Documented stage-by-stage column contracts (§6). |
| **Local-only mode** | `data_source: local` — user supplies canonical `metadata.tsv` + `sequences.fasta`; no fetch, optional ViralQC; all downstream stages (curate, subsample, phylo, export) preserved. |

---

## 3. Phase-0 audit

### 3.1 Already externalized (pattern to follow)

| Behavior | Mechanism | Key files |
|---|---|---|
| Country→continent | `regions.country_map` + TSV override | `regions.py:30-38`, `data/regions/country_to_continent.tsv` |
| Brazil state→region / abbrev | `regions.division_map` + TSV overrides | `regions.py:41-72` |
| Host normalization | Generic rule-type interpreter + YAML | `hosts.py:64-77`, `data/hosts/host_rules.yaml` |
| Drop columns | Bundled YAML, no config key needed | `columns.py:22-24`, `data/curation/drop_columns.yaml` |
| ViralQC virus/segment matching | Alias/regex registry (data-driven) | `viralqc_join.py:133-199`, `data/viralqc/aliases.yaml` |
| Clade truncation | `clade_levels` / `clade_separator` config | `clades.py:12` |
| Date normalization | YAML policy, configurable override | `dates.py`, `data/curation/date_formats.yaml` |
| Phylo mask / clades / ufboot / confidence | Explicit config-driven conditionals | `phylogenetic/Snakefile:27-39,50-60,121-209,227,328` |

### 3.2 Genuine code coupling — fixed by registry (§7)

| Location | Behavior | Today | After |
|---|---|---|---|
| `lineage_parser.py:85-93` + `config.py:324` | Lineage parser dispatch | `if/elif` + closed `Literal["none","dengue","pango","generic_dot"]` | `@register_parser("name")` dict; config validates against registry keys |
| `pipeline.py:109-123` + `regions.py:157-215` | Brazil division string parsing | `division_parser=="brazil"` branch → `_parse_brazil_division` (IBGE/City-UF/UF regexes) | Registry keyed by `cfg.regions.division_parser`; `brazil` is a registered parser; internal logic unchanged |
| `pipeline.py:26-33` | Brazil-named symbol imports in orchestrator | Imports `_parse_brazil_division`, `build_brazil_maps`, `lookup_brazil_region`, etc. | Generic registry dispatch; Brazil parser retains its own module-private internals |

### 3.3 Remote-fetch coupling — fixed by local mode (§8)

| Location | Behavior | Impact for local mode |
|---|---|---|
| `ingest/Snakefile:87-91` | `_source` string selects `_RAW_METADATA/_RAW_SEQUENCES` filenames | Adding `_source="local"` routes merge input automatically — DAG is already extensible |
| `ingest/Snakefile:120-151` | `fetch_pathoplexus` / `fetch_ncbi` rules | Add sibling `rule fetch_local` (copy; no network) |
| `merge.py:207-261` | Merge treats remote as authority | Local mode bypasses merge; `fetch_local` writes merged outputs directly |
| `ingest/Snakefile:183-221` | ViralQC is unconditional hard dependency | Add conditional precomputed/skip branch (§9) |
| `ingest/Snakefile:241-251` | `augur curate rename` hard-coded to PPX vocabulary | Local metadata must present canonical column names; validator enforces |
| `config.py:422` | `data_source: Literal["pathoplexus","ncbi"]` | Widen to `["pathoplexus","ncbi","local"]` |

### 3.4 Scaffolding friction — fixed by validator + auto-discovery (§10)

| Issue | Evidence | Fix |
|---|---|---|
| Build lists duplicated in both integration test files | `test_ingest_wiring.py:34-63` and `test_phylo_wiring.py:16-35` are separate hardcoded lists; new build must be added twice | Auto-discovery via `builds/*/config.yaml` glob |
| Column contracts scattered | `qc.required_columns` per build, phylo-seed header in `test_phylo_wiring.py:46-48`, fixtures | Central doc in §6 |
| `cache_coordinates.tsv` v1 vs v2 header inconsistency | zikv uses v1 `level query lat lon display_name`; contract is v2 `level,name,query,latitude,longitude` | Validator warns |
| Live-run blockers never caught before run | Subsample schema, alias key validity, missing BED, missing email | Validator |

---

## 4. Target architecture overview

```
builds/<name>/
  config.yaml           ← data_source: pathoplexus | ncbi | local (NEW)
  subsample.yaml
  reference.gb
  clades.tsv
  auspice_config.json
  keep.txt / ignore.txt / cache_coordinates.tsv
  masks/reference_terminal.bed  (optional)
  local_data/           ← metadata.tsv + sequences.fasta  (local mode only)

flexpipe/
  curate/
    lineage_parser.py   ← _PARSERS registry, @register_parser decorator
    regions.py          ← _DIVISION_PARSERS registry, @register_division_parser
    pipeline.py         ← dispatch via registries, no Brazil literals
  validate.py           ← flexpipe-validate-build entry point (NEW)
  config.py             ← data_source += "local"; viralqc.mode field (NEW)
  ingest/
    (no change to fetch modules)
ingest/Snakefile        ← rule fetch_local (NEW); merge passthrough for local;
                           conditional ViralQC rule (NEW)
tests/integration/
  conftest.py           ← BUILD_CONFIGS auto-discovered glob helper (NEW)
  test_ingest_wiring.py ← hardcoded lists replaced by shared fixture
  test_phylo_wiring.py  ← same
```

---

## 5. Local-mode user story and inputs

**User story:**  
"I downloaded NCBI records, cleaned the metadata in a spreadsheet, and have a FASTA of QC-passed
sequences.  I want subsample → tree → Auspice JSON using flexpipe's pipeline conveniences, without
setting up Pathoplexus credentials or waiting for a remote fetch."

**Entry point:** `flexpipe-run --config builds/my-local/config.yaml --workdir /tmp/run`  
Same CLI, same stages, same manifest/lock.  Only the DAG wiring changes.

**Required inputs:**
- `local_sequences.metadata`: a TSV with at minimum `strain`, `date`.  Additional canonical columns
  (`country`, `division`, `location`, `clade`, `source`, `data_use`) improve downstream steps but
  are not required — curate synthesizes sensible defaults for missing ones.
- `local_sequences.sequences`: FASTA with IDs matching the `strain` column.

**Skipped stages:** `fetch_pathoplexus`, `fetch_ncbi`, `merge_local_sequences` (replaced by
passthrough copy).

**QC options (controlled by `viralqc.mode`):**
- `run` (default): full ViralQC pipeline — requires datasets installed.
- `precomputed: <path>`: user-supplied `results.tsv` in ViralQC output format is copied in; no
  `vqc` invocation.
- `skip`: a synthetic `results.tsv` is generated from sequence length + any existing `clade`
  column; `genome_quality=A`, `coverage` estimated, `qc.overallStatus=good`.  Validator warns that
  quality is unverified.

**Preserved conveniences:** curate pipeline, date normalization, subsample, colors, coordinates,
phylogenetics, manifest, workdir isolation.

**Relationship to existing `local_sequences` merge:** the existing `local_sequences.enabled` path
*adds* local sequences on top of a remote fetch.  The new `data_source: local` *replaces* the
remote fetch entirely.  Use `local_sequences.enabled` when supplementing surveillance data; use
`data_source: local` when the user owns the full dataset.

---

## 6. Stage-by-stage metadata contract (normative)

This is the single source of truth replacing the scattered per-build `required_columns` and the
de-facto contract buried in `test_phylo_wiring.py:46-48`.

### Post-merge (input to curate)
Required: `strain` or `accessionVersion` (detected by `merge.py:detect_id_column`)  
Expected PPX-style fields (rename targets): `accessionVersion`, `sampleCollectionDate`,
`geoLocCountry`, `geoLocAdmin1`, `geoLocAdmin2`, `dataUseTerms`, `lineage`, `host`.

For **local mode**: metadata must already use canonical names (`strain`, `date`, `country`,
`division`, `location`, `data_use`, `clade`, `host`) OR go through the same `augur curate rename`
field-map — if so, the source column names above are required.  The validator enforces this.

### Post-curate (output of `flexpipe-curate`, input to subsample)
Required: `strain`, `date`  
Expected: `continent`, `country`, `division`, `location`, `clade`, `clade_truncated`, `region`,
`source`, `data_use`, `genome_quality`, `coverage`  
Optional (lineage parser configured): `serotype`, `genotype`, `major_lineage`, `minor_lineage`

### Post-subsample / phylo input (static inputs to `phylogenetic/Snakefile`)
Same columns as post-curate.  The phylo Snakefile reads `strain`, `date`, `clade`, `clade_truncated`
plus whatever `traits.columns` specifies.

### ViralQC results contract (input to curate join)
Required: `seqName`, `genomeQuality`, `coverage`, `qc.overallStatus`, `virus`, `segment`  
Clade column: configurable via `viralqc.clade_column` (default `clade`)

---

## 7. Phase 2 — Lineage + division parser registries

### 7.1 Lineage registry (`flexpipe/curate/lineage_parser.py`)

```python
_PARSERS: dict[str, Callable[[object], dict[str, str]]] = {}

def register_parser(name: str):
    def deco(fn):
        _PARSERS[name] = fn
        return fn
    return deco

def available_parsers() -> list[str]:
    return sorted(_PARSERS)

@register_parser("none")
def _parse_none(clade): return {}

@register_parser("dengue")
def parse_dengue_lineage(clade): ...   # existing implementation, unchanged

@register_parser("pango")
@register_parser("generic_dot")
def parse_generic_dot_lineage(clade): ...   # existing, unchanged

def parse_lineage(clade: object, parser: str) -> dict[str, str]:
    if parser not in _PARSERS:
        raise ValueError(
            f"Unsupported lineage parser: {parser!r}. "
            f"Available: {available_parsers()}"
        )
    return _PARSERS[parser](clade)
```

`config.py:324`: replace `Literal["none","dengue","pango","generic_dot"]` with `str` + validator:
```python
@field_validator("lineage_parser")
@classmethod
def validate_lineage_parser(cls, v):
    from flexpipe.curate.lineage_parser import available_parsers
    if v not in available_parsers():
        raise ValueError(f"lineage_parser {v!r} not in {available_parsers()}")
    return v
```

### 7.2 Division parser registry (`flexpipe/curate/regions.py`)

```python
_DIVISION_PARSERS: dict[str, Callable] = {}

def register_division_parser(name: str):
    def deco(fn):
        _DIVISION_PARSERS[name] = fn
        return fn
    return deco

def available_division_parsers() -> list[str]:
    return sorted(_DIVISION_PARSERS)

@register_division_parser("none")
def _parse_none_division(division, **kwargs): return division, ""

@register_division_parser("brazil")
def _parse_brazil_division(division, **kwargs): ...   # existing, unchanged
```

`pipeline.py:109-123`: replace the `division_parser == "brazil"` literal branch:
```python
from flexpipe.curate.regions import _DIVISION_PARSERS, available_division_parsers

if region_source == "division" and "division" in df.columns:
    parser_fn = _DIVISION_PARSERS.get(division_parser)
    if parser_fn is None:
        logger.warning(
            "division_parser %r not registered; available: %s",
            division_parser, available_division_parsers(),
        )
    else:
        parsed = df["division"].apply(lambda d: parser_fn(d, abbrev=..., canonical=...))
        ...
```

`config.py:335`: add validator against `available_division_parsers()`.

**Migration:** `dengue`, `brazil`, `none`, `pango`, `generic_dot` all remain valid config keys.
No build config file changes required.

---

## 8. Phase 3 — `data_source: local`

### Config changes (`flexpipe/config.py`)
```python
data_source: Literal["pathoplexus", "ncbi", "local"] = "pathoplexus"
```
New `@model_validator` for `data_source == "local"`:
- Requires `local_sequences.metadata` and `local_sequences.sequences` to exist (reuse the
  existing enabled-local check at `config.py:153-160`; set `local_sequences.enabled = True`
  implicitly when `data_source == "local"`).
- Skips the `pathoplexus.organism` and `ncbi.taxid`/`ncbi.email` validators.

### Snakefile changes (`ingest/Snakefile`)
```python
# line ~90: _source already drives RAW path names; no change needed there

rule fetch_local:
    """Copy user-supplied metadata + sequences into the ingest results slot.
    Only triggered when data_source=local."""
    input:
        metadata  = config.get("local_sequences", {}).get("metadata", ""),
        sequences = config.get("local_sequences", {}).get("sequences", ""),
    output:
        metadata  = f"{_wd}/results/ingest/local_metadata.tsv",
        sequences = f"{_wd}/results/ingest/local_sequences.fasta",
    shell:
        """
        cp {input.metadata:q}  {output.metadata:q}
        cp {input.sequences:q} {output.sequences:q}
        """
```

`merge_local_sequences`: add a passthrough branch when `_source == "local"`:
```python
if _source == "local":
    # Bypass merge — local data is already the full dataset
    rule merge_local_sequences:
        input:  metadata=_RAW_METADATA, sequences=_RAW_SEQUENCES
        output: metadata=_MERGED_METADATA, sequences=_MERGED_SEQUENCES
        shell:  "cp {input.metadata:q} {output.metadata:q} && cp {input.sequences:q} {output.sequences:q}"
else:
    rule merge_local_sequences:
        ...  # existing rule unchanged
```

### Example build: `builds/local-example/`
A committed fixture build for integration tests:
- `config.yaml`: `data_source: local`, `viralqc.mode: skip`, first-pass phylo profile.
- `local_data/metadata.tsv`: 15 synthetic rows with canonical column names.
- `local_data/sequences.fasta`: 15 synthetic sequences.
- Standard `reference.gb`, `clades.tsv`, `subsample.yaml`, `auspice_config.json`.

---

## 9. Phase 4 — Precomputed + skippable ViralQC

### Config
```python
class ViralqcConfig(BaseModel):
    ...
    mode: Literal["run", "precomputed", "skip"] = "run"
    precomputed: str = ""   # path to pre-existing results.tsv when mode=precomputed
```
Validator: `mode == "precomputed"` requires `precomputed` path to exist.

### Snakefile conditional
```python
_viralqc_mode = config.get("viralqc", {}).get("mode", "run")

if _viralqc_mode == "run":
    rule viralqc:
        ...  # existing rule, unchanged

elif _viralqc_mode == "precomputed":
    rule viralqc:
        input:  config["viralqc"]["precomputed"]
        output: f"{_wd}/results/viralqc/outputs/results.tsv"
        shell:  "cp {input:q} {output:q}"

else:  # skip
    rule viralqc:
        input:  f"{_wd}/results/ingest/merged_sequences.fasta"
        output: f"{_wd}/results/viralqc/outputs/results.tsv"
        params: genome_size = config.get("ncbi", {}).get("genome_size", 0)
        script: "scripts/synthesize_viralqc.py"
```

The `synthesize_viralqc.py` script: reads merged metadata, computes `coverage` from FASTA sequence
length / `genome_size` (or 1.0 if unknown), writes a ViralQC-shaped TSV with `genomeQuality=A`,
`qc.overallStatus=good`, clade from an existing metadata column if present (configurable via
`viralqc.clade_column`).

**Migration:** `mode` defaults to `"run"` → all 14 existing builds are untouched.

---

## 10. Phase 5 — Validator + integration-test auto-discovery

### `flexpipe-validate-build` (`flexpipe/validate.py`)

```
$ flexpipe-validate-build builds/measles-brazil/config.yaml

✗  subsample.yaml: 'subsamples' key found — augur requires 'samples'       [subsample-schema]
✗  parameters.mask_sites_file=masks/reference_terminal.bed — file not found [missing-bed]
✗  viralqc.expected_segment='4' is not a registered alias key               [unknown-alias]
⚠  ncbi.email empty and NCBI_EMAIL unset (required at runtime)             [ncbi-email]
⚠  cache_coordinates.tsv uses v1 header — expected v2 (level,name,query,…) [cache-schema]
ℹ  clades.tsv is header-only — no branch labels (acceptable for first pass) [header-only-clades]
✓  reference.gb present and not PLACEHOLDER
✓  data_source/organism/taxid prerequisites satisfied
```

Checks (each maps to a real `GAPS_LOG.md` entry):

| Check | Failure class | Source |
|---|---|---|
| `subsample.yaml` uses `samples:`, list `group_by`, plain `query` | error | GAPS_LOG: subsample schema |
| `mask_sites_file` set → BED exists and non-empty | error | GAPS_LOG: empty BED |
| `expected_virus`/`expected_segment` known alias keys | error | GAPS_LOG: flu segment naming, RSV virus naming |
| `data_source` prereqs: ncbi→email, ppx→organism, local→files exist | error/warning | GAPS_LOG: NCBI email |
| `reference.gb` present and not `PLACEHOLDER` | warning | BUILD_ROSTER: phylo skip |
| `cache_coordinates.tsv` v2 header | warning | audit inconsistency |
| `clades.tsv` header-only | info | acceptable first-pass |
| `traits.columns` includes `continent country` for Brazil focal builds | warning | convention |

Exit codes: `0` = no errors (warnings/info OK), `1` = one or more errors.

### Integration-test auto-discovery

Replace the hardcoded lists in both test files with a shared `conftest.py` helper:

```python
# tests/integration/conftest.py
import glob, pathlib

def all_build_configs():
    """Discover all builds with a real (non-PLACEHOLDER) reference."""
    root = pathlib.Path(__file__).parents[2] / "builds"
    configs = sorted(root.glob("*/config.yaml"))
    return [p for p in configs if p.parent.name not in {"__pycache__"}]

def real_reference_builds():
    """Subset: builds whose reference.gb is not a PLACEHOLDER."""
    result = []
    for cfg in all_build_configs():
        ref = cfg.parent / "reference.gb"
        if ref.exists() and "PLACEHOLDER" not in ref.read_text():
            result.append(cfg)
    return result
```

Tests use `@pytest.mark.parametrize("build_config", all_build_configs(), ids=...)`.
Archetype-specific assertion methods (yfv production profile, denv lineage columns, etc.) remain as
named methods but also use the helpers to drive parametrization.

---

## 11. Commit roadmap

| # | Commit | Intent | Files changed | Tests | Rollback |
|---|---|---|---|---|---|
| 1 | `docs: pipeline flexibility audit and target architecture` | Land this doc + update service_contract | `docs/plan_pipeline_flexibility.md`, `docs/service_contract.md` (§6 column contracts), `builds/PIPELINE_FIXES.md` | n/a | delete doc |
| 2 | `refactor: lineage and division parser registries` | Remove the two enum/branch couplings | `lineage_parser.py`, `regions.py`, `pipeline.py`, `config.py` | extend `test_lineage_parser.py`; add `test_regions.py` | config keys unchanged; revert module |
| 3 | `feat: data_source local ingest path` | User-supplied data → pipeline, no fetch | `config.py`, `ingest/Snakefile`, `builds/local-example/` | ingest dry-run: `fetch_local` present, fetch_ppx/ncbi absent | new enum value, opt-in; revert rule |
| 4 | `feat: precomputed and skippable ViralQC` | BYO-QC and no-QC paths | `config.py`, `ingest/Snakefile`, `scripts/synthesize_viralqc.py` | precomputed + skip dry-runs; synthesizer unit | `mode: run` default; no existing build changes; revert |
| 5 | `feat: flexpipe-validate-build and test auto-discovery` | Pre-run blocker detection; remove duplicate build lists | `flexpipe/validate.py`, `cli.py`, `pyproject.toml`, `tests/integration/conftest.py`, both wiring test files | validator unit; self-validate all 14 builds must pass | keep validator advisory only |

---

## 12. Gap analysis mapped to GAPS_LOG + MULTI_BUILD_LEARNINGS

| Gap | Fixed by | Phase |
|---|---|---|
| Subsample `subsamples:` schema errors (RSV/OROV/flu) | Validator check | 5 |
| Flu segment `"4"` vs `"HA"` naming | Alias registry (already done); validator checks alias validity | 5 |
| RSV `expected_virus` Nextclade naming | Alias registry (already done); validator | 5 |
| NCBI email required | Validator check | 5 |
| Lineage parser enum edit required | Registry | 2 |
| Brazil division parser edit required | Registry | 2 |
| No local-only ingest mode | `data_source: local` | 3 |
| ViralQC mandatory even when data pre-curated | `viralqc.mode` | 4 |
| New build requires editing two test files | Auto-discovery | 5 |
| Column contracts scattered / undocumented | §6 | 1 |
| Empty BED causes wrong masking | Validator check | 5 |

Items from `MULTI_BUILD_LEARNINGS.md` "Known limitations (deferred)" remain deferred:
- Mutation clade TSVs (P1) — manual biological input
- Geocoding warning/reporting for large batches (P2)
- Brazil-focal context cap without `sequences_per_group` conflict (P2)
- Production phylo profiles (P2)
- Segmented-virus fan-out (P3)

---

## 13. Risk register

| Risk | Mitigation |
|---|---|
| Regression on 14 existing builds | Registry keys backward-compatible; `viralqc.mode` defaults `run`; local is opt-in; auto-discovery covers all builds in ingest dry-run; full integration suite before every commit |
| `augur curate rename` silently drops local columns not in PPX vocabulary | Validator enforces required canonical columns for local mode; documented in §6 |
| Synthesized QC (`mode: skip`) masks real quality issues | Explicit config opt-in; validator warns; `mode: run` is default |
| Registry import-time error / circular import | Register parsers in the same module that defines them; unit-test `available_parsers()` membership at import |
| `fetch_local` copy path for large datasets (memory/disk) | `cp` is shell-level; Snakemake will not load into Python memory; same as existing fetch outputs |
| Auto-discovery picks up incomplete scaffold directories | Validator self-check on all discovered builds in CI; `PLACEHOLDER` reference guard already in phylo dry-run |

---

## 14. Verification

Run after every commit:

```bash
conda run -n nextstrain pytest -q
conda run -n nextstrain pytest -m integration -q
conda run -n nextstrain ruff check .
conda run -n nextstrain black --check .
conda run -n nextstrain mypy flexpipe/ --ignore-missing-imports
```

Post-Phase-3 smoke test:
```bash
flexpipe-run --config builds/local-example/config.yaml \
    --workdir /tmp/local-run --stage ingest
```

Post-Phase-5 validation sweep:
```bash
for cfg in builds/*/config.yaml; do
    flexpipe-validate-build "$cfg" || echo "FAILED: $cfg"
done
```

All 14 existing builds must keep ingest + phylo dry-run green throughout.
