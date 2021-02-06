[![CI](https://github.com/NBISweden/BLR/workflows/CI/badge.svg?branch=master)](https://github.com/NBISweden/BLR/actions?query=branch%3Amaster)

:exclamation:**NB! This is currently under heavy development.**:exclamation:

# Barcode-Linked Reads Analysis

- [About the pipeline](#About-the-pipeline)
- [Usage](#Usage)
- [One-time installation](#One-time-installation)
- [Development](#development)
- [Old version](#Old-version)

## About the pipeline

The BLR pipeline is end-to-end Snakemake workflow for whole genome haplotyping
 and structural variant calling from FASTQs. It was originally developed for the
prep-processing of data for the paper 
[High throughput barcoding method for genome-scale phasing](https://www.nature.com/articles/s41598-019-54446-x) 
for input into the 10x LongRanger pipeline (see [Old version](#Old-version
)) but have since been
 heavily
modified to run completely independant of LongRanger. The pipeline also
allowes for inputting FASTQs from other linked-read technologies such as: 
10x Genomics Chromium Genome, Universal Sequencing TELL-seq and MGI
stLFR. Read more about the integrated linked-read platforms 
[here](doc/platforms.rst)

## Usage

- [1. Setup analysis](#1-setup-an-analysis-folder)
- [2. Run analysis](#2-running-an-analysis)
- [3. MultiQC plugin](#3-multiqc-plugin)

### 1. Setup an analysis folder

Activate your Conda environment.

    conda activate blr

Create the analysis directory using `blr init`. Choose a name for the
 analysis, `output_folder` in this example. Specify the library type using
  the `-l` flag, here we choose `blr`.

    blr init --reads1=path/to/sample.R1.fastq.gz -l blr path/to/output_folder

Note that BLR expects paired-end reads. However, only the path to the R1 file
needs to be provided. The R2 file will be found automatically.

Move into your newly created analysis folder.

    cd path/to/output_folder

Then, you may need to edit the configuration file `blr.yaml`, in
particular to enter the path to your reference genome. 

    blr config --set genome_reference path/to/GRCh38.fasta

To see what other configurations can be altered, read the documentation in the `blr.yaml` file or run `blr config` to print the current configs to the terminal.

### 2. Running an analysis

Change working directory to your analysis folder

    cd path/to/output_folder

The pipeline it launched using the `blr run` command. To automatically runs all steps run: 

    blr run

For more options, see the documentation.

    blr run -h

### 3. MultiQC plugin

There is a MultiQC plugin included in the BLR pipeline called 
MultiQC_BLR. If you wish to run MultiQC without this plugin include 
`--disable-blr-plugin` in your multiqc command. 

The plugin allows for comparison between different runs. In this case go to 
the directory containing the folders for the runs you wish to compare. Then run:

    multiqc -d .
    
The `-d` option prepends the directory name to each sample allowing differentiation 
between the runs. 

## One-time installation

- [1. Setup Conda](#1-prerequisite-conda)
- [2. Install BLR](#2-install-blr)
- [3. Optional installations](#3-optional-installations)

### 1. Prerequisite: Conda

Install [miniconda](https://docs.conda.io/en/latest/miniconda.html). You could 
also try copy-pasting the following to your terminal. This will download 
miniconda, install it to you `$HOME` folder.

    if [[ $OSTYPE = "linux-gnu" ]]; then 
        wget http://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh
    elif [[ $OSTYPE = "darwin"* ]]; then 
        wget https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh -O miniconda.sh
    fi
    bash miniconda.sh -b -p $HOME/miniconda
    source $HOME/miniconda/etc/profile.d/conda.sh

Enable the [bioconda channel](http://bioconda.github.io/)

    conda config --add channels bioconda

### 2. Install BLR

Clone the git repository.

      git clone https://github.com/FrickTobias/BLR.git

Create & activate a new Conda environment, in which all dependencies will be 
installed.

      conda env create -n blr -f environment.yml
      conda activate blr

Install blr into the environment in "editable install" mode.

      pip install -e .

This will install blr in such a way that you can still modify the source code
and get any changes immediately without re-installing.

### 3. Optional installations

#### 3.1 DeepVariant

To enable [DeepVariant](https://github.com/google/deepvariant), install it
 separately to your environment. Note that it is currently only available for
  linux. 

    conda activate blr
    conda install deepvariant

To use DeepVariant for variant calling in your analysis, run:
   
    blr config --set variant_caller deepvariant    

#### 3.2 Lariat aligner

To use [lariat](https://github.com/10XGenomics/lariat) for alignment you need to manually install it within your 
environment. For help on installation see [the following instructions](doc
/lariat_install.rst). To enable mapping using lariat, run:

    blr config --set read_mapper lariat

#### 3.3 NAIBR

The latest version of the [NAIBR repo](https://github.com/raphael-group/NAIBR
) will be downloaded and used automatically. If you want to use another
 version of NAIBR this can be set through:
 
    blr config --set naibr_path /path/to/NAIBR/

## Development

Issues are tracked through https://github.com/FrickTobias/BLR/issues. For
 more information on development go [here](doc/develop.rst).

## Old version

To run the analysis described in [High throughput barcoding method for genome-scale phasing](https://www.nature.com/articles/s41598-019-54446-x),
look at the [stable branch](https://github.com/FrickTobias/BLR/tree/stable) for this git repository.

That version of BLR Analysis is also available at [OMICtools](https://omictools.com/blr-tool).
