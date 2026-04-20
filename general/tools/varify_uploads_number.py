"""
Module that varify's all files have been uploaded based on a CSV file with a set called "Filename"
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")
import pandas as pd
import requests

INVENIO_URL = "https://data-collections.psdi.ac.uk"
COMMUNITY_ID = "6bf5e15a-07ca-4fd7-85c9-349136666383"
API_TOKEN = ""
CSV_FILE = "constents/batch_out_all_info_with_zscores.csv"

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

df = pd.read_csv(CSV_FILE)

if "Filename" not in df.columns:
    raise ValueError("CSV must contain 'Filename' column")

csv_files = set(df["Filename"].dropna())

print(f"Loaded {len(csv_files)} filenames from CSV")

def fetch_community_files():
    """
    Gets all the files from a the comunity being checked and adds there names to a set.
    Returns
    -------
        community_files : set
        A set of all unique file names found in the community.
    """
    community_files = set()
    page = 1
    size = 100

    while True:
        print(f"Fetching page {page}")

        response = requests.get(
            f"{INVENIO_URL}/api/records",
            headers=HEADERS,
            params={
                "q": f"parent.communities.ids:{COMMUNITY_ID}",
                "page": page,
                "size": size,
            },
        )
        response.raise_for_status()
        data = response.json()

        hits = data["hits"]["hits"]

        if not hits:
            break

        for record in hits:
            files = record.get("files", {}).get("entries", {})

            for filename in files.keys():
                community_files.add(filename)

        page += 1

    return community_files


print("Querying Invenio community...")
community_files = fetch_community_files()

print(f"Community contains {len(community_files)} files")

missing_files = csv_files - community_files
present_files = csv_files & community_files

print("\n===== RESULTS =====")

if missing_files:
    print("\nMissing files:")
    for f in sorted(missing_files):
        print(f" - {f}")
else:
    print("All files exist in community ✅")

print(f"Found: {len(present_files)}")
print(f"Missing: {len(missing_files)}")

