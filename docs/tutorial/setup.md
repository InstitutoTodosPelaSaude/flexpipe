# Setup

This chapter guides you through installing flexpipe and verifying that everything works.

## Time Estimate

~5 minutes for installation; ~5 additional minutes if ViralQC datasets need downloading (~2–5 GB).

## Step 1: Clone the Repository

Clone flexpipe with the ViralQC submodule:

```bash
git clone --recurse-submodules https://github.com/InstitutoTodosPelaSaude/flexpipe.git
cd flexpipe
```

## Step 2: Create Conda Environment

Choose one:

**Flexible (development)**: Accepts newer versions of dependencies
```bash
conda env create -f config/nextstrain.yml
```

**Pinned (production)**: Reproducible versions
```bash
conda env create -f config/nextstrain.lock.yml
```

For this tutorial, the flexible install is fine. The environment setup takes ~2–3 minutes.

## Step 3: Activate Environment

```bash
conda activate nextstrain
```

## Step 4: Install flexpipe Package

Install flexpipe in editable mode with dev and test extras:

```bash
pip install -e '.[test,dev]'
```

## Step 5: Set Up ViralQC

This installs the ViralQC submodule environment and downloads genome datasets (~5 GB, takes 5–10 minutes):

```bash
bash scripts/install_viralqc.sh
```

When finished, you should see:
```
ViralQC installation complete.
```

## Step 6: Verify Installation

Check that the main command works:

```bash
flexpipe-run --help
```

You should see the usage message with available flags.

### Optional: Run Tests

Test the installation:

```bash
pytest -q
```

Should report something like:
```
... passed in X.XXs
```

## Step 7: Set NCBI Email (Optional)

If you plan to use NCBI data, set your email:

```bash
export NCBI_EMAIL=your.email@example.com
```

Add this to your shell profile (`~/.bashrc`, `~/.zshrc`) to persist it:

```bash
echo 'export NCBI_EMAIL=your.email@example.com' >> ~/.zshrc
```

## Troubleshooting

### Conda Environment Won't Activate

```bash
conda deactivate
conda activate nextstrain
```

### `flexpipe-run: command not found`

Make sure the nextstrain environment is activated:

```bash
conda activate nextstrain
flexpipe-run --help
```

### ViralQC Installation Fails

Check that the viralQC submodule is present:

```bash
ls viralQC/
```

Should show: `Dockerfile, LICENSE, pyproject.toml, etc.`

If missing, run:

```bash
git submodule update --init --recursive
```

Then retry:

```bash
bash scripts/install_viralqc.sh
```

### Disk Space Issues

ViralQC datasets are large (~5 GB). Check available space:

```bash
df -h ~
```

You need at least 10 GB free for ViralQC + tutorial runs.

## You're Ready!

Once all steps complete, you're set up. Proceed to [First Run](first-run.md).
