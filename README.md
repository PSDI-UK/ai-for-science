# AI-For-Science

## Table of Contents
1. [About](#About)
2. [Using this project](#Using-this-project)
3. [Documentation](#Documentation)
4. [Links](#Links)

## About
The "AI for Science" PSDI project aims to tackle a key challenge in modern physical sciences research the fact that methods for analyzing and interpreting experimental data have not kept pace with the exponentially increasing volume of data being generated. As experimental techniques and facilities advance, the rate of data production continues to grow, placing pressure on researchers and infrastructure to extract meaningful insights efficiently.

AI and machine learning models can play a key role in pre-experimental screening and experimental steering. These models can use a brief and low-cost initial data collection to plan and steer more resource-consuming workflows. This approach supports high-throughput synthesis and timely characterization of research data.

Working in collaboration with the Physical Sciences Data Infrastructure (PSDI), UCL, and the Ada Lovelace Centre (ALC), this project will make data more Findable, Accessible, Interpretable, and Reusable (FAIR).

This project results from the funding grant [Provision of "AI ready" data: prototyping data pipelines and repositories](https://gtr.ukri.org/projects?ref=UKRI2697), grant application APP84520, award UKRI2697, opportunity OPP1033:EPSRC AI for Science.

## Using this project
This project is currently working with several groups. Each group has its own sections within this repository, explaining any group-specific information.
There is also a general section file in this repository that includes scripts for injecting, extracting, and updating data from the repository and any other information that is not team-specific.

## Documentation
When documentation is created, links to it will be here.

## Code overview
The datasets related to this project are hosted in [AI Ready Datasets](https://data-collections.psdi.ac.uk/communities/ai-ready-datasets). The code in this repository includes code that in time could be gathered into an "AI Ready Datasets" input pipeline:
   * code to create non-aggregated community data collection [Project M Community Data Collections records](https://data-collections.psdi.ac.uk/communities/project-m/records?q=&l=list&p=1&s=10&sort=newest) containing all data in separate records in a consistent format (project_m/metadata_upload)[https://github.com/PSDI-UK/ai-for-science/tree/main/project_m/metadata_upload]
   * code to create aggregated "AI Ready Datasets" community data collection with additional metadata from [Project M Community Data Collections records](https://data-collections.psdi.ac.uk/communities/project-m/records?q=&l=list&p=1&s=10&sort=newest). A reusable, configuration-driven pipeline has been developed to generate MLCommons Croissant metadata for Project M machine learning tasks. The workflow creates task datasets from PSDI Community Data Collections, enriches metadata using the PSDI DCAT catalogue, applies task-specific inputs, generates Croissant RecordSets/Fields, and computes derived distribution metadata such as file size, format, URLs, and SHA256 hashes. The main entry point for running the full workflow is [`project_m/croissant_generation/scripts/createCroissant_run.py`](project_m/croissant_generation/scripts/createCroissant_run.py), with supporting task folders and documentation in [`project_m/croissant_generation/`](project_m/croissant_generation/). Input sources used by the pipeline include the [PSDI DCAT catalogue](https://metadata.psdi.ac.uk/psdi-dcat.jsonld) and [Project M Community Data Collections records](https://data-collections.psdi.ac.uk/communities/project-m/records?q=&l=list&p=1&s=10&sort=newest).
   * code to process NEDF electron diffraction data to create [Single Crystal 3D ED Electron Diffraction Dataset (University of Southampton NCS/NEDF) for Sample Screening](https://data-collections-dev.psdi.ac.uk/communities/ai-ready-datasets/records?q=%22Single%20Crystal%203D%20ED%20Electron%20Diffraction%20Dataset%22&l=list&p=1&s=10&sort=bestmatch)
   * code to spot-check and correct categorisation and annotation of NEDF electron diffraction data [singleCryED_NEDF/quality_adjuster.py](https://github.com/PSDI-UK/ai-for-science/blob/main/singleCryED_NEDF/quality_adjuster.py)
   * code for tools to create and convert croissant and ro-crate files in [general/tools](https://github.com/PSDI-UK/ai-for-science/tree/main/general/tools)

## Links
Links to specific group files:
1. [General](general/)
2. [Project_M](project_m/)
3. [SingleCryED-NEDF](singleCryED_NEDF/)
