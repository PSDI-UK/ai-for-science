#!/usr/bin/python3
"""
Module for extracting metadata associated with Zenodo records.

This module reads metadata from CSV, XLSX, and JSON files and maps
the extracted values to Invenio metadata fields.
"""
from .zenodo_pull_files import download_selected_files
import pathlib
import tempfile
import json
import csv
import pandas as pd
import requests
import os

# Fields describing additive metadata present in JSON files
ADDITIVES = [
    "label",
    "chebi url",
    "amino acid type",
    "ChEBI_molecule_class_urls",
    "ChEBI_molecule_class_names",
    "iupac_name_en",
    "formula",
    "mass",
    "canonical_smiles",
    "standard_inchi",
    "standard_inchi_key",
    "name",
    "pI",
    "pKa",
    "pKb",
    "pKc",
]


def cast_csv_type(value: str) -> any:
    """
    Convert a CSV string value into an appropriate Python data type.

    Parameters
    ----------
    value : str
        Raw value read from a CSV cell.

    Returns
    -------
    Any
        Value converted to an appropriate Python type.
    """
    if value is None:
        return None

    value = value.strip()
    if value == "":
        return None

    if (value.startswith("[") and value.endswith("]")) or (
        value.startswith("{") and value.endswith("}")
    ):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass

    if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
        return int(value)

    try:
        return float(value)
    except ValueError:
        pass

    return value


def extract_from_XLS(file_path: pathlib.Path, metadata_input_json: dict, *args) -> dict:
    """
    Extract metadata from an Excel (.xlsx) file.

    Parameters
    ----------
    file_path : pathlib.Path
        Path to the XLSX file containing metadata.
    metadata_input_json : dict
        Mapping describing spreadsheet cell locations and their
        corresponding Invenio metadata fields.
    *args : tuple
        Unused arguments included for dispatcher compatibility.

    Returns
    -------
    dict
        Extracted metadata mapped to Invenio field names.
    """
    linked_field_data = {}

    xlsx_file = pd.read_excel(file_path)

    for metadata_field in metadata_input_json[file_path.name]:
        row_idx, col_idx = map(
            int,
            next(iter(metadata_input_json[file_path.name].keys())).split(","),
        )

        linked_field_data[
            metadata_input_json[file_path.name][metadata_field]
        ] = xlsx_file.iat[row_idx - 1, col_idx - 1]

    return linked_field_data


def extract_from_CSV(file_path: pathlib.Path, metadata_input_json: dict, xye_file_name: str, *args) -> dict:
    """
    Extract metadata from a CSV file.

    Parameters
    ----------
    file_path : pathlib.Path
        Path to the CSV metadata file.
    metadata_input_json : dict
        Mapping between CSV column names and Invenio metadata fields.
    xye_file_name : str
        Name of the XYE data file used to identify
        the dataset and select the corresponding metadata entries.
    *args : tuple
        Unused arguments included for dispatcher compatibility.

    Returns
    -------
    dict
        Extracted metadata mapped to Invenio field names.
    """
    linked_field_data = {}

    with open(file_path, encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)

        for row in reader:
            if row.get("Filename") == xye_file_name:
                for metadata_field in metadata_input_json[file_path.name]:
                    raw_value = row.get(metadata_field)

                    linked_field_data[
                        metadata_input_json[file_path.name][metadata_field]
                    ] = cast_csv_type(raw_value)

                break

    return linked_field_data


def extract_from_JSON(file_path: pathlib.Path, metadata_input_json: dict, xye_file_name: str, temp_dir: str, *args) -> dict:
    """
    Extract metadata from a JSON file.

    Parameters
    ----------
    file_path : pathlib.Path
        Path to the JSON metadata file.
    metadata_input_json : dict
        Mapping between JSON keys and Invenio metadata fields.
    xye_file_name : str
        Name of the XYE data file used to identify
        the dataset and select the corresponding metadata entries.
    temp_dir : str
        Directory of the temp file that has the other zenodo files in
    *args : tuple
        Unused arguments included for dispatcher compatibility.

    Returns
    -------
    dict
        Extracted metadata mapped to Invenio field names.
    """
    linked_field_data = {}
        
    with open(file_path) as file:
        data = json.load(file)

        for metadata_field in metadata_input_json[file_path.name]:
            if metadata_field not in ADDITIVES:
                linked_field_data[
                    metadata_input_json[file_path.name][metadata_field]
                ] = data[metadata_field]
            else:
                linked_field_data = additive_metadata(
                    data,
                    linked_field_data,
                    xye_file_name,
                    temp_dir
                )

    return linked_field_data

def additive_metadata(data: dict,linked_field_data: dict,xye_file_name: str, temp_dir: str) -> dict:
    """
    Populate additive-related metadata fields.

    Parameters
    ----------
    data : dict
        Parsed JSON metadata.
    linked_field_data : dict
        Metadata dictionary currently being populated.
    xye_file_name : str
        Name of the XYE data file used to identify
        the dataset and select the corresponding metadata entries.
    temp_dir : str
        The tempary directory where all the zenodo files are stored

    Returns
    -------
    dict
        Updated metadata dictionary including additive fields.
    """
    additive_metadata = data["Additives"]

    for item in additive_metadata:
        additive = find_additive(xye_file_name, temp_dir)

        if item.get("label") == additive:
            linked_field_data[metadata_field] = item[field]

    return linked_field_data


def find_additive(xye_file_name: str, temp_dir: str):
    """
    Determine which additive corresponds to the specified dataset.

    Parameters
    ----------
    xye_file_name : str
        Name of the XYE data file used to identify
        the dataset and select the corresponding metadata entries.
    temp_dir : str
        The tempary directory where all the zenodo files are stored

    Returns
    -------
    Any
        Additive identifier associated with the dataset.
    """
    with open(
        pathlib.Path(temp_dir)
        / "batch_out_all_info_with_zscores.csv"
    ) as file:
        reader = csv.DictReader(file)

        for row in reader:
            if row.get("Filename") == xye_file_name:
                additive = cast_csv_type(row.get(xye_file_name))
                return additive


def add_misc_data(linked_field_data: dict, filename: str) -> dict:
    """
    Add derived metadata fields required by the Invenio record.

    Parameters
    ----------
    linked_field_data : dict
        Metadata dictionary already populated from source files.
    filename : str
        Name of the XYE data file.

    Returns
    -------
    dict
        Metadata dictionary including derived fields.
    """
    linked_field_data["structure_id"] = filename.removesuffix(".xye")

    if linked_field_data["vaterite_unit_cell_length_a"] is not None:
        linked_field_data["vaterite_phase_present"] = True
    else:
        linked_field_data["vaterite_phase_present"] = False
        del linked_field_data["vaterite_unit_cell_angle_alpha"]
        del linked_field_data["vaterite_unit_cell_angle_beta"]
        del linked_field_data["vaterite_unit_cell_angle_gamma"]

    if linked_field_data["calcite_unit_cell_length_a"] is not None:
        linked_field_data["calcite_phase_present"] = True
    else:
        linked_field_data["calcite_phase_present"] = False
        del linked_field_data["calcite_unit_cell_angle_alpha"]
        del linked_field_data["calcite_unit_cell_angle_beta"]
        del linked_field_data["calcite_unit_cell_angle_gamma"]

    return linked_field_data


def extract_from_zenodo(xye_file_name: str,metadata_fields_json: str,record_id: str, constants_dir: pathlib.Path) -> dict:
    """
    Download Zenodo files and extract metadata from all configured sources.

    Parameters
    ----------
    xye_file_name : str
        Name of the XYE data file used to identify
        the dataset and select the corresponding metadata entries.
    metadata_fields_json : str
        Metadata mapping titles in new repo to names in current files.
    record_id : str
        The Id of the zenodo being refernced
    constants_dir: pathlib.Path
        The file path to where all constants are stored

    Returns
    -------
    dict
        Combined metadata dictionary ready for Invenio ingestion.
    """
    linked_field_data = {}

    with open(metadata_fields_json, "r") as metadata_file:
        metadata = json.load(metadata_file)
        file_names = [file_name for file_name in metadata]

    with tempfile.TemporaryDirectory() as temp_dir:
        download_selected_files(
            record_id,
            ".",
            file_names,
            temp_dir,
        )

        with open(metadata_fields_json, "r") as metadata_file:
            metadata = json.load(metadata_file)

            for file_name in metadata:
                linked_field_data.update(
                    process_file(
                        pathlib.Path(temp_dir) / file_name,
                        metadata,
                        xye_file_name,
                        temp_dir,
                        constants_dir
                    )
                )

    return linked_field_data

def find_file_path(file_name: str, temp_dir: str, constants_dir: pathlib.Path) -> pathlib.Path:
    """
    Search for a file in temp directory first, then constants directory for a spesified file.

    Parameters
    ----------
    file_name : str
        The name of the file being searched for
    temp_dir : str
        The tempary directory where all the zenodo files are stored
    constants_dir : pathlib.Path
        The file path to where all constants are stored

    Returns
    -------
    pathlib.Path
        The file path of the file searched for
    """

    file_name = pathlib.Path(file_name).name

    temp_path = pathlib.Path(temp_dir) / file_name
    if temp_path.exists():
        return temp_path

    const_path = pathlib.Path(constants_dir) / file_name
    if const_path.exists():
        return const_path

    raise FileNotFoundError(
        f"{file_name} not found in:\n"
        f" - {temp_path}\n"
        f" - {const_path}"
    )

def process_file(file_path: pathlib.Path,metadata_fields: dict,xye_file_name: str, temp_dir: str, constants_dir: str) -> dict:
    """
    Dispatch metadata extraction based on file type.

    Parameters
    ----------
    file_path : pathlib.Path
        Path to the metadata file.
    metadata_fields : dict
        Metadata mapping titles in new repo and in current files.
    xye_file_name : str
        Name of the XYE diffraction data file used to identify
        the dataset and select the corresponding metadata entries.
    temp_dir : str
        The tempary directory where all the zenodo files are stored
    constants_dir : pathlib.Path
        The file path to where all constants are stored

    Returns
    -------
    dict
        Extracted metadata from the specified file.
    """
    file_handler = {
        ".csv": extract_from_CSV,
        ".xlsx": extract_from_XLS,
        ".json": extract_from_JSON,
    }
    
    found_file = find_file_path(file_path, temp_dir, constants_dir)

    file_type = found_file.suffix.lower()

    if file_type not in file_handler:
        raise ValueError(f"Unsupported file type: {file_type}")

    linked_data = file_handler[file_type](
        found_file,
        metadata_fields,
        xye_file_name,
        temp_dir
    )

    return linked_data
