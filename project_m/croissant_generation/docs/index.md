# Project M Croissant Generation

This documentation describes the scripts and workflow used to generate MLCommons Croissant metadata for Project M machine learning tasks.

## What this project does

The pipeline creates Croissant metadata files by combining:

- a base Croissant template
- PSDI DCAT metadata
- task-specific user inputs
- dataset field definitions
- computed file properties

## Main outputs

Typical outputs include:

- `project_m_datafile.csv`
- `MLTaskX_croissantMetadata.json`

## Main pipeline stages

1. Generate task CSV from PSDI API
2. Create base Croissant metadata file
3. Populate fields from DCAT
4. Apply task-specific user inputs
5. Build Croissant recordSets from tabular files
6. Compute file metadata such as SHA256 and content size

See the other pages for details.