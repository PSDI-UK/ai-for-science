import csv
import json
from copy import deepcopy
from pathlib import Path

import requests


CONFIG_FILE = "MLTask_config.json"


def load_config(config_file=CONFIG_FILE):
    """
    Load the task configuration JSON.

    Parameters
    ----------
    config_file : str or pathlib.Path
        Path to the task-specific config JSON.

    Returns
    -------
    dict
        Parsed configuration.
    """
    with open(config_file, "r", encoding="utf-8") as f:
        return json.load(f)


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


def fetch_json_from_url(url, timeout=30, verify_ssl=True):
    """
    Fetch JSON content from a URL.

    Parameters
    ----------
    url : str
        URL to fetch.
    timeout : int, optional
        Request timeout in seconds.
    verify_ssl : bool, optional
        Whether to verify SSL certificates.

    Returns
    -------
    dict | list
        Parsed JSON response.
    """
    response = requests.get(url, timeout=timeout, verify=verify_ssl)
    response.raise_for_status()
    return response.json()


def get_dcat_document(config, base_dir):
    """
    Load the DCAT document from either a URL or a local file.

    Parameters
    ----------
    config : dict
        Task configuration.
    base_dir : pathlib.Path
        Base directory for resolving relative paths.

    Returns
    -------
    dict
        DCAT JSON-LD document.
    """
    location = config["dcat_file_location"]

    if str(location).startswith(("http://", "https://")):
        return fetch_json_from_url(
            location,
            timeout=config.get("timeout_seconds", 30),
            verify_ssl=config.get("verify_ssl", True),
        )

    return load_json_file((base_dir / location).resolve())


def copy_template_to_output(config, base_dir):
    """
    Copy the Croissant template into the configured output file.

    Parameters
    ----------
    config : dict
        Task configuration.
    base_dir : pathlib.Path
        Base directory for resolving relative paths.

    Returns
    -------
    dict
        Newly created Croissant data structure.
    """
    template_file = config.get("croissant_template_file", "croissantConstantsTemplate.json")
    output_file = config["croissant_output_file"]

    template = load_json_file((base_dir / template_file).resolve())
    croissant_data = deepcopy(template)

    if "datePublished" not in croissant_data:
        croissant_data["datePublished"] = ""

    save_json_file((base_dir / output_file).resolve(), croissant_data)
    return croissant_data


def find_dcat_dataset(dcat_doc, target_id):
    """
    Find the DCAT dataset matching the configured @id.

    Parameters
    ----------
    dcat_doc : dict
        DCAT JSON-LD document.
    target_id : str
        Dataset @id to match.

    Returns
    -------
    dict
        Matching dataset block.

    Raises
    ------
    ValueError
        If no matching dataset is found.
    """
    graph = dcat_doc.get("@graph", {})
    catalogs = graph.get("dcat:Catalog", [])

    if isinstance(catalogs, dict):
        catalogs = [catalogs]

    for catalog in catalogs:
        datasets = catalog.get("dcat:Dataset", [])

        if isinstance(datasets, dict):
            datasets = [datasets]

        for dataset in datasets:
            if dataset.get("@id") == target_id:
                return dataset

    raise ValueError(f"Could not find dataset with @id = {target_id}")


def load_mapping_rows(mapping_csv_path):
    """
    Load the Croissant-to-DCAT mapping table.

    Supports comma-, tab-, or semicolon-delimited files.

    Parameters
    ----------
    mapping_csv_path : str or pathlib.Path
        Path to the mapping file.

    Returns
    -------
    list[dict]
        Rows from the mapping file.
    """
    with open(mapping_csv_path, "r", encoding="utf-8-sig", newline="") as f:
        content = f.read()

    if not content.strip():
        raise ValueError(f"Mapping CSV is empty: {mapping_csv_path}")

    sample = content[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","

    lines = [line for line in content.splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"No non-empty lines found in mapping CSV: {mapping_csv_path}")

    reader = csv.DictReader(lines, delimiter=delimiter)
    rows = list(reader)

    if not rows:
        raise ValueError(f"No rows found in mapping CSV: {mapping_csv_path}")

    print("Detected mapping delimiter:", repr(delimiter))
    print("Detected mapping columns:", list(rows[0].keys()))
    return rows


def detect_column_name(row, candidates):
    """
    Detect a column name from a set of possible header variants.

    Parameters
    ----------
    row : dict
        Example row from CSV DictReader.
    candidates : list[str]
        Candidate header names.

    Returns
    -------
    str
        Actual matching header name.
    """
    def norm(text):
        return " ".join(str(text).strip().lower().replace("_", " ").split())

    normalised = {norm(k): k for k in row.keys() if k is not None}

    for candidate in candidates:
        key = norm(candidate)
        if key in normalised:
            return normalised[key]

    raise ValueError(
        f"Could not find any of these columns: {candidates}. "
        f"Found columns: {list(row.keys())}"
    )


def extract_text(value):
    """
    Flatten a DCAT/JSON-LD value into text where appropriate.

    Parameters
    ----------
    value : any
        Input value from DCAT JSON-LD.

    Returns
    -------
    str
        Flattened text representation.
    """
    if value is None:
        return ""

    if isinstance(value, str):
        return value

    if isinstance(value, list):
        parts = []
        for item in value:
            text = extract_text(item)
            if text:
                parts.append(text)
        return "; ".join(parts)

    if isinstance(value, dict):
        for key in ("@value", "foaf:name", "name", "rdfs:label", "skos:prefLabel"):
            if key in value:
                return extract_text(value[key])

        if "@id" in value:
            return str(value["@id"])

        return json.dumps(value, ensure_ascii=False)

    return str(value)


def normalise_creator_value(value):
    """
    Convert DCAT creator entries into Croissant/schema.org creator objects.

    Parameters
    ----------
    value : list | dict | str
        DCAT creator field.

    Returns
    -------
    list[dict]
        Croissant creator objects.
    """
    if value is None:
        return []

    if not isinstance(value, list):
        value = [value]

    creators = []

    for item in value:
        if isinstance(item, dict):
            creator = {"@type": "sc:Person"}

            name = item.get("foaf:name") or item.get("name") or item.get("rdfs:label")
            if name:
                creator["name"] = name

            url = item.get("@id") or item.get("url")
            if url:
                creator["url"] = url

            if "name" in creator:
                creators.append(creator)

        elif isinstance(item, str):
            creators.append({
                "@type": "sc:Person",
                "name": item
            })

    return creators


def normalise_further_information(value):
    """
    Convert psdiDcatExt:furtherInformation into Croissant citeAs format.

    Parameters
    ----------
    value : list | dict | str
        Further information field from DCAT.

    Returns
    -------
    str
        BibTeX-like citation block.
    """
    if value is None:
        return ""

    if not isinstance(value, list):
        value = [value]

    entries = []

    for i, item in enumerate(value, start=1):
        if isinstance(item, dict):
            title = (
                item.get("title")
                or item.get("dcterms:title")
                or item.get("name")
                or item.get("rdfs:label")
                or ""
            )

            url = (
                item.get("url")
                or item.get("@id")
                or item.get("dcat:landingPage")
                or ""
            )

            if isinstance(url, dict):
                url = url.get("@id", "")

            if title and url:
                entries.append(
                    f"@Article{{furtherInformation{i},title = '{title}', url='{url}'}}"
                )
            elif title:
                entries.append(
                    f"@Article{{furtherInformation{i},title = '{title}'}}"
                )

        elif isinstance(item, str):
            entries.append(
                f"@Article{{furtherInformation{i},title = '{item}'}}"
            )

    return "\n\n".join(entries)


def normalise_dcat_value(dcat_field_name, value):
    """
    Convert a DCAT field value into the appropriate Croissant-compatible format.

    Parameters
    ----------
    dcat_field_name : str
        DCAT field name.
    value : any
        Raw value from DCAT dataset.

    Returns
    -------
    any
        Normalised value for Croissant JSON.
    """
    if value is None:
        return ""

    if dcat_field_name == "psdiDcatExt:furtherInformation":
        return normalise_further_information(value)

    if dcat_field_name == "dcterms:creator":
        return normalise_creator_value(value)

    if dcat_field_name == "dcterms:license":
        return extract_text(value)

    if dcat_field_name == "dcat:landingPage":
        if isinstance(value, dict):
            return value.get("@id", "")
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and "@id" in item:
                    return item["@id"]
                if isinstance(item, str):
                    return item
            return ""
        return str(value)

    if dcat_field_name in {"dcat:version", "dcterms:issued"}:
        return extract_text(value)

    return extract_text(value)


def apply_dcat_mapping(croissant_data, dcat_dataset, mapping_rows):
    """
    Apply DCAT-to-Croissant field mappings.

    Parameters
    ----------
    croissant_data : dict
        Current Croissant JSON structure.
    dcat_dataset : dict
        Matched DCAT dataset.
    mapping_rows : list[dict]
        Mapping rows from the CSV/TSV file.

    Returns
    -------
    dict
        Updated Croissant data.
    """
    first_row = mapping_rows[0]

    croissant_col = detect_column_name(
        first_row,
        ["croissant field name", "croissant_field_name", "croissant field", "croissant_field"]
    )
    dcat_col = detect_column_name(
        first_row,
        ["DCAT field name", "dcat field name", "dcat_field_name", "dcat field", "dcat_field"]
    )

    for row in mapping_rows:
        croissant_field = (row.get(croissant_col) or "").strip()
        dcat_field = (row.get(dcat_col) or "").strip()

        if not croissant_field or not dcat_field:
            continue

        raw_value = dcat_dataset.get(dcat_field, "")
        croissant_data[croissant_field] = normalise_dcat_value(dcat_field, raw_value)

    return croissant_data


def main(config_file=CONFIG_FILE):
    """
    Build the Croissant metadata file using the DCAT mapping step.

    Parameters
    ----------
    config_file : str or pathlib.Path, optional
        Path to the task-specific configuration file.
    """
    config_path = Path(config_file).resolve()
    base_dir = config_path.parent

    config = load_config(config_path)

    copy_template_to_output(config, base_dir)

    output_path = (base_dir / config["croissant_output_file"]).resolve()
    croissant_data = load_json_file(output_path)

    dcat_doc = get_dcat_document(config, base_dir)
    dcat_dataset = find_dcat_dataset(dcat_doc, config["id_of_dcat_dataset"])
    mapping_rows = load_mapping_rows((base_dir / config["croissant_dcat_mapping_csv"]).resolve())

    croissant_data = apply_dcat_mapping(croissant_data, dcat_dataset, mapping_rows)
    save_json_file(output_path, croissant_data)

    print(f"Created/updated: {output_path}")
    print(f"Matched dataset: {config['id_of_dcat_dataset']}")


if __name__ == "__main__":
    main()