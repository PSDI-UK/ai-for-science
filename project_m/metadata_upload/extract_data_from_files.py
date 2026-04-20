"""
Module for reading relevent data from zenodo files.
"""
from pathlib import Path
from general import download_selected_files
import tempfile
import json
import csv
import pandas as pd

RECORD_ID = 17631085

#↓↓↓If aditional data about aditives are needed use this variable↓↓↓
ADDITIVES = ["label", "chebi url", "amino acid type", "ChEBI_molecule_class_urls", "ChEBI_molecule_class_names", "iupac_name_en",
            "formula", "mass", "canonical_smiles", "standard_inchi", "standard_inchi_key", "name", "pI", "pKa", "pKb", "pKc"]

def cast_csv_type(value: str) -> any:
    """
    CSV file have no typings so this takes in a String read from the CSV file and changes it to the most reasonable type.

    Parameters
    ----------
    value: str
        The string that will be typed

    Returns
    -------
    Any
        The input casted to its most relevent type
    """
    if value is None:
        return None

    value = value.strip()
    if value == "":
        return None

    lower = value.lower()

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

def extract_from_XLS(xls_dir: Path, linked_field_data: dict) -> dict:
    """
    Extracts all relevent data from a given XLS file.
    
    Parameters
    ----------
    xls_dir: Path
        The path were file with the XLS files are stored
    linked_field_data : Dict
        The dictonary storing all the data linked to the metadata field names in the Invenio.

    Returns
    -------
    Dict
        The dictonary storing all the data linked to the metadata field names in the Invenio updated with the data from the XLS.
    """
    #df = pd.read_excel(Path.cwd() / "constents"  / "calibration_metadata.xlsx") #Using Local
    df = pd.read_excel(Path(xls_dir)  / "calibration_metadata.xlsx")
    row_idx, col_idx = next(iter(XLSX_FIELD_NAMES))
    for field, metadata_field in XLSX_FIELD_NAMES:
        linked_field_data[metadata_field] = df.iat[row_idx-1, col_idx-1]
    return linked_field_data

def extract_from_CSV(csv_dir: Path, linked_field_data: dict, filename: str) -> dict:
    """
    Extracts all relevent data from a given CSV file.

    Parameters
    ----------
    csv_dir: Path
        The path were file with the CSV files are stored
    linked_field_data : Dict
        The dictonary storing all the data linked to the metadata field names in the Invenio.
    filename : String
        The file name that the extracted data needs to be about.

    Returns
    -------
    Dict
        The dictonary storing all the data linked to the metadata field names in the Invenio updated with the data from the CSV.
    String
        The name of the additive linked to this data
    """

    addative = ""
    #with open(Path.cwd() / "constents" / "batch_out_all_info_with_zscores.csv") as file: #Using Local
    with open(Path(csv_dir) / "batch_out_all_info_with_zscores.csv") as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row.get("Filename") == filename:
                for field, metadata_field in CSV_FIELD_NAMES.items():
                    raw_value = row.get(field)
                    linked_field_data[metadata_field] = cast_csv_type(raw_value)
                    if field == "Additive":
                        addative = cast_csv_type(raw_value)
    return linked_field_data, addative
   
def extract_from_CSV2(csv_dir: Path, linked_field_data: dict, filename: str) -> dict:
    """
    Extracts all relevent data from a given CSV file.

    Parameters
    ----------
    csv_dir: Path
        The path were file with the CSV files are stored
    linked_field_data : Dict
        The dictonary storing all the data linked to the metadata field names in the Invenio.
    filename : String
        The file name that the extracted data needs to be about.

    Returns
    -------
    Dict
        The dictonary storing all the data linked to the metadata field names in the Invenio updated with the data from the CSV.
    String
        The name of the additive linked to this data
    """

    addative = ""
    with open(Path.cwd() / "constents" / "project_m_datafile.csv", encoding="utf-8") as file: #Using Local
    #with open(Path(csv_dir) / "batch_out_all_info_with_zscores.csv") as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row.get("Filename") == filename:
                for field, metadata_field in CSV_FIELD_2.items():
                    raw_value = row.get(field)
                    linked_field_data[metadata_field] = cast_csv_type(raw_value)
                    print(raw_value)
                    if field == "Additive":
                        addative = cast_csv_type(raw_value)
    return linked_field_data, addative


def extract_from_JSON(linked_field_data: dict, addative: str) -> dict:
    """
    Extracts all relevent data from a given JSON file.

    Parameters
    ----------
    linked_field_data : Dict
        The dictonary storing all the data linked to the metadata field names in the Invenio.
    addative : String
        The name of the addative linekd to this data

    Returns
    -------
    Dict
        The dictonary storing all the data linked to the metadata field names in the Invenio updated with the data from the JSON.
    """

    with open(Path.cwd() / "constents" /"constants_for_dataset.json") as file:
        data = json.load(file)
        for field, metadata_field in JSON_FIELD_NAMES.items():
            if field not in ADDITIVES: 
                linked_field_data[metadata_field] = data[field]
            else:
                add = data["Additives"]
                for item in add:
                    if item.get("label") == addative:
                        linked_field_data[metadata_field] = item[field]
    return linked_field_data

def add_misc_data(linked_field_data: dict, filename: str) -> dict:
    """
    Adds miscellaneous keys and data that is requiered for the Invenio record but not explicietoly in the files

    Parameters
    ----------
    linked_field_data : Dict
        The dictonary storing all the data linked to the metadata field names in the Invenio.
    filename : String
        The filename all the data colected is assosiated with.

    Returns3
    -------
    Dict
        The dictonary storing all the data linked to the metadata field names in the Invenio updated with the miscellaneous data.
    """
    linked_field_data["structure_id"] = filename.removesuffix(".xye")
    if linked_field_data["vaterite_unit_cell_length_a"] != None:
        linked_field_data["vaterite_phase_present"] = True
    else:
        linked_field_data["vaterite_phase_present"] = False
        del linked_field_data["vaterite_unit_cell_angle_alpha"]
        del linked_field_data["vaterite_unit_cell_angle_beta"]
        del linked_field_data["vaterite_unit_cell_angle_gamma"]
    if linked_field_data["calcite_unit_cell_length_a"] != None:
        linked_field_data["calcite_phase_present"] = True
    else:
        linked_field_data["calcite_phase_present"] = False
        del linked_field_data["calcite_unit_cell_angle_alpha"]
        del linked_field_data["calcite_unit_cell_angle_beta"]
        del linked_field_data["calcite_unit_cell_angle_gamma"]
    return linked_field_data

def extract_from_zenodo(filename: str) -> dict:
    """
    Creates a temport directory to store the Zenodo files and calls functions to extract data
    
    Parameters
    ----------
    filename : String
        The file name of the xye file the data is about.

    Returns
    -------
    Dict
        The dictonary storing all the data linked to the metadata field names in the Invenio
    """
    linked_field_data = dict.fromkeys(list(JSON_FIELD_NAMES.values())+list(XLSX_FIELD_NAMES.values())+list(CSV_FIELD_NAMES.values())+list(CSV_FIELD_2.values()))
    with tempfile.TemporaryDirectory() as temp_dir:
        download_selected_files(RECORD_ID,
                                    ".",
                                    FILE_NAMES,
                                    temp_dir)
        linked_field_data = extract_from_XLS(temp_dir, linked_field_data)
        linked_field_data, addative = extract_from_CSV(temp_dir, linked_field_data, filename)
        linked_field_data = extract_from_JSON(linked_field_data, addative)
        linked_field_data = add_misc_data(linked_field_data, filename)
        linked_field_data, addative = extract_from_CSV2(temp_dir, linked_field_data, filename)
    return linked_field_data


