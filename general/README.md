# General
## About
This directory contains programs used across the AI for science project. These tools provide generic functionality such as Invenio upload verification, metadata enrichment, and repository maintenance, supporting pipelines elsewhere in the project.

**General – [Tools](tools/) Summary:**  
This module provides a collection of reusable functions for interacting with an Invenio repository and interacting with croissant files. It includes utilities for verifying uploaded files, performing ChEBI lookups to enrich metadata, and detecting or removing duplicate files within an Invenio record or bucket. These tools are designed to be generic building blocks that can be reused across multiple ingestion or curation workflows.

**General – [Invenio record upload](invenio_record_upload/) Summary:**  
This script handles the creation of new Invenio records and the upload of associated files. It prepares metadata payloads, attaches local files, validates upload completion, and finalises draft records. The workflow provides a minimal, adaptable foundation for automating dataset ingestion into an Invenio repository, supporting consistent and repeatable automatic upload process.
