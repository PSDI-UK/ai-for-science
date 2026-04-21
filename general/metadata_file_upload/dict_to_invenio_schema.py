"""
Module for formating the dictonary to fit the Invenio json. 
The dictonary has the keys being the names of the json element.
"""
KNOWN_FIELDS = {
    "Resource type": "resource_type.id",
    "Publication Date": "publication_date",
    "Title": "title",
    "Creators": "creators",
    "License": "rights",
}

DOMAIN_ID = "project-m"

DOMAIN_NS = "dsmd" 

def set_path(obj: dict, path: str, value: str):
    """
    Set a value on a nested dictionary using a dot-separated path.
    
    Parameters
    ----------
        obj : Dict
            The dictonary to modify
        path : String
            Dot-separated path specifying where to set the value
        value : String
            The value to assign at the target path.
    """
    parts = path.split(".")
    for p in parts[:-1]:
        obj = obj.setdefault(p, {})
    obj[parts[-1]] = value


def normalize_key(key: str) -> str:
    """
    Make keys normalised for Invenio custom_fields
    
    Parameters
    ----------
    key : String
        The key that is being normalised

    Returns
    -------
    String
        The normalised key
    """
    return (
        str(key)
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("__", "_")
    )


def adapt_creators(creators: list) -> dict:
    """
    Builds the creators and gets all there info in to a dictonary

    Parameters
    ----------
    creators : List
        This is a list of creators
    
    Returns
    -------
    Dict
        The dictonary of the creators and all info about the creators 
    """
    out = []

    for c in creators:
        creator = {
            "person_or_org": {
                "type": "personal",
                "given_name": c.get("Given names"),
                "family_name": c.get("Family name"),
            }
        }

        if "Identifiers" in c:
            creator["person_or_org"]["identifiers"] = [
                {
                    "scheme": "orcid",
                    "identifier": i.split("/")[-1],
                }
                for i in c["Identifiers"]
                if "orcid.org" in i
            ]

        if "Affiliations" in c:
            creator["affiliations"] = [
                {
                    "name": a["Name"],
                    # "id": a.get("ROR"),
                }
                for a in c["Affiliations"]
            ]

        if "Role" in c:
            creator["role"] = {
                "id": (
                    "other"
                    if c["Role"][0].lower().replace(" ", "") == "dataanalysis"
                    else c["Role"][0].lower().replace(" ", "")
                )
            }

        out.append(creator)

    return out


def adapt_license(licence: dict) -> dict:
    """
    Formats licence to be what is expected.

    Parameters
    ----------
    licence : Dict
        A dictonary that has the licence and related licence data
    
    Returns
    -------
    Dict
        Returns a the licence data in a format that is accepted by Invenio
    """
    for _, v in licence.items():
        return [
            {
                "id": "cc-by-4.0",
                "title": {"en": v.get("label")},
                "link": v.get("url"),
            }
        ]


def to_invenio_record(data: dict) -> dict:
    """
    Formats the Dict in to the Invenio json format

    Parameters
    ----------
    data : Dict
        The data that is to be formated

    Returns
    -------
    Dict
        The data formated for Invenio json
    """
    record = {
        "metadata": {},
        "custom_fields": {
            DOMAIN_NS: []
            }
    }

    dsmb_obj = {}

    # Attach the domain
    record["metadata"]["domains"] = [{"id": DOMAIN_ID}]
    
    for key, value in data.items():
        if value is None:
            continue

        # Known Invenio fields
        if key in KNOWN_FIELDS:
            path = KNOWN_FIELDS[key]

            if key == "Resource type":
                set_path(record["metadata"], path, value.lower())

            elif key == "Creators":
                set_path(record["metadata"], path, adapt_creators(value))

            elif key == "License":
                set_path(record["metadata"], path, adapt_license(value))

            else:
                set_path(record["metadata"], path, value)

        # Domain-specific metadata
        else:
            dsmb_obj[normalize_key(key)] = value
            
    if dsmb_obj:
        record["custom_fields"][DOMAIN_NS] = [dsmb_obj]
    return record

