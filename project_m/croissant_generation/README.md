# Croissant Metadata Generation - Project M
This document outlines the step-by-step process for generating Croissant metadata files for Project M datasets, following PSDI and MLCommons Croissant standards.
---

## Configuration
All scripts should read from `MLTask_config.json`. This file contains file locations, dataset identifiers, DCAT source, and filenames. It allows the pipeline to be reused across different ML tasks.
---

## Overall Approach
The croissant file is built incrementally in a series of steps:

1. Generate dataset CSV from PSDI Community Data Collections API.
2. Prepare additional task-specific data.
3. Create base Croissant file.
4. Populate DCAT metadata.
5. Apply user-defined inputs.
6. Build recordsets from data files.
7. Compute derived distribution fields.
---
## Inputs and Outputs

### Inputs (same across tasks)
1. croissantConstantsTemplate.json
2. croissantFieldsThatMapToDCAT.csv
3. croissantFieldsThatNeedToBeComputed.txt
4. MLTask_config.json

### Inputs (task-specific)
1. croissantFieldsFromUserInputs_MLTaskX.json
2. datasetFields.json

### Outputs
1. Croissant file: `MLTaskX_croissantMetadata.json`
2. Dataset file: `project_m_datafile.csv`

### Additional files
1. target_mapping.csv
2. yobs_combined.txt
3. MLTaskX_additionalColumns.csv
---

## Step-by-step process

### Step 1: Generate dataset CSV:
The source is the PSDI Community Data Collections API (eg: https://data-collections.psdi.ac.uk/communities/project-m/records). This step fetches records via API and extracts metadata fields and returns `project_m_datafile.csv` as an output.
---

### Step 2: Prepare `MLTaskX_additionalColumns.csv`
This file is eiher provided by the user **OR** generated from the `project_m_datafile.csv`. This depends on the specific ML task. 
As of 17/04/2026, this file is provided by the user and hence the code reflects that.
---

### Step 3: Create the base croissant file
Create `MLTaskX_croissantMetadata.json` by copying the template file which provides the base structure, schema definitions and placeholders.
---

### Step 4: Populate the DCAT Metadata
The source for this comes from https://metadata.psdi.ac.uk/dev/psdi-dcat.jsonld. The configuration used are `id_of_dcat_dataset` and `dcat_file_location`. The process is to find the dataset with matching `@id`, extract required fields and map using `croissantFieldsThatMapToDCAT.csv` which was provided by the user. Some fields require string formatting or flattening such as creators must be converted into:
 ```json
  {
    "@type": "sc:Person",
    "name": "...",
    "url": "..."
  }
```
---

### Step 5: Apply User Inputs
The source is a json file provided by the user such as `croissantFieldsFromUserInputs_MLTaskX.json` which populates dataset name, description, RAI metadata and distribution definitions. Here for example the distributions looks like:
- `project_m_datafile.csv` - main file
- `MLTaskX_additionalColumns.csv` - task file
- `yobs_combined.txt` - additional file
---

### Step 6: Build RecordSets
It uses `dataFields.json` provided by the user. The process of generating the fields include reading each distribution file, detecting which fields exist in each file, match fields to dataset definitions, and generating `cr:Field` entries. Here only tabular files (CSV,TSV) generate recordSets while non-tabular files (eg. `.txt`) does not generate recordSets. 
The field ID format used here is: `<recordset_id>/<normalised_field_name>`. It was generated as lowercase and replacing non-alphanumeric character with `_`.
---

### Step 7: Compute Distribution Fields
It is based on `croissantFieldsThatNeedToBeComputed.txt`. For each file it computes:
- Content Size: file size in bytes.
- Content URL: `./filename`
- Encoding Format: 
| File Type | Format |
|----------------|-----------|
| CSV         | text/csv |
| TXT        | text/plain |
| ZIP        | application/zip |
- SHA256: Hash of file contents.
---

## Validation
### JSON Validation
To validate the JSON, we used JSON Playground and JSONLint.

### Croissant Validation
To validate croissant file, install MLCroissant.
`pip install mlcroissant`

Test it using the following script:
```
ds = mlc.Dataset("MLTaskX_croissantMetadata.json")
metadata = ds.metadata.to_json()

print(f"{metadata['name']}: {metadata['description']}")

for x in ds.records(record_set="default"):
    print(x)
```
---

## Future Improvements
1. Support multiple data sources in Step 1.
2. Automate ingestion into PSDI Community Data Collections.
3. Integrate directly with PSDI API pipelines.
4. Support additional ML Tasks (1b, 2, etc.)
