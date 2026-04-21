#!/usr/bin/env python3
"""
Automatically accept community submission requests.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, List

import requests


COMMUNITY = "project-m"
BASE_URL = "https://data-collections.psdi.ac.uk"
TOKEN = ""

COMMUNITY_SLUG = os.environ.get("INVENIO_COMMUNITY_SLUG", COMMUNITY)

PAGE_SIZE = int(os.environ.get("INVENIO_PAGE_SIZE", "50"))
SLEEP_SECONDS = float(os.environ.get("INVENIO_SLEEP_SECONDS", "0.05"))

HEADERS = {
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
    return requests.request(method, url, headers=HEADERS, timeout=60, **kwargs)


def get_community_id(slug: str) -> str:
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


def search_requests(q: str, page: int, size: int) -> Dict[str, Any]:
    """
    Search review requests using a query string.

    Parameters
    ----------
    q : str
        Search query.
    page : int
        Page number.
    size : int
        Results per page.

    Returns
    -------
    dict
        JSON response containing requests.
    """
    r = req(
        "GET",
        "/api/requests",
        params={"q": q, "page": page, "size": size, "sort": "newest"},
    )
    return r.json()


def extract_hits(resp: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract request hits from API response.

    Parameters
    ----------
    resp : dict
        API response JSON.

    Returns
    -------
    list
        List of request records.
    """
    return (resp.get("hits") or {}).get("hits") or []


def guess_request_is_open(hit: Dict[str, Any]) -> bool:
    """
    Determine whether a request appears open.

    Parameters
    ----------
    hit : dict
        Request metadata.

    Returns
    -------
    bool
        True if request should be processed.
    """
    if hit.get("is_closed") is True:
        return False

    status = (hit.get("status") or "").lower()
    if status in {"accepted", "declined", "cancelled", "canceled"}:
        return False

    return True


def accept_request(
    request_id: str,
    message: str = "Auto-accepted by script.",
) -> bool:
    """
    Accept a community submission request.

    Parameters
    ----------
    request_id : str
        Request identifier.
    message : str, optional
        Acceptance message.

    Returns
    -------
    bool
        True if accepted successfully.
    """
    payload = {"payload": {"content": message, "format": "html"}}

    r = req("POST", f"/api/requests/{request_id}/actions/accept", json=payload)

    if r.ok:
        return True

    print(
        f"  ! Failed to accept {request_id}: {r.status_code} {r.text}",
        file=sys.stderr,
    )
    return False


def main() -> int:
    """
    Search for community submission requests and accept them.
    """
    community_id = get_community_id(COMMUNITY_SLUG)
    print(f'Community "{COMMUNITY_SLUG}" -> id={community_id}')

    candidate_queries = [
        f'type:"community-submission" AND receiver.community:"{community_id}"',
        f'type:community-submission AND receiver.community:"{community_id}"',
        f'receiver.community:"{community_id}"',
        f'type:"community-submission"',
    ]

    accepted = 0
    seen = set()

    for q in candidate_queries:
        print(f"\nSearching requests with q={q!r}")
        page = 1

        while True:
            resp = search_requests(q=q, page=page, size=PAGE_SIZE)
            hits = extract_hits(resp)

            if not hits:
                break

            for hit in hits:
                rid = hit.get("id")
                if not rid or rid in seen:
                    continue

                seen.add(rid)

                if not guess_request_is_open(hit):
                    continue

                receiver = hit.get("receiver") or {}
                recv_comm = receiver.get("community")

                if recv_comm and str(recv_comm) != str(community_id):
                    continue

                title = hit.get("title") or ""
                r_type = hit.get("type") or ""
                status = hit.get("status") or ""

                print(
                    f"- Request {rid}: "
                    f"type={r_type!r} status={status!r} title={title!r}"
                )

                if accept_request(rid):
                    accepted += 1
                    print("  -> accepted")

                time.sleep(SLEEP_SECONDS)

            page += 1

    print(f"\nDone. Accepted: {accepted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())