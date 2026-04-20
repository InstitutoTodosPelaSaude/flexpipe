# flexpipe
Flexible nextstrain pipeline for genomic epidemiology of pathogens.

This repository contains the essential files to create a [nextstrain build](https://nextstrain.org/). By using this pipeline users can to perform genomic epidemiology analyses and visualize phylogeographic results to track pathogen spread using genomic data and their associated metadata.

![alt text](https://github.com/InstitutoTodosPelaSaude/flexpipe/blob/main/overview.png)
Nextstrain panel with results overview

## Getting started
<!--- 
### For Windows users

Native Linux and Mac Users are all set, and can move on to step #2. Windows users, however, must install a Linux subsystem before being able to install nextstrain. Visit [this website](https://docs.nextstrain.org/en/latest/install.html) and follow its step-by-step guide about how to [setup Linux on Windows](https://docs.microsoft.com/en-us/windows/wsl/install-win10) (please choose 'Ubuntu 18.04 LTS or superior versions'), and how to launch Linux and [create a user account and password](https://learn.microsoft.com/en-us/shows/one-dev-minute/how-do-i-configure-a-wsl-distro-to-launch-in-the-home-directory-in-windows-terminal--one-dev-questio) using command line.
-->
### Learning basic UNIX commands

Familiarize yourself with basic UNIX commands for navigating and managing files and folders in a command line interface ("Terminal"). In this platform you can perform all simple tasks you usually do using mouse clicks: to copy, move, delete, access, and create files and folders. All you need to do is to type a few commands. Below you can find the main commands required to operate in a Terminal. Please access [this page](https://commons.wikimedia.org/wiki/File:Unix_command_cheatsheet.pdf) to learn a few more commands. Please practice the use of the commands listed below, so that you are able to navigate from/to directories ("folders") and manage files and folders in command line interfaces.

Creating, Moving and Deleting | Navigating directories | Checking content
------------ | ------------- | -------------
**mkdir** folderX → *create folderX* | **cd** folderX → *move into folderX* | **ls** → *list files and folders*
**mv** → *move files/folder from/to another directory* | **cd ..** → *go back to previous folder* | **head** → *see the first 10 lines of a file*
**rm** → *delete files/folders from a directory* | **pwd** → *check you current directory* | **tail** → *see the last 10 lines of a file*

<!--- 
### Installing nextstrain

If you need to install nexstrain in your computer, please [click here](https://github.com/InstitutoTodosPelaSaude/flexpipe/blob/master/nextstrain_installation.pdf) to download the guidelines to install it. That document provides instructions on how to install `augur` (bioinformatics pipeline) and `auspice` (visualization tool). For more information about the installation process, visit this [nextstrain page](https://docs.nextstrain.org/en/latest/install.html).
-->

### Creating a nextstrain build
[Click here](https://github.com/InstitutoTodosPelaSaude/flexpipe/blob/master/nextstrain_tutorial.pdf) to download a tutorial with a step-by-step tutorial on how to prepare your working directory (files and folders), run `augur`, and visualize the results with `auspice`. Please check [this webiste](https://neherlab.org/201910_RIVM_nextstrain.html) for more information about the distinct functionalities of nextstrain.

## FAQs


### 1. A checkpoint issue during the `rule tree` prevents the flexpipe run to progress. How do I solve that?

If the workflow is executed and it fails to complete the `rule tree`, the previously created files will not allow `iqtree` to resume a new run. As a result, you may see an error message like this:

```
Checkpoint (results/alignments/masked.fasta.ckp.gz) indicates that a previous run successfully finished
Use `--redo` option if you really want to redo the analysis and overwrite all output files.
Use `--redo-tree` option if you want to restore ModelFinder and only redo tree search.
Use `--undo` option if you want to continue previous run when changing/adding options.
```

To resume the run and solve that issue you need to explicitly asks `iqtree` to `-redo` the phylogenetic inference. To do so, add an argument `--redo` argument in the `iqtree` command line in `rule tree`:

```
iqtree \
	-s {input.alignment} \
	-bb {params.bootstrap} \
	-nt {params.threads} \
	-m {params.model} \
	--redo
```
---

### 2. Why does `rule refine` display the message "ERROR: unsupported rooting mechanisms or root not found"?

This error is mostly likely caused by missing root genome(s). For example, if the phylogeny has to be rooted based on the branch leading to the genome 'JF912185', such genome must be listed among the ones in `config/keep.txt`. If the rooting genomes are not included in that file, they will not be included in the alignment, and this error message will be prompted:

```
augur refine is using TreeTime version 0.9.4
0.82        TreeTime.reroot: with method or node: JF912185

ERROR: unsupported rooting mechanisms or root not found
```

'JF912185' is a Yellow Fever Virus (YFV) genome. If you are not running a YFV analysis, you need to add an appropriate genome in `config/keep.txt`, and also change the [root genome(s)](https://github.com/InstitutoTodosPelaSaude/flexpipe/blob/main/Snakefile#L39) listed in `rule parameters` of the Snakefile:

```
rule parameters:
	params:
		mask_5prime = 142,
		mask_3prime = 548,
		bootstrap = 1, # default = 1, but ideally it should be >= 100
		model = "GTR",
		
		root = "JF912185", # <<< set one or more genomes to root the phylogeny
		
		clock_rate = 0.0003,
		clock_std_dev = 0.0001,
```
---

### 3. How does the hierarchical colour system work in flexpipe?

The `colour_maker.py` script allows you to define colours for categories and subcategories in a hierarchical way. You only need to manually define the hue for the **top-level categories**, and the script automatically generates gradient shades for the lower levels.

**Practical example:**
- Level 1 (category): `continent` → you define the hue (e.g. blue for Europe)
- Level 2 (subcategory): `country` → the script automatically generates blue shades for each European country

**Columns in the metadata**

The metadata must have **one column per hierarchical level** you want to colour. For example:

| continent | country |
|-----------|---------|
| Europe | France |
| Europe | Germany |
| Americas | Brazil |

**The `name2hue.tsv` file (colour scheme)**

You need to create a TSV file with **only the top-level categories** and their corresponding hues. Hues are numbers from 0 to 350 (colour wheel) or matplotlib colormap names (e.g. `Blues_r`).

```tsv
category	hue
Europe	210
Americas	120
Asia	30
Africa	50
Oceania	270
```

> **Tip:** Hues follow the colour wheel in increments of 10 (0 = red, 120 = green, 210 = blue, 270 = purple, etc.).

**Configuring `colour_maker.py` in a rule in the Snakefile**

The correct approach is to set the column groups in the `params` of the `colours` rule, **not directly in `--levels`** inside the shell block. This keeps the shell commands clean and makes the configuration easier to maintain.

**Recommended structure**

```python
rule colours:
    message:
        """
        Assigning colour scheme for defined columns in {input.matrix}
        """
    input:
        matrix = rules.process_metadata.output.final_metadata,
        scheme = files.colscheme,
    params:
        host = "host_type host",              # top level → lower level
        geo  = "region division location",    # top → mid → lower level
    output:
        colours1      = temp("config/col_hosts.tsv"),
        colours2      = temp("config/col_geo.tsv"),
        colour_scheme = "config/colour_scheme.tsv",
    shell:
        """
        python scripts/colour_maker.py \
            --input {input.matrix} \
            --colours {input.scheme} \
            --levels {params.host} \
            --output {output.colours1}

        python scripts/colour_maker.py \
            --input {input.matrix} \
            --colours {input.scheme} \
            --levels {params.geo} \
            --output {output.colours2}

        python scripts/multi_merger.py \
            --path "./config" \
            --regex "col_*" \
            --columns "field, value, hex_color" \
            --output {output.colour_scheme}
        """
```

**What each param means**

| Param | Example value | Interpretation |
|-------|--------------|----------------|
| `host` | `"host_type host"` | `host_type` is the top level (e.g. *human*, *avian*); `host` is the actual species |
| `geo` | `"region division location"` | `region` → `division` → `location`, from broadest to most specific |

> **Rule:** The **first column** in each param must be the one with entries defined in `name2hue.tsv`. The remaining columns receive derived colours automatically.

**Other use case examples**

Any pair (or trio) of hierarchical columns works the same way:

```python
params:
    lineage = "lineage_major lineage_minor"
    geo     = "continent country"
    clade   = "clade subclade variant"
```

**Summary workflow**

```
metadata.tsv             name2hue.tsv
(with hierarchical   →   (hues for top-level
 columns)                 categories only)
        ↓
   colour_maker.py --levels [top_col] [lower_col]
        ↓
  col_*.tsv (temporary files per group)
        ↓
   multi_merger.py
        ↓
  colour_scheme.tsv  ← used by Auspice/Nextstrain
```

## Author

* **Anderson Brito, Instituto Todos pela Saúde (ITpS)** - [Website](https://www.itps.org.br/membros) - anderson.brito@itps.org.br

## License

This project is licensed under the MIT License.
