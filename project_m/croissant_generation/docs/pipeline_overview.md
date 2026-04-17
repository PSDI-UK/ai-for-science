# Pipeline Overview

The Croissant metadata generation workflow is carried out in stages.

## Step 1: CSV generation

The CSV generator fetches records from the PSDI Community Data Collections API and writes a task-ready CSV file.

Main script:
- `MLTask_csvgen.py`

Main output:
- `project_m_datafile.csv`

## Step 2: Base Croissant file creation and DCAT mapping

The base Croissant file is created from a shared template and then populated using DCAT metadata.

Main script:
- `MLTask_build_croissant_from_dcat.py`

Main inputs:
- `croissantConstantsTemplate.json`
- `croissantFieldsThatMapToDCAT.csv`
- `MLTask_config.json`

## Step 3: Apply task-specific user inputs

Task-specific fields such as descriptions, RAI metadata, distributions, and manual recordSets are applied from a user input JSON file.

Main script:
- `MLTask_apply_user_inputs_to_croissant.py`

## Step 4: Build recordSets

RecordSets are generated for tabular files such as CSV and TSV. Field definitions are matched using `datasetFields.json`.

Main script:
- `MLTask_build_croissant_recordsets.py`

## Step 5: Compute distribution metadata

Derived file properties are calculated and added to the Croissant JSON:

- `contentSize`
- `contentUrl`
- `encodingFormat`
- `sha256`

Main script:
- `MLTask_compute_croissant_distribution_fields.py`

## Step 6: Run the full pipeline

A small runner script executes the full process in order.

Main script:
- `createCroissant_run.py`