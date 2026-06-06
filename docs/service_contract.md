# flexpipe Service Execution Contract

This document defines the minimum contract for running flexpipe unattended, such
as from cron, a scheduler, or a future web service. It is not a web application
design. It describes the inputs, ownership boundaries, resource controls, and
failure semantics the pipeline now enforces.

## Build Inputs

Each run is defined by:

- `config_path`: path to one build `config.yaml`.
- `workdir`: writable per-build run directory.
- `run_date`: ISO `YYYY-MM-DD` reference date.

`flexpipe-run` validates `run_date` before Snakemake starts. Build-relative
paths in `config.yaml` are resolved against `config_path.parent`, then written
as absolute paths to `<workdir>/config/snakemake_resolved.yaml`. Direct
Snakemake invocations should pass the build config path as `build_config=<path>`
when possible, or use the resolved config produced by `flexpipe-run`.

Resolved path semantics apply to:

- `files.*`
- `local_sequences.*`
- `parameters.mask_sites_file`
- `coordinates.force_file`
- `regions.*`
- `curation.host_rules`
- `colours.hue_tables.*`
- `subsample.yaml` `defaults.exclude`, sample `include`, and sample `exclude`

Optional empty paths remain empty. Explicit override files fail fast when
required. Disabled local-sequence paths may be absent; enabled local sequences
must provide existing metadata and FASTA files.

## Workdir Ownership

The source tree is read-only at runtime. Generated state belongs under
`workdir`:

- `results/`: ingest, subsampled, alignment, tree, node-data, and QC artifacts
- `auspice/`: exported Auspice JSON
- `config/`: resolved Snakemake config, resolved subsample config, latlongs,
  `name2hue.tsv`, and `colour_scheme.tsv`
- `cache/`: mutable coordinate and hue caches
- `logs/`: stage logs
- `manifest.json`: run status and provenance

Coordinate cache ownership:

- Build seed: `cfg.files.cache`, read-only.
- Runtime cache: `<workdir>/cache/cache_coordinates.tsv`.
- Internal cache format is v2: `level`, `name`, `query`, `latitude`,
  `longitude`.
- Augur output remains `latlongs.tsv` compatible.

Hue cache ownership:

- Runtime cache: `<workdir>/cache/name2hue.tsv`.
- Fixed configured hue tables remain authoritative.
- Unknown categories use cached values first, then deterministic SHA-256 hue
  buckets.

ViralQC dataset ownership:

- `viralqc.datasets_dir` has highest precedence.
- `$VIRALQC_DATASETS_DIR` is next.
- The bundled `viralQC/datasets/` submodule path is the fallback.
- Dataset provenance is fingerprinted by path, file count, sizes, mtimes, and a
  metadata hash instead of hashing every large database file.

## Resource Quotas

`flexpipe-run --cores N` is the external quota for one build run. Snakemake caps
rule threads to this value. CPU-heavy rules derive tool thread counts from
Snakemake `{threads}` rather than directly from `options.threads`.

Current thread-aware rules include:

- ViralQC
- MAFFT alignment through `augur align`
- IQ-TREE
- TreeTime refine

Concurrent build policy:

- `flexpipe-run` creates `<workdir>/.flexpipe.lock`.
- A second process targeting the same workdir exits with code `2`.
- Different workdirs may run concurrently, subject to scheduler quotas.

## Network And Retry Policy

Pathoplexus requests retry transient HTTP 429, HTTP 5xx, timeout, and connection
errors with backoff. Nominatim geocoding observes a conservative request delay
and retries rate-limit failures. NCBI fetch uses Entrez history and retry loops
for transient read/network errors.

Schedulers should retry complete failed runs only when the manifest status and
logs indicate a transient upstream/network failure. Configuration, validation,
empty data, malformed ViralQC output, and boundary failures should not be
retried without changing inputs.

## Credentials And Environment

Supported environment variables:

- `PPX_AUTH_TOKEN`: optional Pathoplexus bearer token.
- `NCBI_EMAIL`: required for `data_source: ncbi` unless `ncbi.email` is set.
- `NCBI_API_KEY`: optional NCBI API key.
- `VIRALQC_DATASETS_DIR`: optional ViralQC dataset directory.

NCBI runs no longer fall back to a placeholder email. Use a real contact email
for unattended operation.

## Logs, Status, And Exit Codes

Exit codes:

- `0`: success
- `1`: pipeline or boundary failure
- `2`: configuration, preflight, or workdir lock failure

Manifest status values:

- `success`
- `ingest_failed`
- `boundary_failed`
- `phylo_failed`

Important manifest fields:

- `run_id`, `run_date`, `build_name`, `config_hash`
- `status`, `stage`, `cores`, `elapsed_seconds`
- `counts`
- `tool_versions`
- `resolved_config_digest`
- `resolved_inputs`
- `resolved_artifacts`
- `git`
- `viralqc`

Logs are written to `<workdir>/logs/ingest.log` and
`<workdir>/logs/phylo.log`.

## Data Use Terms

Pathoplexus `dataUseTerms` is preserved through ingest and renamed to
`data_use` during curation. The pipeline normalizes values to uppercase for
display and filtering, and it includes `data_use` in color generation when
configured. A service must surface these terms to downstream users rather than
silently dropping or hiding them.

## Fail Fast Versus Warn

Fail fast:

- Invalid config enums, unsafe column-list strings, bad run dates
- Missing explicit override paths
- Enabled local sequences with missing files
- `data_source: ncbi` without `ncbi.email` or `NCBI_EMAIL`
- Zero merged FASTA records before ViralQC
- ViralQC result file missing required `seqName`
- Ingest to phylo boundary schema or minimum-sequence failures
- Concurrent run on the same workdir

Warn and continue:

- Missing optional geocoding results after retries
- Unknown color categories assigned deterministic hues
- Missing optional force-coordinate file when not configured
- Direct Snakemake runs without `run_date`, which retain legacy unbounded
  behavior
