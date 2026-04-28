#!/usr/bin/env python3
"""
Module for getting files from zenodo.
"""
import requests
import os

ZENODO_BASE_URL = "https://zenodo.org/api/records/"

def get_record_metadata(record_id: str):
    """
    Retrieve metadata for a Zenodo record's metadata.
    Parameters
    ----------
    record_id : str
        string of numbers that is the zenodo's record ID. 
    Retrurns
    --------
    json
        The metadata fo the record in a json format.
    """
    print("HTTPS_PROXY:", os.environ.get("HTTPS_PROXY"))
    url = f"{ZENODO_BASE_URL}{record_id}"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def download_file(file_info: str, output_dir: str ="."):
    """
    Download a single file from Zenodo.
    
    Parameters
    ----------
    file_info : str
        File info for the file gotten from the zenodo metadata file
    output_dir : str, optional
        Directory for the files to be stored in. Default is '.'.
    """
    download_url = file_info["links"]["self"]
    filename = file_info["key"]
    filepath = os.path.join(output_dir, filename)

    print(f"Downloading: {filename}")
    response = requests.get(download_url, stream=True, timeout=300)
    response.raise_for_status()

    with open(filepath, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"Saved to {filepath}")


def download_selected_files(record_id: str, match_extensions: list[str] = ".", match_names: list[str] = ".", output_dir: str = "."):
    """
    Setup for downloading selected files from a Zenodo record.
    Paramiters
    ----------
        
    record_id : str
        string of numbers that is the zenodo's record ID.
    match_extensions : list[str], optional
        List of file extensions that are needing needing to be downloaded. Default is '.'.
    match_names : list[str], optional
        List for file names that are needing to be downloaded. Default is '.'.
    output_dir : str, optional
        Directory for the files to be stored in. Default is '.'.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    metadata = get_record_metadata(record_id)
    files = metadata.get("files", [])

    print(f"Found {len(files)} files in record {record_id}")
    for f in files:
        filename = f["key"]

        # Match by extension
        if match_extensions and any(filename.endswith(ext) for ext in match_extensions):
            download_file(f, output_dir)
            continue

        # Match by partial filename
        if match_names and any(name in filename for name in match_names):
            download_file(f, output_dir)
            continue

def download_all_files(record_id: str, output_dir: str ="."):
    """
    Setup for downloading all files from a Zenodo record.
    Paramiters
    ----------
    
    record_id : str
        string of numbers that is the zenodo's record ID.
    output_dir : str, optional
        Directory for the files to be stored in. Default is '.'.

    """
    os.makedirs(output_dir, exist_ok=True)


    metadata = get_record_metadata(record_id)
    files = metadata.get("files", [])

    print(f"Found {len(files)} files in record {record_id}")

    for f in files:
        download_file(f, output_dir)

