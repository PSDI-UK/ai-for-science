import csv
import json
import re
import unicodedata
from pathlib import Path

CONFIG_FILE = "MLTask_config.json"


def load_json_file(path):
    """
    Load a JSON file from disk.

    Parameters
    ----------
    path : str or pathlib.Path
        Path to the JSON file.

    Returns
    -------
    dict | list
        Parsed JSON content.
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json_file(path, data):
    """
    Save JSON data to disk.

    Parameters
    ----------
    path : str or pathlib.Path
        Output file path.
    data : dict | list
        JSON-serializable content.
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_config(path):
    """
    Load the task configuration file.

    Parameters
    ----------
    path : str or pathlib.Path
        Path to the configuration JSON.

    Returns
    -------
    dict
        Parsed configuration data.
    """
    return load_json_file(path)


def infer_task_prefix_from_output(output_file):
    """
    Infer the task prefix from the Croissant output filename.

    For example:
    - MLTask1a_croissantMetadata.json -> MLTask1a

    Parameters
    ----------
    output_file : str
        Name of the Croissant output file.

    Returns
    -------
    str
        Inferred task prefix.
    """
    suffix = "_croissantMetadata.json"
    return output_file[:-len(suffix)] if output_file.endswith(suffix) else Path(output_file).stem


def resolve_user_inputs_file(config, base_dir):
    """
    Resolve the path to the user input JSON file.

    If explicitly defined in config, that path is used.
    Otherwise, the filename is inferred from the task prefix.

    Parameters
    ----------
    config : dict
        Task configuration.
    base_dir : pathlib.Path
        Base directory for resolving relative paths.

    Returns
    -------
    pathlib.Path
        Absolute path to the user inputs JSON file.
    """
    explicit = config.get("croissant_user_inputs_file")
    if explicit:
        return (base_dir / explicit).resolve()

    task_prefix = infer_task_prefix_from_output(config["croissant_output_file"])
    return (base_dir / f"croissantFieldsFromUserInputs_{task_prefix}.json").resolve()


def normalise_id_part(text):
    """
    Normalise a label for use in a Croissant field or recordSet ID.

    Parameters
    ----------
    text : str
        Input label or identifier fragment.

    Returns
    -------
    str
        Normalised identifier component.
    """
    text = str(text).strip()
    text = unicodedata.normalize("NFKD", text).replace("–", "-").replace("—", "-").lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def make_field_id(recordset_id, label):
    """
    Construct a Croissant field ID.

    Parameters
    ----------
    recordset_id : str
        Parent recordSet identifier.
    label : str
        Field label.

    Returns
    -------
    str
        Field ID in the format '<recordset_id>/<normalised_field_name>'.
    """
    return f"{recordset_id}/{normalise_id_part(label)}"


def get_recordset_id(file_id):
    """
    Map a distribution file ID to its Croissant recordSet ID.

    Parameters
    ----------
    file_id : str
        Distribution file identifier.

    Returns
    -------
    str
        RecordSet identifier.
    """
    return "main_file_recordset" if file_id == "main_file" else f"{file_id}_recordset"


def get_recordset_name(filename):
    """
    Generate a recordSet name from a filename.

    Parameters
    ----------
    filename : str
        Name of the data file.

    Returns
    -------
    str
        RecordSet name based on the file stem.
    """
    return f"{Path(filename).stem}_recordset"


def normalise_for_matching(text):
    """
    Normalise text for field-name matching.

    This is used to compare dataset field definitions to actual CSV headers
    in a tolerant way.

    Parameters
    ----------
    text : str
        Input text to normalise.

    Returns
    -------
    str
        Normalised text suitable for matching.
    """
    text = str(text).strip()
    text = unicodedata.normalize("NFKD", text).replace("–", "-").replace("—", "-").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def build_field_lookup(dataset_fields):
    """
    Build a lookup table from dataset field definitions.

    The lookup supports a number of aliases so that fields in CSV headers
    can still match definitions in datasetFields.json even when naming
    conventions differ slightly.

    Parameters
    ----------
    dataset_fields : list[dict]
        Field definitions loaded from datasetFields.json.

    Returns
    -------
    dict
        Mapping of normalised field names and aliases to field definitions.
    """
    lookup = {}
    extra_aliases = {
        "Excluded (True/False)": [
            "Excluded (yes/no)",
            "Excluded yes/no",
            "Excluded_yes_no"
        ],
        "ML Task Target": ["Annotation"],
        "Degree of Crystallinity": [
            "degree_of_crystallinity",
            "Degree_of_Crystallinity"
        ],
    }

    for field_def in dataset_fields:
        name = field_def.get("name", "")
        if not name:
            continue

        aliases = {
            name,
            name.replace(" ", "_"),
            name.replace("–", "-"),
            name.replace("-", " "),
            name.replace("–", " "),
            name.replace(" URL", "URL").replace(" url", "url"),
            name.replace("(R_wp)", "R_wp"),
            name.replace("(COOH group)", "COOH group"),
            name.replace("(NH2 group)", "NH2 group"),
            name.replace("(other group)", "other group")
        }

        aliases.update(extra_aliases.get(name, []))

        for alias in aliases:
            lookup[normalise_for_matching(alias)] = field_def

    return lookup


def get_matching_field_definition(header, field_lookup):
    """
    Look up a dataset field definition for a CSV header.

    Parameters
    ----------
    header : str
        Column header from a tabular file.
    field_lookup : dict
        Lookup table produced by build_field_lookup().

    Returns
    -------
    dict | None
        Matching field definition if found, otherwise None.
    """
    return field_lookup.get(normalise_for_matching(header))


def read_tabular_headers(file_path):
    """
    Read the header row from a tabular file.

    Supports automatic delimiter detection for comma-, tab-, and
    semicolon-delimited files.

    Parameters
    ----------
    file_path : str or pathlib.Path
        Path to the tabular file.

    Returns
    -------
    list[str]
        List of cleaned column headers.
    """
    with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = ","

        reader = csv.reader(f, delimiter=delimiter)
        headers = next(reader, [])

    return [str(h).strip() for h in headers if str(h).strip()]


def is_tabular_file(filename):
    """
    Determine whether a file should generate a Croissant recordSet.

    Parameters
    ----------
    filename : str
        File name to check.

    Returns
    -------
    bool
        True for CSV or TSV files, otherwise False.
    """
    return Path(filename).suffix.lower() in {".csv", ".tsv"}


def normalise_key_fields(key_value):
    """
    Normalise recordSet key field definitions into a list.

    Parameters
    ----------
    key_value : str | list[str] | None
        Key field definition from the user input JSON.

    Returns
    -------
    list[str]
        List of cleaned key field names.
    """
    if not key_value:
        return []

    return [str(v).strip() for v in key_value] if isinstance(key_value, list) else [str(key_value).strip()]


def make_croissant_field(file_id, recordset_id, column_name, field_def):
    """
    Build a Croissant field object from a known dataset field definition.

    Parameters
    ----------
    file_id : str
        Distribution file identifier.
    recordset_id : str
        Parent recordSet identifier.
    column_name : str
        Column name from the tabular file.
    field_def : dict
        Matching field definition from datasetFields.json.

    Returns
    -------
    dict
        Croissant field object.
    """
    return {
        "@type": "cr:Field",
        "@id": make_field_id(recordset_id, column_name),
        "name": field_def.get("name", column_name),
        "description": field_def.get("description", ""),
        "dataType": field_def.get("dataType", []),
        "source": {
            "fileObject": {"@id": file_id},
            "extract": {"column": column_name}
        }
    }


def make_fallback_field(file_id, recordset_id, column_name):
    """
    Build a fallback Croissant field object when no dataset definition matches.

    Parameters
    ----------
    file_id : str
        Distribution file identifier.
    recordset_id : str
        Parent recordSet identifier.
    column_name : str
        Column name from the tabular file.

    Returns
    -------
    dict
        Croissant field object with minimal metadata.
    """
    return {
        "@type": "cr:Field",
        "@id": make_field_id(recordset_id, column_name),
        "name": column_name,
        "description": "",
        "dataType": [],
        "source": {
            "fileObject": {"@id": file_id},
            "extract": {"column": column_name}
        }
    }


def build_recordset_key_block(recordset_id, key_fields):
    """
    Build the Croissant key block for a recordSet.

    Parameters
    ----------
    recordset_id : str
        RecordSet identifier.
    key_fields : list[str]
        List of key field names.

    Returns
    -------
    dict | list[dict] | None
        Single key reference, multiple key references, or None if no keys exist.
    """
    key_ids = [make_field_id(recordset_id, key_field) for key_field in key_fields]

    if not key_ids:
        return None

    return {"@id": key_ids[0]} if len(key_ids) == 1 else [{"@id": key_id} for key_id in key_ids]


def build_recordset_for_distribution(distribution_item, field_lookup, base_dir):
    """
    Build a Croissant recordSet for a distribution file.

    This function:
    - resolves the file path
    - skips missing files
    - skips non-tabular files
    - reads headers from tabular files
    - matches headers to known dataset field definitions
    - generates Croissant field objects

    Parameters
    ----------
    distribution_item : dict
        Distribution definition from the user input JSON.
    field_lookup : dict
        Lookup table from normalised field names to dataset field definitions.
    base_dir : pathlib.Path
        Base directory used to resolve file paths.

    Returns
    -------
    dict | None
        Generated recordSet object, or None if the file should not produce one.
    """
    file_id = distribution_item.get("@id", "").strip()
    filename = distribution_item.get("filename", "").strip()
    description = distribution_item.get("description", "").strip()
    key_fields = normalise_key_fields(distribution_item.get("recordset/key", []))

    recordset_id = get_recordset_id(file_id)
    recordset = {
        "@type": "cr:RecordSet",
        "@id": recordset_id,
        "name": get_recordset_name(filename),
        "description": description
    }

    key_block = build_recordset_key_block(recordset_id, key_fields)
    if key_block is not None:
        recordset["key"] = key_block

    file_path = (base_dir / filename).resolve()

    if not file_path.exists():
        print(f"WARNING: Skipping missing file: {file_path}")
        return None

    if not is_tabular_file(filename):
        print(f"{filename}: non-tabular file, skipping recordSet")
        return None

    headers = read_tabular_headers(file_path)

    fields = []
    matched_count = 0
    fallback_count = 0

    for header in headers:
        field_def = get_matching_field_definition(header, field_lookup)

        if field_def:
            fields.append(make_croissant_field(file_id, recordset_id, header, field_def))
            matched_count += 1
        else:
            fields.append(make_fallback_field(file_id, recordset_id, header))
            fallback_count += 1

    recordset["field"] = fields
    print(f"{filename}: matched {matched_count}, fallback {fallback_count}")
    return recordset


def main(config_file=CONFIG_FILE):
    """
    Generate Croissant recordSet definitions for the configured task.

    This step:
    1. Loads task configuration
    2. Resolves user input and dataset field definition files
    3. Builds recordSets for all tabular distribution files
    4. Skips non-tabular files such as text files
    5. Replaces previously generated recordSets
    6. Saves the updated Croissant metadata file

    Notes
    -----
    Existing generated recordSets with IDs such as:
    - default
    - main_file_recordset
    - task_file_recordset
    - additional_file_recordset

    are removed before regenerated recordSets are merged in.
    """
    config_path = Path(config_file).resolve()
    base_dir = config_path.parent
    config = load_config(config_path)

    croissant_file = (base_dir / config["croissant_output_file"]).resolve()
    user_inputs_file = resolve_user_inputs_file(config, base_dir)
    dataset_fields_file = (base_dir / "datasetFields.json").resolve()

    croissant_data = load_json_file(croissant_file)
    user_inputs = load_json_file(user_inputs_file)
    dataset_fields = load_json_file(dataset_fields_file)

    field_lookup = build_field_lookup(dataset_fields)

    generated = []
    for distribution_item in user_inputs.get("distribution", []):
        recordset = build_recordset_for_distribution(distribution_item, field_lookup, base_dir)
        if recordset is not None:
            generated.append(recordset)

    generated_ids_to_replace = {
        "default",
        "main_file_recordset",
        "task_file_recordset",
        "additional_file_recordset"
    }

    merged = {
        rs.get("@id"): rs
        for rs in croissant_data.get("recordSet", [])
        if rs.get("@id") and rs.get("@id") not in generated_ids_to_replace
    }

    for rs in generated:
        merged[rs["@id"]] = rs

    croissant_data["recordSet"] = list(merged.values())

    save_json_file(croissant_file, croissant_data)

    print(f"Updated {croissant_file.name}")
    print(f"Generated {len(generated)} recordSet entries")
    print(f"Final total recordSet entries: {len(croissant_data['recordSet'])}")


if __name__ == "__main__":
    main()