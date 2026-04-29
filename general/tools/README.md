# Tools
## About
This module provides a collection of reusable functions for interacting with an Invenio repository and interacting with croissant files. It includes utilities for verifying uploaded files, performing ChEBI lookups to enrich metadata, and detecting or removing duplicate files within an Invenio record or bucket. These tools are designed to be generic building blocks that can be reused across multiple ingestion or curation workflows.

---

**Tools – [ChEBI Lookup](CHEBI_Lookup.py) Summary:**  
This module enriches JSON documents containing an `Additives` list by querying the public ChEBI REST API. For each additive entry, the script extracts ontology relationships (“is a” parent classes), IUPAC names, molecular formula, mass, SMILES, InChI, and related identifiers. It includes robust ID parsing, HTML stripping, retry logic, and safe nested‑value extraction. The output is written to a new `<input>_enriched.json` file.

**Key capabilities include:**
- Parsing ChEBI IDs from URLs or raw numeric input  
- Fetching full ChEBI payloads  
- Extracting class IDs, names, and URLs  
- Cleaning HTML‑tagged fields returned by the API  
- Adding structural chemical descriptors (SMILES, InChI, InChIKey)  
- Producing a fully enriched JSON document for further processing

**What you give it:**  
- A JSON file containing an `Additives` list  
- Each additive must have a ChEBI link or ID  

**Output:**  
- A new file named `<original>_enriched.json`  
- Each additive enriched with:
  - ChEBI class IDs, names, URLs  
  - IUPAC name  
  - Formula, mass  
  - SMILES, InChI, InChIKey  
- Additives that fail enrichment get an error message added  

---

**Tools – [Invenio delete duplicate entries](invinio_delete_dupes.py) Summary:**  
This script scans an Invenio community for records with identical titles and identifies duplicates. It groups all records by title, detects cases where multiple records share the same name, and removes redundant entries while preserving the first instance. Deletion is performed safely by creating and deleting edit drafts of published records, ensuring the repository remains consistent. A `DRY_RUN` mode allows administrators to preview actions before performing destructive operations.

**Key capabilities include:**
- Enumerating all records within a specific Invenio community  
- Grouping records by title to detect duplicates  
- Safe deletion 
- Optional dry‑run mode for non‑destructive inspection  
 
**Variables Inputs:**  
- `INVENIO_URL`: your Invenio instance URL  
- `COMMUNITY_ID`: the community you want to scan  
- `API_TOKEN`: your personal access token  
- `DRY_RUN`: set to `False` to actually delete records  

**Outputs:**  
- A list of duplicate titles to comand line
- For each duplicate group:
  - The record that will be kept  
  - The records that will be deleted  
- If `DRY_RUN = False`, the duplicates are removed from the repository

---

**Tools – [CSV‑to‑Invenio Upload Verification](verify_upload_number.py) Summary:**  
This module validates that all expected files listed in a CSV exist within an Invenio community. It reads a CSV containing a `Filename` column, extracts the expected file list, and compares it against the actual filenames attached to records in the repository. The script reports missing files, present files, and overall upload completeness. The use of this was batch‑upload verification.

**Key capabilities include:**
- Loading expected filenames from a CSV  
- Querying all records in an Invenio community  
- Extracting file entries from each record  
- Comparing expected vs. actual file sets  
- Reporting missing, present, and total file counts  

**Variables inputs:**  
- `INVENIO_URL`: your Invenio instance URL  
- `COMMUNITY_ID`: the community you want to check  
- `API_TOKEN`: your personal access token  
- `CSV_FILE`: the path to the CSV you want to validate  

**Command Line Outputs:**  
- Number of filenames found in the CSV  
- Number of files found in the Invenio community  
- A list of missing files  
- A list of present files  
