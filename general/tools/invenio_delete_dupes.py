"""
Module for finding and deleting duplicate records in an Invenio community.
"""

import requests

INVENIO_URL = "https://data-collections.psdi.ac.uk"
COMMUNITY_ID = "6bf5e15a-07ca-4fd7-85c9-349136666383"
API_TOKEN = ""

# Set to False to enable deletion
DRY_RUN = False

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def collect_community_records():
    """
    Retrieve all records belonging to a community and group them by title.

    Returns
    -------
    dict
        Dictionary mapping titles to lists of record IDs.
    """
    records_by_title = {}

    page = 1
    size = 100

    while True:
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
            record_id = record["id"]
            title = record["metadata"]["title"]

            records_by_title.setdefault(title, []).append(record_id)

        page += 1

    return records_by_title


def find_duplicates(records_by_title):
    """
    Identify duplicate records based on identical titles.

    Parameters
    ----------
    records_by_title : dict
        Dictionary mapping titles to record IDs.

    Returns
    -------
    dict
        Titles mapped to duplicate record ID lists.
    """
    return {
        title: ids
        for title, ids in records_by_title.items()
        if len(ids) > 1
    }


def delete_published_record(record_id):
    """
    Delete a published Invenio record by creating and deleting a draft.

    Parameters
    ----------
    record_id : str
        ID of the record to delete.
    """
    print(f"Processing record {record_id}")

    if DRY_RUN:
        print("DRY RUN — not deleting")
        return

    # Create edit draft
    response = requests.post(
        f"{INVENIO_URL}/api/records/{record_id}/draft",
        headers=HEADERS,
    )
    response.raise_for_status()

    print("Draft created")

    # Delete draft (removes published record)
    response = requests.delete(
        f"{INVENIO_URL}/api/records/{record_id}/draft",
        headers=HEADERS,
    )
    response.raise_for_status()

    print(f"Deleted published record {record_id}")


def delete_duplicate_records(duplicates):
    """
    Delete duplicate records while keeping the first instance.

    Parameters
    ----------
    duplicates : dict
        Dictionary of duplicate titles and record IDs.
    """
    for title, ids in duplicates.items():
        keep = ids[0]
        remove = ids[1:]

        print(f"\nKeeping {keep}")
        print(f"Deleting {remove}")

        for record_id in remove:
            delete_published_record(record_id)


def main():
    records_by_title = collect_community_records()
    duplicates = find_duplicates(records_by_title)

    print(f"Found {len(duplicates)} duplicate titles")
    print(duplicates)

    delete_duplicate_records(duplicates)

    print("\nFinished.")


if __name__ == "__main__":
    main()