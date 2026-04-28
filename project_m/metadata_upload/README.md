# Metadata Upload Pipeline — Project M

This document outlines the step-by-step process for generating and uploading metadata records for **Project M datasets** into an **Invenio repository**, using metadata extracted from Zenodo records and locally defined mappings.

---

## Configuration

All execution is controlled through configuration variables defined inside:

`project_m/metadata_upload/upload_script.py`

The script requires the following variables to be configured before execution:

INVENIO_URL = "URL OF INVENIO INSTANCE"  
TOKEN = "INVENIO API TOKEN"  
ZENODO_RECORD_ID = "ZENODO RECORD ID NUMBER"  
METADATA_JSON = "PATH TO METADATA MAPPING JSON"  
CONSTENTS_DIR = "DIRECTORY CONTAINING CONSTANT FILES"

These variables allow the workflow to be reused across datasets and repositories.

---

## Overall Approach

The metadata upload workflow operates as a staged pipeline:

1. Create metadata mapping definition.  
2. Retrieve dataset files from Zenodo.  
3. Download required constant files.  
4. Resolve file locations automatically.  
5. Extract metadata based on file type.  
6. Build Invenio payloads.  
7. Submit records to the configured Invenio instance.

---

## Inputs and Outputs

### Inputs (Common Across Runs)

- metadata_mapping.json
- Invenio repository (via API)
- Zenodo Record (via API) 

### Metadata Mapping File

Create a JSON file describing how metadata fields map between existing files and the Invenio API schema.

Example:

{
  "filename": {
    "name in current file": "name in zenodo api"
  }
}

This mapping controls how extracted metadata populates repository records.
There is an example in `project_m/metadata_upload/metadata_fields.json`

## Step-by-Step Process

### Step 1 — Load Metadata Mapping

The script loads the user-provided metadata mapping JSON specified by METADATA_JSON.  
This file defines how metadata fields are translated into the Invenio schema.

---

### Step 2 — Retrieve Zenodo Record Files

Using ZENODO_RECORD_ID, the pipeline:

- queries the Zenodo API  
- lists available files  
- downloads datasets into a temporary working directory  

---

### Step 3 — Load Constant Files

Some metadata requires reference datasets or predefined values.

The script checks:

- Temporary download directory  
- CONSTENTS_DIR  

before raising missing-file errors.

Examples:

- constants_for_dataset.json  
- project_m_datafile.csv  
---

### Step 4 — Find File Locations

Each metadata file is resolved automatically:

- temp directory → preferred  
- constants dir → fallback  

This allows workflows to work whether files are downloaded dynamically or stored locally.

---

### Step 5 — Dispatch Metadata Extraction

Metadata extraction is performed based on file type.

Supported formats:

- .csv → extract_from_CSV  
- .xlsx → extract_from_XLS  
- .json → extract_from_JSON  

The correct extractor automatically is uesed automaticaly.

---

### Step 6 — Build Invenio Payload

Extracted metadata fields are combined into an Invenio-compatible payload including:

- dataset spisific metadata  
- creators  
- titles  

---

### Step 7 — Upload to Invenio

The script authenticates using TOKEN and submits payloads to INVENIO_URL.

Operations performed:

- create or update drafts  
- attach metadata  
- submit records  

---

## Running the Script

Navigate in to the home working directory (ai-for-science/):

run: python -m project_m.metadata_upload.upload_script

