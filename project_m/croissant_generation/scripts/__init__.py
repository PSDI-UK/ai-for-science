"""
Project M Croissant Generation Scripts
=====================================

This package contains the core pipeline scripts used to generate
MLCommons Croissant metadata for Project M datasets.

Modules
-------

MLTask_csvgen
    Generates task-specific CSV datasets from the PSDI API.

MLTask_build_croissant_from_dcat
    Creates the base Croissant metadata file and populates it using DCAT metadata.

MLTask_apply_user_inputs_to_croissant
    Applies task-specific user inputs such as descriptions, distributions,
    and manual recordSets.

MLTask_build_croissant_recordsets
    Generates Croissant RecordSet definitions from tabular dataset files.

MLTask_compute_croissant_distribution_fields
    Computes derived distribution fields such as file size, encoding format,
    content URL, and SHA256 hash.

createCroissant_run
    Runs the full Croissant generation pipeline end-to-end.

Notes
-----
All scripts are designed to be configuration-driven using a task-specific
`MLTask_config.json` file. Paths are resolved relative to the location of
the config file, allowing reuse across multiple tasks (e.g. MLTask1a, MLTask1b, MLTask2).
"""
