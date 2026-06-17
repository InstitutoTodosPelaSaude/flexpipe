# Developer Guide

This guide covers testing, linting, and documentation for flexpipe contributors.

## Testing

### Unit Tests

Run unit tests (excludes integration and network tests):

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=flexpipe
```

### Integration Tests

Integration tests run actual Snakemake workflows on small datasets:

```bash
pytest -m integration
```

These require the nextstrain conda environment and Snakemake to be available. They execute dry-run (`--dry-run`) wiring tests to verify that rules are correctly orchestrated.

### Running Specific Tests

Test a single file:
```bash
pytest tests/unit/test_config.py
```

Test a specific function:
```bash
pytest tests/unit/test_config.py::test_load_config
```

Test integration for a specific build:
```bash
pytest -m integration -k "denv3"
```

### Integration Coverage for New Builds

Integration tests automatically discover `builds/*/config.yaml`. Add the build
directory and config, then run:

```bash
pytest -m integration -k "my-pathogen"
```

This will run a dry-run (`--dry-run`) of both ingest and phylo Snakefiles for your build, verifying configuration and rule wiring without executing expensive computations.

## Code Quality

### Linting

Check code with ruff:

```bash
ruff check .
```

Fix auto-fixable issues:

```bash
ruff check . --fix
```

### Formatting

Check code formatting with black:

```bash
black --check .
```

Auto-format code:

```bash
black .
```

### Type Checking

Run mypy:

```bash
mypy flexpipe/
```

## Building Documentation

Documentation is built with Sphinx and hosted on Read the Docs.

### Local Build

Install documentation dependencies:

```bash
pip install -r docs/requirements.in
```

Build locally:

```bash
cd docs
make html
```

Or use Sphinx directly:

```bash
sphinx-build -b html . _build/html
```

### Strict Build (All Warnings Fatal)

For CI/pre-commit checks:

```bash
sphinx-build -b html -W . _build/html
```

The `-W` flag treats warnings as errors.

### View Locally

Open `docs/_build/html/index.html` in a browser.

## Code Structure

```
flexpipe/
  config.py              # Configuration models (Pydantic)
  paths.py               # Workdir path constants
  manifest.py            # Run provenance
  run.py                 # Orchestrator (flexpipe-run)
  cli.py                 # Console script dispatch
  io.py                  # File I/O utilities
  ingest/
    pathoplexus.py       # Pathoplexus fetch
    ncbi.py              # NCBI Entrez fetch
    merge.py             # Local sequence merge
  curate/
    pipeline.py          # Main curation orchestrator
    dates.py             # Date normalization
    qc_summary.py        # QC statistics
    regions.py           # Geographic assignment
    hosts.py             # Host assignment
    clades.py            # Clade truncation
    columns.py           # Column operations
    viralqc_join.py      # ViralQC integration
  geo/
    coordinates.py       # Nominatim geocoding
    cache.py             # Coordinate caching
  colors/
    hues.py              # Hue assignment
    scheme.py            # Color scheme generation
  phylo/
    traits.py            # Trait collapse
    reference_mask.py    # BED mask generation
  data/
    regions/             # Geographic mappings
    colors/              # Color hue presets
    geo/                 # Coordinate cache seed
    viralqc/             # ViralQC aliases
    phylo/               # Masking profiles
```

## Key Concepts

### Configuration Resolution

The `FlexpipeConfig` Pydantic model (in `config.py`) validates all build config keys at load time. Runtime overrides (e.g., ViralQC dataset paths from env vars) are applied by `write_snakemake_config_overrides()` before Snakemake invocation.

### Workdir Paths

All output paths are computed by `WorkdirPaths` (in `paths.py`). Build config never specifies workdir paths; they're always derived from the workdir location.

### Snakemake Config Injection

`flexpipe-run` writes a merged config to `<workdir>/config/snakemake_resolved.yaml` and passes it to Snakemake as the single `--configfile`. This avoids Snakemake's quirk where only the last `--configfile` is used when multiple are passed.

### ViralQC Dataset Resolution

Order of resolution:
1. `viralqc.datasets_dir` (config)
2. `$VIRALQC_DATASETS_DIR` (env var)
3. `viralQC/datasets/` (submodule; auto-discovered)

Implemented in `flexpipe/config.py` during Pydantic validation.

## Validation Utilities

### flexpipe-validate-build

Validates a build config without running the pipeline:

```bash
flexpipe-validate-build builds/my-pathogen/config.yaml
```

Checks:
- Config syntax and types
- Required files (reference, clades, etc.)
- Data source prerequisites (taxid for NCBI, etc.)

Useful for pre-flight checks before adding a new pathogen.

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make changes and test:
   ```bash
   ruff check . && black . && mypy flexpipe/ && pytest
   ```
4. Update docs if needed: `cd docs && make html`
5. Commit with a clear message
6. Push and open a pull request

## Common Development Tasks

### Add a New CLI Command

1. Add entry point in `pyproject.toml` under `[project.scripts]`
2. Implement function in appropriate module (e.g., `flexpipe/curate/new_feature.py`)
3. Dispatch from `flexpipe/cli.py`
4. Test: `pytest tests/unit/test_cli.py`
5. Document in [commands.md](commands.md)

### Add a New Config Section

1. Define Pydantic model in `flexpipe/config.py`
2. Add to `FlexpipeConfig` class
3. Update docs: [configuration.md](configuration.md)
4. Add unit test in `tests/unit/test_config.py`

### Add a New Ingest Rule

1. Add rule to `ingest/Snakefile`
2. Reference in pipeline docs: [pipeline/ingest.md](pipeline/ingest.md)
3. Add to [commands.md](commands.md) if it's user-facing
4. Test with: `pytest -m integration`

## References

- [Snakemake documentation](https://snakemake.readthedocs.io/)
- [Augur documentation](https://docs.nextstrain.org/projects/augur/en/stable/)
- [Auspice documentation](https://docs.nextstrain.org/projects/auspice/en/latest/)
- [Pydantic documentation](https://docs.pydantic.dev/)
