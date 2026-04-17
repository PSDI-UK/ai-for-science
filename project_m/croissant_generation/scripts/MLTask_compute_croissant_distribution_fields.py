import hashlib
import json
import mimetypes
from datetime import datetime, timezone
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


def compute_sha256(file_path, chunk_size=1024 * 1024):
    """
    Compute the SHA256 hash of a file.

    Parameters
    ----------
    file_path : str or pathlib.Path
        Path to the file to hash.
    chunk_size : int, optional
        Number of bytes to read per chunk.

    Returns
    -------
    str
        SHA256 hash as a hexadecimal string.
    """
    sha = hashlib.sha256()

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sha.update(chunk)

    return sha.hexdigest()


def guess_encoding_format(file_path):
    """
    Infer the MIME type / encoding format for a file.

    Parameters
    ----------
    file_path : str or pathlib.Path
        Path to the file.

    Returns
    -------
    str
        MIME type string suitable for Croissant `encodingFormat`.
    """
    suffix = file_path.suffix.lower()

    explicit_map = {
        ".csv": "text/csv",
        ".tsv": "text/tab-separated-values",
        ".txt": "text/plain",
        ".json": "application/json",
        ".jsonl": "application/jsonl+json",
        ".gz": "application/gzip",
        ".gzip": "application/gzip",
        ".zip": "application/zip",
        ".tar": "application/x-tar",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".xls": "application/vnd.ms-excel",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".parquet": "application/vnd.apache.parquet"
    }

    if suffix in explicit_map:
        return explicit_map[suffix]

    guessed, _ = mimetypes.guess_type(str(file_path))
    return guessed or "application/octet-stream"


def make_content_url(file_path, base_dir):
    """
    Generate a relative content URL for a distribution file.

    Parameters
    ----------
    file_path : pathlib.Path
        Absolute path to the file.
    base_dir : pathlib.Path
        Base directory for relative path generation.

    Returns
    -------
    str
        Relative Croissant content URL in the form './filename'.
    """
    rel = str(file_path.relative_to(base_dir)).replace("\\", "/")
    return f"./{rel}"


def current_date_published():
    """
    Generate the current publication date in UTC.

    Returns
    -------
    str
        Timestamp formatted for Croissant `datePublished`.
    """
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT00:00:00Z")


def main(config_file=CONFIG_FILE):
    """
    Compute derived distribution fields for the configured Croissant file.

    This step updates each distribution entry with:
    - `contentSize`
    - `contentUrl`
    - `encodingFormat`
    - `sha256`

    It also updates the top-level `datePublished` field.

    """
    config_path = Path(config_file).resolve()
    base_dir = config_path.parent
    config = load_config(config_path)

    croissant_file = (base_dir / config["croissant_output_file"]).resolve()
    croissant_data = load_json_file(croissant_file)

    updated_count = 0
    skipped_count = 0

    for dist in croissant_data.get("distribution", []):
        file_id = str(dist.get("@id", "")).strip()
        filename = str(dist.get("name", "")).strip()

        if not filename:
            print(f"WARNING: Distribution entry has no filename for @id={file_id!r}, skipping")
            skipped_count += 1
            continue

        file_path = (base_dir / filename).resolve()

        if not file_path.exists():
            print(f"WARNING: Distribution file not found, skipping: {file_path}")
            skipped_count += 1
            continue

        dist["contentSize"] = f"{file_path.stat().st_size} B"
        dist["contentUrl"] = make_content_url(file_path, base_dir)
        dist["encodingFormat"] = guess_encoding_format(file_path)
        dist["sha256"] = compute_sha256(file_path)

        updated_count += 1

    croissant_data["datePublished"] = current_date_published()

    save_json_file(croissant_file, croissant_data)

    print(f"Updated computed distribution fields in {croissant_file.name}")
    print(f"Updated: {updated_count} distribution entries")
    print(f"Skipped: {skipped_count} distribution entries")


if __name__ == "__main__":
    main()