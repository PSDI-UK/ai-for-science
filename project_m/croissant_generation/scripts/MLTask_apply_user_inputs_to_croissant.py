import json
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
    - MLTask1a_croissantMetadata.json → MLTask1a

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

    If explicitly defined in config, use that. Otherwise infer the filename
    based on the task prefix.

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


def apply_top_level_user_fields(croissant_data, user_inputs):
    """
    Apply top-level fields from user input into the Croissant metadata.

    Fields such as name, description, and RAI metadata are copied directly.
    Distribution and recordSet are handled separately.

    Parameters
    ----------
    croissant_data : dict
        Existing Croissant metadata.
    user_inputs : dict
        User-provided metadata fields.

    Returns
    -------
    dict
        Updated Croissant metadata.
    """
    for key, value in user_inputs.items():
        if key in {"distribution", "recordSet"}:
            continue
        croissant_data[key] = value
    return croissant_data


def build_distribution_entries(distribution_inputs):
    """
    Build Croissant distribution entries from user input.

    Parameters
    ----------
    distribution_inputs : list[dict]
        List of distribution definitions from user input JSON.

    Returns
    -------
    list[dict]
        List of Croissant FileObject entries.

    Raises
    ------
    ValueError
        If required fields such as '@id' or 'filename' are missing.
    """
    out = []
    for item in distribution_inputs:
        file_id = item.get("@id", "").strip()
        filename = item.get("filename", "").strip()
        description = item.get("description", "").strip()

        if not file_id:
            raise ValueError(f"Missing '@id' in distribution item: {item}")
        if not filename:
            raise ValueError(f"Missing 'filename' in distribution item: {item}")

        out.append({
            "@type": "cr:FileObject",
            "@id": file_id,
            "name": filename,
            "description": description,
            "contentSize": "",
            "contentUrl": "",
            "encodingFormat": "",
            "sha256": ""
        })

    return out


def build_recordset_entries(recordset_inputs):
    """
    Build Croissant RecordSet entries from user input.

    Parameters
    ----------
    recordset_inputs : list[dict]
        List of recordSet definitions from user input JSON.

    Returns
    -------
    list[dict]
        List of validated Croissant RecordSet objects.

    Raises
    ------
    ValueError
        If required fields are missing or incorrectly formatted.
    """
    recordsets = []

    for item in recordset_inputs:
        recordset_id = str(item.get("@id", "")).strip()

        if not recordset_id:
            raise ValueError(f"Missing '@id' in recordSet item: {item}")

        fields = item.get("field", [])
        if not isinstance(fields, list):
            raise ValueError(f"'field' must be a list in recordSet item: {recordset_id}")

        validated_fields = []

        for field in fields:
            field_id = str(field.get("@id", "")).strip()
            if not field_id:
                raise ValueError(f"Missing '@id' in field for recordSet: {recordset_id}")

            field_data_type = field.get("dataType", [])
            if not isinstance(field_data_type, list):
                raise ValueError(
                    f"'dataType' must be a list in field '{field_id}' of recordSet '{recordset_id}'"
                )

            validated_fields.append({
                "@type": field.get("@type", "cr:Field"),
                "@id": field_id,
                "description": str(field.get("description", "")).strip(),
                "dataType": field_data_type
            })

        recordsets.append({
            "@type": item.get("@type", "cr:RecordSet"),
            "@id": recordset_id,
            "description": str(item.get("description", "")).strip(),
            "data": item.get("data", []),
            "dataType": item.get("dataType", ""),
            "key": item.get("key", {}),
            "field": validated_fields
        })

    return recordsets


def main(config_file="MLTask_config.json"):
    """
    Apply user-provided inputs to an existing Croissant metadata file.

    This step updates:
    - Top-level dataset fields (e.g. name, description, RAI fields)
    - Distribution entries (FileObjects)
    - RecordSet definitions (manual additions or overrides)

    The script:
    1. Loads task configuration
    2. Loads the existing Croissant metadata file
    3. Loads user input JSON
    4. Applies updates and merges recordSets
    5. Writes the updated Croissant file

    Notes
    -----
    - Existing recordSets are merged by '@id'
    - User-defined recordSets override existing ones with the same '@id'
    """

    config_path = Path(config_file).resolve()
    base_dir = config_path.parent

    config = load_config((base_dir / CONFIG_FILE).resolve())

    croissant_file = (base_dir / config["croissant_output_file"]).resolve()
    user_inputs_file = resolve_user_inputs_file(config, base_dir)

    croissant_data = load_json_file(croissant_file)
    user_inputs = load_json_file(user_inputs_file)

    croissant_data = apply_top_level_user_fields(croissant_data, user_inputs)

    if "distribution" in user_inputs:
        croissant_data["distribution"] = build_distribution_entries(user_inputs["distribution"])

    if "recordSet" in user_inputs:
        merged = {
            rs.get("@id"): rs
            for rs in croissant_data.get("recordSet", [])
            if rs.get("@id")
        }

        for rs in build_recordset_entries(user_inputs["recordSet"]):
            merged[rs["@id"]] = rs

        croissant_data["recordSet"] = list(merged.values())

    save_json_file(croissant_file, croissant_data)

    print(f"Updated {croissant_file.name} using {user_inputs_file.name}")
    print(f"Distribution entries: {len(croissant_data.get('distribution', []))}")


if __name__ == "__main__":
    main()