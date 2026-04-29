# SingleCryED_NEDF Tools

This repository contains two main components designed to support the evaluation and refinement of 3D Electron Microscopy (3D‑EM) image quality:

1. **`create_metadata_csv.py`** — a preprocessing script that was used to generate a clean, standardised metadata CSV  
2. **`quality_adjuster.py`** — an interactive tool for manually reviewing image quality, validating automated predictions, and refining threshold boundaries

The Quality Adjuster is the primary tool in this project, while the metadata script ensures the input CSV is consistent and ready for use as well as adding any extra data like quality rating.

---

## 1. `create_metadata_csv.py`
### Metadata Cleaner & Enhancer

`create_metadata_csv.py` is a lightweight utility script that prepares your metadata for downstream processing. Its purpose is to take a metadata CSV created from other scripts that create the intial data and produce an **enhanced, standardised version** that avoids common formatting issues and adds extra data that needed pre-procesing like a data quality ranking.

### Key Features

- **Normalises file paths**
  - Converts backslashes (`\`) and forward slashes (`/`) into a consistent format  

- **Standardises column formatting**
  - Normalises column names  

- **General CSV hygiene**
  - Removes blank rows  
  - Ensures consistent datatypes  
  - Reorders or groups columns for readability

- **Adds Extra data that needed processing**
  - Adds Data Quality ranking

---

## 2. `quality_adjuster.py`
### Interactive 3D‑EM Image Quality Labelling Tool

The `quality_adjuster.py` provides a graphical interface for reviewing 3D‑EM images, inspecting metadata, comparing automated predictions, and assigning manual quality labels.

---

### Core Capabilities

#### **Image Viewer**
- Automatic resizing

#### **Metadata Display**
- Shows all relevant metadata fields  
- Updates dynamically as you navigate through images  

#### **Automated Quality Classification**
The tool computes a predicted quality label using two metadata fields:

- `diff_limit`  
- `indexation`

Each is classified independently into:

- **good**  
- **complex**  
- **bad**

The final label uses a **worst‑case rule**, meaning whichever classification field is worse becomes the combined label.

#### **Manual Labelling**
- Buttons for **Good**, **Complex**, **Bad**  
- Keyboard shortcuts:  
  - `1` → good  
  - `2` → complex  
  - `3` → bad  
- Manual labels are saved immediately back into `metadata.csv`  
- Tracks session progress and total labelled count  

#### **Threshold Suggestion Engine**
After at least 5 manual labels, the tool can:

- Compute accuracy  
- Suggest optimal threshold boundaries for:  
  - `diff_limit` → (d1, d2)  
  - `indexation` → (i1, i2)  

This allows you to refine automated classification rules based on real human judgement.

---

### Session Completion

When all unlabeled images have been reviewed, the tool:

- Saves all changes to `metadata.csv`  
- Prints a summary of total manual labels  
- Closes cleanly  

---

## Workflow Summary

1. **Prepare metadata**  
   Run `create_metadata_csv.py` to generate a clean, enhanced CSV.

2. **Launch the Quality Adjuster**  
   Start the GUI to begin reviewing images.

3. **Label images manually**  
   Use the interface to assign quality labels.

4. **Refine thresholds**  
   Use the built‑in suggestion tool to compute optimal classification boundaries.

5. **Export updated metadata**  
   The CSV is updated automatically throughout the session.

---
