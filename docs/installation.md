# Installation

## Clone the Repository

Clone flexpipe with the viralQC submodule:

```bash
git clone --recurse-submodules https://github.com/InstitutoTodosPelaSaude/flexpipe.git
cd flexpipe
```

If you've already cloned without `--recurse-submodules`, initialize the submodule:

```bash
git submodule update --init --recursive
```

## Set Up the Conda Environment

Install conda dependencies. Choose one:

- **Flexible (recommended for development)**: accepts compatible newer versions
  ```bash
  conda env create -f config/nextstrain.yml
  ```

- **Pinned (recommended for production/scheduled runs)**: reproducible versions
  ```bash
  conda env create -f config/nextstrain.lock.yml
  ```

Activate the environment:

```bash
conda activate nextstrain
```

## Install flexpipe Package

Install flexpipe in editable mode with development and testing extras:

```bash
pip install -e '.[test,dev]'
```

## Set Up ViralQC

Install the bundled ViralQC submodule (creates env, downloads datasets, runs tests):

```bash
bash scripts/install_viralqc.sh
```

## Environment Variables

Several API keys and paths can be configured via environment variables:

| Variable | Purpose | Required? |
|----------|---------|-----------|
| `NCBI_EMAIL` | Email for NCBI API requests | For NCBI mode |
| `NCBI_API_KEY` | API key for higher NCBI rate limits | Optional (Entrez email sufficient) |
| `VIRALQC_DATASETS_DIR` | Path to ViralQC datasets | Optional (auto-discovered) |
| `PPX_AUTH_TOKEN` | Authentication for private Pathoplexus instances | If applicable |

```{warning}
Never commit API keys, tokens, or credentials. Store them in your shell profile or a local `.env` file (ignored by git).
```

## Verify Installation

Check that the CLI tools are available:

```bash
flexpipe-run --help
```

Optionally, run the test suite to verify everything is working:

```bash
pytest -q
```

## ViralQC Datasets

The ViralQC integration requires genome datasets. The resolution order is:

1. `viralqc.datasets_dir` in your build config
2. `$VIRALQC_DATASETS_DIR` environment variable
3. Auto-discovered from `viralQC/datasets/` (submodule)

Datasets are large (~5–10 GB). The `install_viralqc.sh` script handles downloading them. If you need to update or add datasets, see the [ViralQC documentation](https://github.com/InstitutoTodosPelaSaude/viralQC).
