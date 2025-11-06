import requests
import os

# -----------------------------
# Configuration
# -----------------------------
INVENIO_URL = "https://your-invenio-instance.org"  # Replace with your InvenioRDM URL
API_TOKEN = "YOUR-API-KEY"                         # Replace with your personal access token
FILES_TO_UPLOAD = [
        r"FILES-TO-UPLOAD",
        r"FILES-TO-UPLOAD",
        ]
RECORD_METADATA = {
    "title": "TITLE",
    "creators": [{"name": "CREATOR"}],
    "publication_date": "2025",
    "resource_type": {"type": "dataset"},
}

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

# -----------------------------
# Create a draft record
# -----------------------------
draft_url = f"{INVENIO_URL}/api/records"
response = requests.post(draft_url, headers=HEADERS, json={"metadata": RECORD_METADATA})

if response.status_code not in [200, 201]:
    print("Failed to create draft record:", response.text)
    exit(1)

record = response.json()
record_id = record["id"]
print(f"Draft record created with ID: {record_id}")

# -----------------------------
# Upload files to draft
# -----------------------------
upload_url = f"{INVENIO_URL}/api/records/{record_id}/draft/files"

for file_path in FILES_TO_UPLOAD:
    file_name = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        files = {"file": (file_name, f)}
        response = requests.post(upload_url, headers={"Authorization": f"Bearer {API_TOKEN}"}, files=files)

    if response.status_code in [200, 201]:
        print(f"Uploaded '{file_name}' successfully.")
    else:
        print(f"Failed to upload '{file_name}': {response.status_code}")
        print(response.text)

# -----------------------------
# Publish the draft
# -----------------------------
publish_url = f"{INVENIO_URL}/api/records/{record_id}/draft/actions/publish"
response = requests.post(publish_url, headers=HEADERS)

if response.status_code in [200, 202]:
    print(f"Record {record_id} published successfully!")
else:
    print(f"Failed to publish record: {response.status_code}")
    print(response.text)

