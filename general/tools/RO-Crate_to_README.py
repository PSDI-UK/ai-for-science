#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
File: RO-crate_to_README.py
Author: Matthew Partridge
Created: 2026-03-27
Description: Command-line RO-Crate JSON to README.md generator
Version: 0.1
"""

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath


def build_readme_from_rocrate(crate_json):
    graph = crate_json.get("@graph", [])
    if not isinstance(graph, list):
        raise ValueError("The RO-Crate metadata file does not contain a valid @graph array.")

    entities = {
        entity.get("@id"): entity
        for entity in graph
        if isinstance(entity, dict) and "@id" in entity
    }

    root = entities.get("./")
    if root is None:
        raise ValueError("Could not find the root dataset entity with @id './'.")

    sections = []
    sections.append("# Readme")

    about_lines = render_about(root, entities)
    if about_lines:
        sections.append(about_lines)

    people_section = render_people_section(root, entities)
    if people_section:
        sections.append(people_section)

    main_entity_section = render_main_entity(root, entities)
    if main_entity_section:
        sections.append(main_entity_section)

    file_structure_section = render_file_structure(root, entities)
    if file_structure_section:
        sections.append(file_structure_section)

    metadata_notes = render_metadata_notes(crate_json, root, entities)
    if metadata_notes:
        sections.append(metadata_notes)

    return "\n\n".join(
        section.strip() for section in sections if section and section.strip()
    ) + "\n"


def render_about(root, entities):
    lines = ["## About", ""]

    summary_fields = [
        ("Name", root.get("name")),
        ("Description", root.get("description")),
        ("Type", describe_type(root.get("@type"))),
        ("Date published", root.get("datePublished")),
        ("Version", root.get("version")),
        ("License", format_reference(root.get("license"), entities)),
        ("Keywords", format_reference(root.get("keywords"), entities)),
        ("Main entity", format_reference(root.get("mainEntity"), entities)),
        ("About", format_reference(root.get("about"), entities)),
    ]

    for label, value in summary_fields:
        if value:
            lines.append(f"**{label}:** {value}")

    return "\n".join(lines)


def render_people_section(root, entities):
    role_candidates = ["author", "creator", "publisher", "contributor"]
    seen = set()
    people_blocks = []

    for role in role_candidates:
        values = ensure_list(root.get(role))
        formatted_people = []

        for item in values:
            key = json.dumps(item, sort_keys=True) if isinstance(item, dict) else str(item)
            if key in seen:
                continue
            seen.add(key)
            formatted_people.append(format_agent(item, entities))

        if formatted_people:
            people_blocks.append(
                f"### {prettify_term(role)}\n" + "\n".join(formatted_people)
            )

    if not people_blocks:
        return ""

    return "## People and Organisations\n\n" + "\n\n".join(people_blocks)


def render_main_entity(root, entities):
    main_entity = root.get("mainEntity")
    if not main_entity:
        return ""

    resolved = resolve_entity(main_entity, entities)
    if not resolved:
        return ""

    lines = ["## Main Resource", ""]
    lines.extend(render_entity_bullets(resolved, entities))
    return "\n".join(lines)


def render_entity_bullets(entity, entities):
    lines = []

    name = entity.get("name") or entity.get("@id") or "Unnamed entity"
    lines.append(f"- **{name}**")

    preferred_order = [
        "@type",
        "description",
        "datePublished",
        "dateCreated",
        "dateModified",
        "version",
        "license",
        "keywords",
        "creator",
        "author",
        "contributor",
        "publisher",
        "about",
        "encodingFormat",
        "contentSize",
        "url",
        "identifier",
    ]

    seen = {"name", "@id"}
    for key in preferred_order:
        if key in entity:
            value = entity.get(key)
            if value not in (None, "", [], {}):
                lines.append(f"  - **{prettify_term(key)}:** {format_reference(value, entities)}")
                seen.add(key)

    for key, value in entity.items():
        if key in seen:
            continue
        if value in (None, "", [], {}):
            continue
        lines.append(f"  - **{prettify_term(key)}:** {format_reference(value, entities)}")

    return lines


def render_file_structure(root, entities):
    parts = ensure_list(root.get("hasPart"))
    if not parts:
        return ""

    rows = collect_file_structure_rows(parts, entities)
    if not rows:
        return ""

    lines = ["## File Structure", ""]
    lines.append("| Location | File | Format | Description |")
    lines.append("|---|---|---|---|")

    for row in rows:
        location = escape_markdown_table_cell(row["location"])
        file_name = escape_markdown_table_cell(row["file_name"])
        encoding_format = escape_markdown_table_cell(row["encoding_format"])
        description = escape_markdown_table_cell(row["description"])
        lines.append(f"| {location} | {file_name} | {encoding_format} | {description} |")

    return "\n".join(lines)


def collect_file_structure_rows(parts, entities):
    rows = []

    for part in parts:
        resolved = resolve_entity(part, entities)
        if not resolved:
            if isinstance(part, dict):
                resolved = part
            else:
                path = str(part)
                resolved = {"@id": path, "name": path}

        path = extract_path_identifier(resolved)
        if not path:
            continue

        path = normalize_rocrate_path(path)
        if not path:
            continue

        file_name = PurePosixPath(path).name
        parent = str(PurePosixPath(path).parent)
        if parent in ("", "."):
            location = "/"
        else:
            location = f"/{parent.strip('/')}/"

        rows.append(
            {
                "location": location,
                "file_name": file_name,
                "encoding_format": str(resolved.get("encodingFormat") or ""),
                "description": str(resolved.get("description") or "No description available."),
                "sort_path": path.lower(),
                "sort_name": file_name.lower(),
            }
        )

    rows.sort(key=lambda row: (folder_sort_key(row["location"]), row["sort_path"], row["sort_name"]))
    return rows


def folder_sort_key(location):
    if location == "/":
        return (0, "")
    folder_path = location.strip("/")
    parts = [part for part in folder_path.split("/") if part]
    return (len(parts), folder_path.lower())


def escape_markdown_table_cell(value):
    return str(value).replace("\n", " ").replace("|", "\\|").strip()


def extract_path_identifier(entity):
    for key in ("@id", "name", "identifier", "url"):
        value = entity.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def normalize_rocrate_path(value):
    value = value.strip()

    if value.startswith("./"):
        value = value[2:]

    if value in ("", "."):
        return ""

    if value.startswith("/"):
        value = value[1:]

    return value


def is_folder_path(path, entity):
    entity_type = entity.get("@type")
    if isinstance(entity_type, list):
        entity_type = " ".join(str(v) for v in entity_type)
    entity_type = str(entity_type or "").lower()
    path = str(path).lower()

    return (
        path.endswith("/")
        or "dataset" in entity_type
        or "collection" in entity_type
        or "directory" in entity_type
    )


def render_entity_details(entity, entities, heading_level="###"):
    title = entity.get("name") or entity.get("@id") or "Unnamed entity"
    lines = [f"{heading_level} {title}", ""]

    table = render_property_table(entity, entities)
    if table:
        lines.append(table)

    return "\n".join(lines)


def render_property_table(entity, entities, skip_keys=None):
    skip_keys = set(skip_keys or [])
    rows = []

    preferred_order = [
        "name",
        "description",
        "@type",
        "datePublished",
        "dateCreated",
        "dateModified",
        "version",
        "license",
        "keywords",
        "creator",
        "author",
        "contributor",
        "publisher",
        "mainEntity",
        "about",
        "hasPart",
        "encodingFormat",
        "contentSize",
        "url",
        "identifier",
    ]

    seen = set()
    for key in preferred_order:
        if key in entity and key not in skip_keys:
            value = entity.get(key)
            if value not in (None, "", [], {}):
                rows.append((prettify_term(key), format_reference(value, entities)))
                seen.add(key)

    for key, value in entity.items():
        if key in seen or key in skip_keys:
            continue
        if value in (None, "", [], {}):
            continue
        rows.append((prettify_term(key), format_reference(value, entities)))

    if not rows:
        return ""

    lines = ["| Field | Value |", "|---|---|"]
    for field, value in rows:
        safe_value = str(value).replace("\n", " ")
        lines.append(f"| {field} | {safe_value} |")
    return "\n".join(lines)


def render_metadata_notes(crate_json, root, entities):
    context = crate_json.get("@context")
    conforms_to = []

    metadata_entity = None
    for entity in crate_json.get("@graph", []):
        if entity.get("@id") == "ro-crate-metadata.json":
            metadata_entity = entity
            break

    if metadata_entity:
        conforms_to = ensure_list(metadata_entity.get("conformsTo"))

    lines = ["## Metadata Notes", ""]
    if context:
        lines.append(f"- **JSON-LD context:** {format_reference(context, entities)}")
    if conforms_to:
        lines.append("- **Conforms to:** " + ", ".join(format_reference(x, entities) for x in conforms_to))
    lines.append("- **Root entity type:** " + describe_type(root.get("@type")))
    lines.append(f"- **Entities described:** {len([k for k in entities.keys() if k is not None])}")
    lines.append("- **Generated by:** This README was generated automatically from the RO-Crate JSON metadata loaded from the command line.")

    return "\n".join(lines)


def describe_type(type_value):
    if isinstance(type_value, list):
        return ", ".join(prettify_term(v) for v in type_value)
    if type_value:
        return prettify_term(type_value)
    return ""


def format_agent(value, entities):
    entity = resolve_entity(value, entities)
    if not entity:
        return f"- {format_reference(value, entities)}"

    name = entity.get("name") or entity.get("@id") or "Unnamed agent"
    parts = [f"- **{name}**"]

    entity_type = describe_type(entity.get("@type"))
    if entity_type:
        parts.append(f" ({entity_type})")

    affiliation = entity.get("affiliation")
    if affiliation:
        parts.append(f" — affiliation: {format_reference(affiliation, entities)}")

    identifier = entity.get("@id")
    if identifier and str(identifier).startswith(("http://", "https://")):
        parts.append(f" — {markdown_link_if_url(identifier, identifier)}")

    return "".join(parts)


def resolve_entity(value, entities):
    if isinstance(value, dict):
        ref_id = value.get("@id")
        if ref_id in entities:
            return entities[ref_id]
        return value
    if isinstance(value, str) and value in entities:
        return entities[value]
    return None


def ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def format_reference(value, entities):
    if isinstance(value, list):
        return ", ".join(format_reference(v, entities) for v in value)

    if isinstance(value, dict):
        if "@id" in value and len(value) == 1:
            resolved = entities.get(value["@id"])
            if resolved:
                label = resolved.get("name") or resolved.get("@id")
                return markdown_link_if_url(label, resolved.get("@id"))
            return markdown_link_if_url(value["@id"], value["@id"])

        if "name" in value and len(value) <= 3:
            label = value.get("name")
            if value.get("@id"):
                return markdown_link_if_url(label, value.get("@id"))
            return str(label)

        return json.dumps(value, ensure_ascii=False)

    if isinstance(value, str):
        resolved = entities.get(value)
        if resolved:
            label = resolved.get("name") or resolved.get("@id")
            return markdown_link_if_url(label, resolved.get("@id"))
        return markdown_link_if_url(value, value)

    return str(value)


def markdown_link_if_url(label, url):
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        safe_label = str(label) if label not in (None, "") else url
        return f"[{safe_label}]({url})"
    return str(label)


def prettify_term(term):
    if not isinstance(term, str):
        return str(term)

    if term.startswith("http://") or term.startswith("https://"):
        final = term.rstrip("/").split("/")[-1] or term
        term = final.split("#")[-1]

    plain = term.replace("_", " ")
    plain = plain.replace("@", "")
    plain = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", plain)
    plain = re.sub(r"\s+", " ", plain).strip()

    if not plain:
        return ""

    return plain[:1].upper() + plain[1:]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a README.md from an RO-Crate JSON file."
    )
    parser.add_argument(
        "json_file",
        help="Path to the RO-Crate JSON file"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    json_path = Path(args.json_file)

    if not json_path.exists():
        print(f"Error: file not found: {json_path}", file=sys.stderr)
        sys.exit(1)

    if not json_path.is_file():
        print(f"Error: not a file: {json_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(json_path, "r", encoding="utf-8") as handle:
            crate = json.load(handle)
    except Exception as exc:
        print(f"Error: could not load JSON file: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        readme_text = build_readme_from_rocrate(crate)
    except Exception as exc:
        print(f"Error: could not generate README: {exc}", file=sys.stderr)
        sys.exit(1)

    output_path = json_path.with_name("README.md")

    try:
        with open(output_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(readme_text)
    except Exception as exc:
        print(f"Error: could not save README: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"README generated: {output_path}")


if __name__ == "__main__":
    main()