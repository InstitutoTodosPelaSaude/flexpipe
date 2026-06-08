# Citation

If you use flexpipe in your research, please cite flexpipe and the underlying tools.

## flexpipe

When publishing results generated with flexpipe, please cite:

```
Instituto Todos pela Saúde. flexpipe: A flexible Nextstrain pipeline for genomic 
epidemiology of viral pathogens. https://github.com/InstitutoTodosPelaSaude/flexpipe
```

BibTeX:
```bibtex
@software{flexpipe2024,
  author = {{Instituto Todos pela Saúde}},
  title = {flexpipe: A flexible Nextstrain pipeline for genomic epidemiology of viral pathogens},
  url = {https://github.com/InstitutoTodosPelaSaude/flexpipe},
  year = {2024}
}
```

## Upstream Tools

flexpipe builds on excellent open-source tools. Please also cite:

### Nextstrain & Augur

The phylogenetic workflow uses Augur, the bioinformatics toolkit from Nextstrain:

```
Hadfield J, Megill C, Bell SM, Huddleston J, Potter B, Callender C, Sagulenko P, 
Bedford T, Neher RA. Nextstrain: real-time tracking of pathogen evolution. 
Bioinformatics. 2018 Dec 1;34(23):4121-4123.
```

BibTeX:
```bibtex
@article{hadfield2018nextstrain,
  author = {Hadfield, James and Megill, Colin and Bell, Sidney M and Huddleston, John and Potter, Barney and 
    Callender, Charlton and Sagulenko, Pavel and Bedford, Trevor and Neher, Richard A},
  title = {Nextstrain: real-time tracking of pathogen evolution},
  journal = {Bioinformatics},
  volume = {34},
  number = {23},
  pages = {4121--4123},
  year = {2018},
  publisher = {Oxford University Press}
}
```

### IQ-TREE

Maximum-likelihood phylogenetics:

```
Minh BQ, Schmidt HA, Chernomor O, Schrempf D, Woodhams MD, von Haeseler A, 
Lanfear R. IQ-TREE 2: New models and parallel inference for phylogenetic trees. 
Mol Biol Evol. 2020 May 1;37(5):1530-1534.
```

BibTeX:
```bibtex
@article{minh2020iqtree,
  author = {Minh, Bui Quang and Schmidt, Heiko A and Chernomor, Olga and Schrempf, Dominik and 
    Woodhams, Michael D and von Haeseler, Arndt and Lanfear, Robert},
  title = {IQ-TREE 2: New models and parallel inference for phylogenetic trees},
  journal = {Molecular Biology and Evolution},
  volume = {37},
  number = {5},
  pages = {1530--1534},
  year = {2020},
  publisher = {Oxford University Press}
}
```

### MAFFT

Multiple sequence alignment:

```
Katoh K, Misawa K, Kuma K, Miyata T. MAFFT: a novel method for rapid multiple 
sequence alignment based on fast Fourier transform. Nucleic Acids Res. 2002 Jul 15;30(14):3059-66.
```

BibTeX:
```bibtex
@article{katoh2002mafft,
  author = {Katoh, Kazutaka and Misawa, Kazuho and Kuma, Kei-ichi and Miyata, Takashi},
  title = {MAFFT: a novel method for rapid multiple sequence alignment based on fast Fourier transform},
  journal = {Nucleic Acids Research},
  volume = {30},
  number = {14},
  pages = {3059--3066},
  year = {2002}
}
```

### TreeTime

Temporal calibration of phylogenetic trees:

```
Sagulenko P, Puller V, Neher RA. TreeTime: Maximum-likelihood phylodynamic inference. 
Virus Evol. 2018 Jan 1;4(1):vex042.
```

BibTeX:
```bibtex
@article{sagulenko2018treetime,
  author = {Sagulenko, Pavel and Puller, Vadim and Neher, Richard A},
  title = {TreeTime: Maximum-likelihood phylodynamic inference},
  journal = {Virus Evolution},
  volume = {4},
  number = {1},
  pages = {vex042},
  year = {2018}
}
```

### Nextclade & ViralQC

Viral classification and genome quality control:

**Nextclade**:
```
Aksamentov I, Roemer C, Hodcroft EB, Neher RA. Nextclade: clade assignment, 
mutation calling and quality control for viral genomes. JOSS. 2021;6(67):3773.
```

BibTeX:
```bibtex
@article{aksamentov2021nextclade,
  author = {Aksamentov, Ivan and Roemer, Cornelius and Hodcroft, Emma B and Neher, Richard A},
  title = {Nextclade: clade assignment, mutation calling and quality control for viral genomes},
  journal = {Journal of Open Source Software},
  volume = {6},
  number = {67},
  pages = {3773},
  year = {2021}
}
```

### BLAST

Sequence homology search:

```
Altschul SF, Gish W, Miller W, Myers EW, Lipman DJ. Basic local alignment search tool. 
J Mol Biol. 1990 Oct 5;215(3):403-10.
```

BibTeX:
```bibtex
@article{altschul1990basic,
  author = {Altschul, Stephen F and Gish, Warren and Miller, Webb and Myers, Eugene W and Lipman, David J},
  title = {Basic local alignment search tool},
  journal = {Journal of Molecular Biology},
  volume = {215},
  number = {3},
  pages = {403--410},
  year = {1990}
}
```

### Auspice

Interactive phylogenetic visualization:

```
Hadfield J, Megill C, Bell SM, Huddleston J, Potter B, Callender C, Sagulenko P, 
Bedford T, Neher RA. Nextstrain: real-time tracking of pathogen evolution. 
Bioinformatics. 2018 Dec 1;34(23):4121-4123.
```

(Same as Nextstrain; Auspice is part of the Nextstrain project.)

## Data Sources

Also acknowledge the data sources used:

### Pathoplexus

If using Pathoplexus/LAPIS for sequence data:

```
GlobalHealth Pathoplexus Consortium. Pathoplexus: A global database of 
viral pathogen sequences and metadata. https://pathoplexus.globalhealthgenomics.org/
```

### NCBI

If using NCBI Entrez:

```
National Center for Biotechnology Information. GenBank. 
https://www.ncbi.nlm.nih.gov/genbank/
```

### ViralQC Datasets

Acknowledge the specific datasets used (e.g., Nextclade, ICTV taxonomy).

## Example Acknowledgments Section

Here's how you might structure an acknowledgments section in your paper:

> *We thank Instituto Todos pela Saúde for developing flexpipe, which orchestrates 
> the phylogenetic analysis pipeline. Phylogenetic inference was performed using 
> Augur, IQ-TREE 3, MAFFT, and TreeTime. Sequence alignment and genome quality control 
> were performed using Nextclade and ViralQC. Sequences were retrieved from 
> [Pathoplexus/NCBI/other source]. Interactive visualization was performed using Auspice.

## License

flexpipe is released under the MIT License. See the [LICENSE](https://github.com/InstitutoTodosPelaSaude/flexpipe/blob/main/LICENSE) file for details.
