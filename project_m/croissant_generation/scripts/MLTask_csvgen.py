import csv
import json
import requests
from pathlib import Path


def load_config(config_file):
    """
    Load the task configuration file.

    Parameters
    ----------
    config_file : str or pathlib.Path
        Path to the configuration JSON.

    Returns
    -------
    dict
        Parsed configuration data.
    """
    with open(config_file, "r", encoding="utf-8") as f:
        return json.load(f)


def deep_get(data, path, default=""):
    """
    Retrieve a nested value using a dot-separated path.
    """
    current = data

    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part, default)
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return default
        else:
            return default

        if current is None:
            return default

    return current


def normalise_value(value):
    """
    Convert extracted values into CSV-friendly format.
    """
    if value is None:
        return ""
    if isinstance(value, list):
        return " | ".join(str(v) for v in value)
    if isinstance(value, bool):
        return str(value)
    return value


def get_headers(config):
    """
    Build HTTP headers for API requests.
    """
    headers = {"Accept": "application/json"}
    if config.get("auth_token"):
        headers["Authorization"] = f"Bearer {config['auth_token']}"
    return headers


def get_first_file_url(record):
    """
    Extract the first file URL from a record.
    """
    entries = record.get("files", {}).get("entries", {})
    if not entries:
        return ""

    first_entry = next(iter(entries.values()))
    links = first_entry.get("links", {})

    return links.get("content", links.get("self", ""))


def extract_value(record, api_path):
    """
    Extract a value using a path or special keyword.
    """
    if api_path == "__first_file_url__":
        return get_first_file_url(record)

    return deep_get(record, api_path, "")


def build_query(config):
    """
    Build PSDI API query string.
    """
    query = config.get("query", "").strip()
    community = config.get("community", "").strip()

    if community:
        community_query = f'parent.communities.entries.slug:"{community}"'
        if query:
            query = f"({query}) AND ({community_query})"
        else:
            query = community_query

    return query


def fetch_record_summaries(config):
    """
    Fetch all summary records (paginated).
    """
    url = config["base_url"].rstrip("/") + config["records_endpoint"]
    query = build_query(config)

    all_summaries = []
    page = 1

    while True:
        params = {
            "q": query,
            "sort": config["sort"],
            "page": page,
            "size": config["page_size"]
        }

        response = requests.get(
            url,
            params=params,
            headers=get_headers(config),
            timeout=config["timeout_seconds"],
            verify=config["verify_ssl"]
        )
        response.raise_for_status()

        data = response.json()
        hits = data.get("hits", {}).get("hits", [])

        if not hits:
            break

        all_summaries.extend(hits)
        print(f"Fetched page {page}: {len(hits)} records")

        if len(hits) < config["page_size"]:
            break

        page += 1

    print(f"Total records fetched: {len(all_summaries)}")
    return all_summaries


def fetch_full_record(config, record_id):
    """
    Fetch full record by ID.
    """
    url = f"{config['base_url'].rstrip('/')}{config['records_endpoint']}/{record_id}"

    response = requests.get(
        url,
        headers=get_headers(config),
        timeout=config["timeout_seconds"],
        verify=config["verify_ssl"]
    )
    response.raise_for_status()

    return response.json()


def fetch_all_full_records(config, summaries):
    """
    Fetch full records for all summaries.
    """
    full_records = []

    for i, summary in enumerate(summaries, start=1):
        record_id = summary.get("id")
        if not record_id:
            continue

        full_records.append(fetch_full_record(config, record_id))

        if i % 25 == 0 or i == len(summaries):
            print(f"Fetched {i}/{len(summaries)} full records")

    return full_records


def generate_csv(records, config, base_dir):
    """
    Generate CSV file from records.
    """
    mapping = config["csv_field_names"]
    output_file = (base_dir / config["output_csv"]).resolve()

    output_columns = list(mapping.keys())

    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=output_columns)
        writer.writeheader()

        for record in records:
            row = {}

            for csv_header, api_path in mapping.items():
                value = extract_value(record, api_path)
                row[csv_header] = normalise_value(value)

            writer.writerow(row)

    print(f"CSV created: {output_file}")


def main(config_file="MLTask_config.json"):
    """
    Generate dataset CSV for a given task.

    Parameters
    ----------
    config_file : str or pathlib.Path
        Path to task-specific config file.

    Usage Example
    --------------
    python MLTask_csvgen.py ../ML_Task1a/MLTask_config.json
    """
    config_path = Path(config_file).resolve()
    base_dir = config_path.parent

    config = load_config(config_path)

    summaries = fetch_record_summaries(config)
    if not summaries:
        print("No summary records found.")
        return

    full_records = fetch_all_full_records(config, summaries)
    if not full_records:
        print("No full records found.")
        return

    generate_csv(full_records, config, base_dir)


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 2:
        main(sys.argv[1])
    else:
        main()