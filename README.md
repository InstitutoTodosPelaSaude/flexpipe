# flexpipe
Flexible nextstrain pipeline for genomic epidemiology of pathogens.


# Nextstrain course

This repository contains the essential files to create a [nextstrain build](https://nextstrain.org/). By using this pipeline users can to perform genomic epidemiology analyses and visualize phylogeographic results to track pathogen spread using genomic data and their associated metadata.


## Getting started

### 1. For Windows users

Native Linux and Mac Users are all set, and can move on to step #2. Windows users, however, must install a Linux subsystem before being able to install nextstrain. Visit [this website](https://docs.nextstrain.org/en/latest/install.html) and follow its step-by-step guide about how to [setup Linux on Windows](https://docs.microsoft.com/en-us/windows/wsl/install-win10) (please choose 'Ubuntu 18.04 LTS or superior versions'), and how to launch Linux and [create a user account and password](https://learn.microsoft.com/en-us/shows/one-dev-minute/how-do-i-configure-a-wsl-distro-to-launch-in-the-home-directory-in-windows-terminal--one-dev-questio) using command line.

### 2. Learning basic UNIX commands

Familiarize yourself with basic UNIX commands for navigating and managing files and folders in a command line interface ("Terminal"). In this platform you can perform all simple tasks you usually do using mouse clicks: to copy, move, delete, access, and create files and folders. All you need to do is to type a few commands. Below you can find the main commands required to operate in a Terminal. Please access [this page](https://commons.wikimedia.org/wiki/File:Unix_command_cheatsheet.pdf) to learn a few more commands. Please practice the use of the commands listed below, so that you are able to navigate from/to directories ("folders") and manage files and folders in command line interfaces.

Creating, Moving and Deleting | Navigating directories | Checking content
------------ | ------------- | -------------
**mkdir** folderX → *create folderX* | **cd** folderX → *move into folderX* | **ls** → *list files and folders*
**mv** → *move files/folder from/to another directory* | **cd ..** → *go back to previous folder* | **head** → *see the first 10 lines of a file*
**rm** → *delete files/folders from a directory* | **pwd** → *check you current directory* | **tail** → *see the last 10 lines of a file*

### 3. Installing nextstrain

If you need to install nexstrain in your computer, please [click here](https://github.com/InstitutoTodosPelaSaude/flexpipe/blob/master/nextstrain_installation.pdf) to download the guidelines to install it. That document provides instructions on how to install `augur` (bioinformatics pipeline) and `auspice` (visualization tool). For more information about the installation process, visit this [nextstrain page](https://docs.nextstrain.org/en/latest/install.html).


### 4. Creating a nextstrain build
[Click here](https://github.com/InstitutoTodosPelaSaude/flexpipe/blob/master/nextstrain_tutorial.pdf) to download the course handout with a step-by-step tutorial on how to prepare your working directory (files and folders), run `augur`, and visualize the results with `auspice`. Please check [this webiste](https://neherlab.org/201910_RIVM_nextstrain.html) for more information about the distinct functionalities of nextstrain.

## Author

* **Anderson Brito, Instituto Todos pela Saúde (ITpS)** - [Website](https://www.itps.org.br/membros) - anderson.brito@itps.org.br

## License

This project is licensed under the MIT License.
