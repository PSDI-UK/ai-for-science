#!/usr/bin/env python3
"""
Publish user drafts to a community or delete drafts without titles.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, Optional

import requests


BASE_URL = "https://data-collections.psdi.ac.uk"
TOKEN = ""
COMMUNITY_SLUG = "project-m"

PAGE_SIZE = int(os.environ.get("INVENIO_PAGE_SIZE", "100"))
SLEEP_SECONDS = float(os.environ.get("INVENIO_SLEEP_SECONDS", "0.05"))
DRY_RUN = os.environ.get("INVENIO_DRY_RUN", "0") == "1"

def headers() -> Dict[str, str]:
    """
    Create request headers for authenticated API access.

    Returns
    -------
    dict
        HTTP headers including authorization token.
    """

    return {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def req(method: str, path: str, **kwargs) -> requests.Response:
    """
    Send an HTTP request to the Invenio API.

    Parameters
    ----------
    method : str
        HTTP method.
    path : str
        API endpoint path.

    Returns
    -------
    requests.Response
        API response object.
    """

    url = f"{BASE_URL}{path}"
    return requests.request(method, url, headers=headers(), timeout=60, **kwargs)


def get_community_id_from_slug(slug: str) -> str:
    """
    Resolve a community slug to its internal ID.

    Parameters
    ----------
    slug : str
        Community slug.

    Returns
    -------
    str
        Community ID.
    """
    r = req("GET", f"/api/communities/{slug}")

    return r.json()["id"]


def list_user_records(page: int, size: int) -> Dict[str, Any]:
    """
    List records owned by the authenticated user.

    Parameters
    ----------
    page : int
        Page number.
    size : int
        Number of results per page.

    Returns
    -------
    dict
        JSON response containing records.
    """
    r = req(
        "GET",
        "/api/user/records",
        params={"page": page, "size": size, "sort": "updated-desc"},
    )

    return r.json()


def try_get_draft(record_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a draft version of a record if it exists.

    Parameters
    ----------
    record_id : str
        Record identifier.

    Returns
    -------
    dict or None
        Draft metadata or None if not a draft.
    """
    r = req("GET", f"/api/records/{record_id}/draft")

    if r.status_code == 404:
        return None

    if not r.ok:
        print(
            f"  ! Could not fetch draft {record_id}: {r.status_code} {r.text}",
            file=sys.stderr,
        )
        return None

    return r.json()


def draft_title(draft: Dict[str, Any]) -> str:
    """
    Extract and normalise the draft title.

    Parameters
    ----------
    draft : dict
        Draft metadata.

    Returns
    -------
    str
        Cleaned title string.
    """
    md = draft.get("metadata") or {}
    title = md.get("title")

    if title is None:
        return ""

    if isinstance(title, str):
        return title.strip()

    return str(title).strip()


def delete_draft(record_id: str) -> bool:
    """
    Delete a draft record.

    Parameters
    ----------
    record_id : str
        Record identifier.

    Returns
    -------
    bool
        True if deletion succeeded.
    """
    if DRY_RUN:
        print(f"  DRY_RUN: would DELETE draft {record_id}")
        return True

    r = req("DELETE", f"/api/records/{record_id}/draft")

    if r.status_code == 204:
        return True

    print(
        f"  ! Failed to delete draft {record_id}: {r.status_code} {r.text}",
        file=sys.stderr,
    )
    return False


def submit_draft_to_community(
    record_id: str,
    community_id: str,
    message: str = "",
) -> bool:
    """
    Submit a draft record to a community for review.

    Parameters
    ----------
    record_id : str
        Record identifier.
    community_id : str
        Community ID.
    message : str, optional
        Submission message.

    Returns
    -------
    bool
        True if submission succeeded.
    """
    payload_review = {
        "receiver": {"community": community_id},
        "type": "community-submission",
    }

    if DRY_RUN:
        print(f"  DRY_RUN: would submit draft {record_id}")
        return True

    r1 = req("PUT", f"/api/records/{record_id}/draft/review", json=payload_review)

    if not r1.ok:
        print(
            f"  ! Failed to set review receiver for {record_id}: {r1.status_code} {r1.text}",
            file=sys.stderr,
        )
        return False

    payload_submit = {
        "payload": {"content": message or "", "format": "html"}
    }

    r2 = req(
        "POST",
        f"/api/records/{record_id}/draft/actions/submit-review",
        json=payload_submit,
    )

    if r2.status_code in (200, 202):
        return True

    print(
        f"  ! Failed to submit for review {record_id}: {r2.status_code} {r2.text}",
        file=sys.stderr,
    )
    return False


def main() -> int:
    community_id = get_community_id_from_slug(COMMUNITY_SLUG)
    print(f'Community "{COMMUNITY_SLUG}" -> id={community_id}')

    total_seen = total_drafts = deleted = submitted = 0

    page = 1
    while True:
        data = list_user_records(page=page, size=PAGE_SIZE)
        hits = (data.get("hits") or {}).get("hits") or []

        if not hits:
            break

        for hit in hits:
            total_seen += 1
            rid = hit.get("id")
            if not rid:
                continue

            draft = try_get_draft(rid)
            if draft is None:
                continue

            total_drafts += 1
            title = draft_title(draft)
            print(f"- Draft {rid}: {title!r}")

            if not title:
                if delete_draft(rid):
                    deleted += 1
                    print("  -> deleted (no title)")
                time.sleep(SLEEP_SECONDS)
                continue

            if submit_draft_to_community(
                rid,
                community_id,
                message="Submitting via script to project-m.",
            ):
                submitted += 1
                print("  -> submitted to community")

            time.sleep(SLEEP_SECONDS)

        page += 1

    print("\nDone.")
    print(f"  records scanned: {total_seen}")
    print(f"  drafts found:    {total_drafts}")
    print(f"  deleted:         {deleted}")
    print(f"  submitted:       {submitted}")

    if DRY_RUN:
        print("\n(DRY_RUN enabled: no changes made.)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())