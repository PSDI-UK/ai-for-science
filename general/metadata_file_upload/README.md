# Metadata File Upload Module
The `metadata_file_upload` package provides a toolkit for extracting metadata from scientific files, transforming that metadata into Invenio compatible json, and publishing records to Invenio. Currently the metadata is gotten from a Zenodo repositories but as long as the data is extracted and put in a dictonary format the origin repositiry should not matter.
## Features
- Extract metadata from a variaty of file types automaticaly
- Convert Python dictionaries into valid Invenio metadata json
- Upload files and metadata to an Invenio instance
- Accept and publish records automaticaly
- Publish records into communitys
- Pull files and metadata from Zenodo repos
- Components can be used independently or as a full pipeline (see, [Progect M](/project_m/metadata_upload/upload_script.py))
## Module Breakdown
### extract_data_from_files.py
Handles metadata extraction from local files.
- Reads input files (JSON) that parses metadata fields such as title, description, authors, timestamps
  JSON file is organised as { "filename": { "name in current file": "name in Invenio" } }
- Extracted values from files and inputs into a Python dictionary under Invenios expected name for the value.
- Handles missing or malformed metadata
- Supports batch extraction
- Outputs a dictionary where the key is the Invenio field and the value is the value from the file
#### Requirements
- file path to JSON file that is organised as { "filename": { "name in current file": "name in Invenio" } }
- File path to where data is stored
### dict_to_invenio_schema.py
Converts a Python dictionary into a valid Invenio metadata schema.
- The dictionary keys are the Invenio field
- Validating required fields (title, creators, resource_type)
- Auto‑generating missing required fields when possible
- Reporting invalid or incomplete metadata
Output is a JSON Invenio metadata object.
#### Requirements
- Dictionary of all the metadata where the key is the name of the Invenio field
### invenio_accept_publish.py
Manages the upload and publication lifecycle of a record in an Invenio instance.
- Creating a draft record
- Uploading file content
- Finalising the draft
- Publishing the record
- Handling authentication and API errors
- Returning the final record ID or URL
#### Requirements
- Invenio URL
- Invenio access key
- Invenio metadata payload
### invenio_comunit_and_publish.py
Handles community‑related operations in Invenio.
- Assigning records to communities
- Publishing records into communities
- Validating community IDs and permissions
#### Requirements
- Invenio URL
- Invenio access key
- Invenio community name and ID
### zenodo_pull_files.py
Integrates with Zenodo’s REST API to retrieve existing deposits.
- Downloading all files for a Zenodo deposit ID
- Fetching deposit metadata
- Saving files locally (suggested in temp file)
- Returning other metadata
#### Requirements
- Zenodo ID
- Directory to save files
