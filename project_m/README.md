# Project-M
## About
This is where all progams and files are stored on project-m

**Project M – Metadata Upload Pipeline Summary:**  
This pipeline automates the extraction, transformation, and upload of metadata from Zenodo into an Invenio repository using a configurable mapping system. It retrieves dataset files, loads constant reference files, resolves file locations, and dispatches metadata extraction based on file type before assembling an Invenio‑compatible payload. The workflow supports reusable configuration, and automated draft creation/submission, enabling consistent upload of Project M datasets into Invenio.

**Project M – Croissant Metadata Generation Summary:**  
This workflow generates Croissant metadata files for Project M datasets following PSDI and MLCommons standards, using a staged process that builds the Croissant file from templates, DCAT metadata, user inputs, and dataset‑derived recordsets. It integrates API‑sourced dataset information, computes distribution fields, and validates outputs to produce a complete Croissant metadata file and supporting dataset CSVs, enabling standardised machine‑learning‑ready metadata across multiple ML tasks.
