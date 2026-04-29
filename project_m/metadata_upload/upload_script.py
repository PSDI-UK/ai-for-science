"""
Module for uploading a record to invenio
"""
import requests
from general.invenio_record_upload.dict_to_invenio_schema import to_invenio_record
from general.invenio_record_upload.extract_data_from_files import extract_from_zenodo
from pathlib import Path

# These are all the variables that need to be chaged
INVENIO_URL = "https://data-collections-dev.psdi.ac.uk"
TOKEN = "INVENIO API TOKEN"
ZENODO_RECORD_ID = "17631085"
METADATA_JSON = "./project_m/metadata_upload/metadata_fields.json"
CONSTENTS_DIR = "./constents/"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

FILE_HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
}

def create_payload(file_name: str) -> dict:
    """
    Returns the metadata payload for a given file
    
    Parameters
    ----------
    file_name : String
        The file name that the metadata payload is about.

    Returns
    -------
    dict
        A json formated dict that has the metadata assosiated with the relevent data.
 
    """
    metadata = extract_from_zenodo(file_name, METADATA_JSON, ZENODO_RECORD_ID, CONSTENTS_DIR)
    payload = to_invenio_record(metadata, "project-m", "dsmd")
    payload["metadata"]["communities"] = [{"id": "project-m"}]
    return payload

def create_draft(payload: dict) -> str:
    """
    Creates a Invenio draft record and returns the ID of that draft

    Parameters
    ----------
    payload : dict
        A json formated dict that has the metadata assosiated with the relevent data.

    Returns
    -------
    String
        The ID of the newly created draft record that can be uesd to reference it for the API.
    """
    response = requests.post(
        f"{INVENIO_URL}/api/records",
        headers=HEADERS,
        json=payload,
    )
    response.raise_for_status() 
    record = response.json()
    record_id = record["id"]
    print("Draft created:", record_id)
    return record_id

def add_file(file_path: Path, record_id: str):
    """
    Adds the file to the draft record

    Parameters
    ----------
    file_path : pathlib.WindowsPath 
        The file path for the file that that is being added to the draft record 
    record_id : String
        The ID of the draft record that is having the file added.
    """
    filename = file_path.name
    filesize = file_path.stat().st_size

    print(f"Uploading file: {filename}")

    init_resp = requests.post(
        f"{INVENIO_URL}/api/records/{record_id}/draft/files",
        headers=HEADERS,
        json=[{"key": filename,}],
    )

    if not init_resp.ok:
        print("Init upload failed")
        print("Status:", init_resp.status_code)
        print("Response text:", init_resp.text)  
    init_resp.raise_for_status()

    with open(file_path, "rb") as f:
        content_resp = requests.put(
            f"{INVENIO_URL}/api/records/{record_id}/draft/files/{filename}/content",
            headers=FILE_HEADERS,
            data=f,
        )
        content_resp.raise_for_status()

    commit_resp = requests.post(
        f"{INVENIO_URL}/api/records/{record_id}/draft/files/{filename}/commit",
        headers=HEADERS,
        )
    commit_resp.raise_for_status()

    print(f"File committed: {filename}")

    print(f"All files uploaded to draft {record_id}")


if __name__ == "__main__":
    rawdatadirectory = Path.cwd() / "constents" / "raw" / "ProjectMDiffractionDataUpdated5December2025"
    #all_files = list(rawdatadirectory.rglob("*.xye"))
    #all_files = list(rawdatadirectory.rglob("*-mythen_summed.xye"))
    file_names = {"578573-mythen_summed.xye"}
    #file_names = [p.name for p in all_files]

    for file_name in file_names:
        payload = create_payload(file_name) 
        record_id = create_draft(payload)
        add_file(rawdatadirectory / file_name, record_id)

