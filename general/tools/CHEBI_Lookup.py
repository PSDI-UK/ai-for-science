"""
A module for adding additives in a JSON document using the ChEBI public API.

Adds (when available):
  - "chebi_api_url"
  - "molecule_class_ids"          (list of final_id where relation_type == "is a")
  - "molecule_class_urls"         (list of https://www.ebi.ac.uk/chebi/CHEBI:<final_id>)
  - "molecule_class_names"        (list of final_name where relation_type == "is a")
  - "iupac_name_en"
  - "formula"
  - "mass"
  - "canonical_smiles"
  - "standard_inchi"
  - "standard_inchi_key"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import requests


CHEBI_API_TEMPLATE = (
    "https://www.ebi.ac.uk/chebi/backend/api/public/compound/"
    "CHEBI%3A{chebi_id}/"
    "?only_ontology_parents=false&only_ontology_children=false"
)

CHEBI_PAGE_PREFIX = "https://www.ebi.ac.uk/chebi/CHEBI:"

_TAG_RE = re.compile(r"<[^>]+>")

def strip_html(text: str) -> str:
    """
    Some variables have HTML tags like <small>...</small> from ChEBI strings, strip these HTML tags.
    
    Parameters
    ----------
        text : String
            The text that needs the HTML tags stripped from it.

    Returns
    -------
        String
            The text that has had the HTML tags stripped.
    """
    return _TAG_RE.sub("", text).strip()

def get_chebi_id(chebi_url: str) -> Optional[str]:
    """
    Extract numeric ChEBI id from URLs.
    
    Parameters
    ----------
        chebi_url : String
            The url for the ChEBI lookup
    
    Rerurns
    -------
    String
        The ChEBI ID that is being looked up
    """
    if not chebi_url:
        return None

    # Common pattern "CHEBI:<digits>"
    m = re.search(r"CHEBI:(\d+)", chebi_url)
    if m:
        return m.group(1)

    # Fallback: maybe user passed just digits
    m = re.fullmatch(r"\d+", chebi_url.strip())
    if m:
        return m.group(0)

    return None


def safe_get(json_dict: dict, path: List[str]) -> Any:
    """
    Safely retrieve a value from a nested dictionary.

    Parameters
    ----------
    json_dict : dict
        The json file in a dictionary to retrieve the value from.
    path : list[str]
        A list of keys representing the path to the desired value within the dictionary.

    Returns
    -------
    Any
        The value found at the specified path, or ``None`` if the path does not exist.
    """
    cur = json_dict
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur

def pick_iupac_name_en(names: Any) -> Optional[str]:
    """
    Gets the IUPAC name ensuring it is in the language code en
    Parameters
    ----------
    names : dict 
        A dictonary that has all the names related to the ChEBI ID 
    
    Returns
    -------
    The English IUPAC name if present.
    """
    if not isinstance(names, dict):
        return None

    iupac_list = names.get("IUPAC NAME")
    if not isinstance(iupac_list, list):
        return None

    for item in iupac_list:
        if not isinstance(item, dict):
            continue
        if item.get("language_code") == "en":
            val = item.get("name")
            if isinstance(val, str) and val.strip():
                return strip_html(val)

    # Fallback: return first available IUPAC name if no English-tagged one found
    for item in iupac_list:
        if isinstance(item, dict):
            val = item.get("name")
            if isinstance(val, str) and val.strip():
                return strip_html(raw)

    return None

def extract_is_a_relations(payload: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """
    Extracts 'is a' relations related to the given ChEBI item

    Parameters
    ----------
    payload : Dict
        A dictonary that has all relations

    Returns
    -------
    final_ids : List
        Id's for relations where relation_type == "is a".
    final_names : List
        Names for relations where relation_type == "is a".
    """
    ids: List[str] = []
    names: List[str] = []

    rels = payload.get("ontology_relations", {})
    if not isinstance(rels, dict):
        return ids, names

    outgoing = rels.get("outgoing_relations", [])
    if not isinstance(outgoing, list):
        return ids, names

    for rel in outgoing:
        if not isinstance(rel, dict):
            continue
        if rel.get("relation_type") != "is a":
            continue

        final_id = rel.get("final_id")
        final_name = rel.get("final_name")

        if final_id is not None:
            ids.append(str(final_id).strip())

        if isinstance(final_name, str) and final_name.strip():
            # strip any HTML markup from names (e.g. <small>, <em>)
            names.append(strip_html(final_name))
        else:
            names.append("")

    return ids, names

def fetch_chebi_payload(
    chebi_id: str,
    session: requests.Session,
    timeout: float = 30.0,
    retries: int = 3,
    backoff_sec: float = 1.5,
) -> Dict[str, Any]:
    """
    Gets the all the ChEBI info of the given ChEBI ID

    Parameters
    ----------
    chebi_id : String
        The ID of the ChEBI element that the data is needed of.
    session : requests.Session
       A persistent HTTP session used to perform requests to the ChEBI API.
    timeout : float, optional
        A float that determins how long the script should wait before timing out.
    retries : int, optional
        A int that determins the maximum number of attempts to fetch the data before failing
    backoff_sec : float, optional
        The delay between retry attempts

    Returns
    -------
    dict
        A dictionary containing the parsed JSON response returned by the ChEBI API.

    Raises
    ------
    RuntimeError
        If the ChEBI ID is not forund or the maximum retries are reached
    """
    url = CHEBI_API_TEMPLATE.format(chebi_id=chebi_id)

    last_err: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, timeout=timeout, headers={"Accept": "application/json"})
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(backoff_sec * attempt)
            else:
                raise

    raise RuntimeError(f"Failed to fetch ChEBI {chebi_id}: {last_err}") 


def enrich_additive(json_dict: Dict[str, Any], payload: Dict[str, Any], chebi_id: str) -> None:
    """
    Collects and adds all additive data about the ChEBI element to the dictonary

    Parameters
    ----------
    json_dict : Dict
        This is where all the additive data is added to agenst there related name
    payload : Dict
        This is the full json receveved by the ChEBI api about the spisific ChEBI ID
    chebi_id : String
        This is the ChEBI ID for the ChEBI element the additive infomation is about.
    """
    # Ontology "is a" relations
    class_ids, class_names = extract_is_a_relations(payload)
    json_dict["ChEBI_molecule_class_urls"] = [f"{CHEBI_PAGE_PREFIX}{cid}" for cid in class_ids if cid]
    json_dict["ChEBI_molecule_class_names"] = class_names
    json_dict["name"] = strip_html(payload.get("name"))

    # IUPAC NAME (English)
    json_dict["iupac_name_en"] = pick_iupac_name_en(payload.get("names"))

    # chemical_data
    chem_data = payload.get("chemical_data", {})
    if isinstance(chem_data, dict):
        json_dict["formula"] = chem_data.get("formula")
        json_dict["mass"] = chem_data.get("mass")

    # default_structure
    struct = payload.get("default_structure", {})
    if isinstance(struct, dict):
        json_dict["canonical_smiles"] = struct.get("smiles")
        json_dict["standard_inchi"] = struct.get("standard_inchi")
        json_dict["standard_inchi_key"] = struct.get("standard_inchi_key")


def main() -> int:
    """
    Reads an input JSON file containing an ``Additives`` list, retrieves
    additional chemical metadata for each additive from the ChEBI REST API,
    and writes the developed result to a new JSON file.


    Returns
    -------
    int
        Exit status code.
        ``0`` successful execution.
        ``2`` a malformed input JSON (missing or invalid ``Additives`` key).
    
    Notes
    -----
    The new file is called <old file name>_enriched.json
    """
    ap = argparse.ArgumentParser(description="Enrich Additives in a JSON using the ChEBI API.")
    ap.add_argument("input_json", help="Path to input JSON file")
    ap.add_argument(
        "-o",
        "--output",
        default=None,
        help="Path to output JSON file (default: <input>_enriched.json)",
    )
    ap.add_argument(
        "--sleep",
        type=float,
        default=0.1,
        help="Sleep seconds between API calls (default: 0.1)",
    )
    args = ap.parse_args()

    in_path = args.input_json
    out_path = args.output or (in_path.rsplit(".", 1)[0] + "_enriched.json")

    with open(in_path, "r", encoding="utf-8") as f:
        doc = json.load(f)

    additives = doc.get("Additives")
    if not isinstance(additives, list):
        print('ERROR: top-level key "Additives" is missing or not a list.', file=sys.stderr)
        return 2

    with requests.Session() as session:
        for i, add in enumerate(additives):
            if not isinstance(add, dict):
                continue

            chebi_url = add.get("chebi url") or add.get("chebi_url") or add.get("chebi")
            if not isinstance(chebi_url, str):
                add["chebi_enrich_error"] = "Missing 'chebi url' string"
                continue

            chebi_id = get_chebi_id(chebi_url)
            if not chebi_id:
                add["chebi_enrich_error"] = f"Could not parse ChEBI id from: {chebi_url}"
                continue

            try:
                payload = fetch_chebi_payload(chebi_id, session=session)
                enrich_additive(add, payload, chebi_id)
            except Exception as e:
                add["chebi_enrich_error"] = str(e)

            if args.sleep > 0 and i < len(additives) - 1:
                time.sleep(args.sleep)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=8, ensure_ascii=False)

    print(f"Wrote enriched JSON to: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

