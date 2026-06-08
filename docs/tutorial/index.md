# Tutorial

Welcome to the flexpipe tutorial! This guided walkthrough takes you from installation to visualization of results.

## Who This Is For

- **Genomic epidemiologists** new to flexpipe
- **Nextstrain pipeline** users wanting to learn flexpipe's approach
- **Anyone** analyzing viral sequences

## Prerequisites

- Linux or macOS (Windows: WSL2 recommended)
- Conda (Miniforge, Mambaforge, or Anaconda)
- Git
- ~8 GB disk space (for ViralQC datasets)
- ~1–2 hours for the full tutorial

## How This Tutorial Works

Each chapter is self-contained but builds on the previous one:

1. **[Setup](setup.md)** (5 min) — Clone, install conda env, verify installation
2. **[First Run](first-run.md)** (10 min) — Run the YFV Brazil pipeline end-to-end
3. **[Config Walkthrough](config-walkthrough.md)** (15 min) — Edit parameters and re-run affected stages
4. **[Add Pathogen](add-pathogen.md)** (20 min) — Set up a new pathogen build (NCBI or Pathoplexus)
5. **[Local Data](local-data.md)** (10 min) — Analyze your own sequences (bring-your-own data mode)
6. **[Inspect Outputs](inspect-outputs.md)** (10 min) — Explore QC reports, Auspice JSON, manifest

Total: ~70 minutes hands-on experience.

## Quick Links

- [Installation](../installation.md) — detailed install guide
- [Configuration Reference](../configuration.md) — all config keys
- [Troubleshooting](../troubleshooting.md) — solutions for common issues

## Notation

Throughout this tutorial:

- `$VARIABLE` — shell variable or environment variable
- `<workdir>` — your per-run output directory (e.g., `/tmp/yfv-run`)
- `builds/yfv-brazil/` — file path relative to repo root
- `bash` code blocks — copy and paste directly

## Do Setup Once

Read [Setup](setup.md) first and complete it fully. All subsequent chapters assume you've installed flexpipe and can run `flexpipe-run --help`.

Then proceed through chapters in order:

```{toctree}
:maxdepth: 1

setup
first-run
config-walkthrough
add-pathogen
local-data
inspect-outputs
```

## Support

- See [Troubleshooting](../troubleshooting.md) for solutions to common issues
- Check [GitHub Issues](https://github.com/InstitutoTodosPelaSaude/flexpipe/issues) for known problems
- File a new issue if stuck
