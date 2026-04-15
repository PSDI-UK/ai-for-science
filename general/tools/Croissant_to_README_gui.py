#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
File: Croissant_to_README_gui.py
Author: Matthew Partridge
Created: 2026-04-10
Description: GUI tool for converting Croissant JSON metadata into a human-readable README.md
Version: 0.2
"""

import json
import re
import sys
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)


class CroissantReadmeBuilder(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Croissant README Generator")
        self.resize(1100, 700)

        self.current_json_path = None
        self.current_markdown_path = None
        self.croissant = None

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

        button_row = QHBoxLayout()
        self.load_button = QPushButton("Load Croissant JSON")
        self.save_button = QPushButton("Save README.md")
        self.save_as_button = QPushButton("Save As…")

        self.load_button.clicked.connect(self.load_json)
        self.save_button.clicked.connect(self.save_markdown)
        self.save_as_button.clicked.connect(self.save_markdown_as)

        button_row.addWidget(self.load_button)
        button_row.addWidget(self.save_button)
        button_row.addWidget(self.save_as_button)
        button_row.addStretch()

        layout.addLayout(button_row)

        splitter = QSplitter(Qt.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("Loaded Croissant JSON"))
        self.json_view = QPlainTextEdit()
        self.json_view.setReadOnly(True)
        left_layout.addWidget(self.json_view)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(QLabel("Generated README.md"))
        self.markdown_editor = QPlainTextEdit()
        self.markdown_editor.setPlaceholderText(
            "Load a Croissant JSON file to automatically generate a README."
        )
        right_layout.addWidget(self.markdown_editor)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

    def load_json(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Croissant Metadata File",
            "",
            "JSON files (*.json);;All files (*)",
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                self.croissant = json.load(handle)
        except Exception as exc:
            QMessageBox.critical(self, "Load failed", f"Could not load JSON file.\n\n{exc}")
            return

        self.current_json_path = file_path
        self.current_markdown_path = str(Path(file_path).with_name("README.md"))
        self.json_view.setPlainText(json.dumps(self.croissant, indent=2, ensure_ascii=False))

        try:
            readme = build_readme_from_croissant(self.croissant)
        except Exception as exc:
            QMessageBox.critical(self, "Generation failed", f"Could not generate README.\n\n{exc}")
            return

        self.markdown_editor.setPlainText(readme)
        self.statusBar().showMessage(f"Loaded {file_path} and generated README")

    def save_markdown(self):
        text = self.markdown_editor.toPlainText().rstrip()
        if not text:
            QMessageBox.information(self, "Nothing to save", "There is no README content to save.")
            return

        target = self.current_markdown_path
        if not target:
            self.save_markdown_as()
            return

        try:
            with open(target, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text + "\n")
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", f"Could not save README.\n\n{exc}")
            return

        self.statusBar().showMessage(f"Saved {target}")

    def save_markdown_as(self):
        text = self.markdown_editor.toPlainText().rstrip()
        if not text:
            QMessageBox.information(self, "Nothing to save", "There is no README content to save.")
            return

        default_name = self.current_markdown_path or "README.md"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save README.md",
            default_name,
            "Markdown files (*.md);;All files (*)",
        )
        if not file_path:
            return

        self.current_markdown_path = file_path
        self.save_markdown()


def build_readme_from_croissant(croissant_json):
    if not isinstance(croissant_json, dict):
        raise ValueError("The Croissant metadata file must be a JSON object.")

    sections = ["# README"]

    for builder in (
        render_about,
        render_people_section,
        render_distribution_section,
        render_recordset_section,
        render_grouped_rai_sections,
        render_metadata_notes,
    ):
        content = builder(croissant_json)
        if content:
            sections.append(content)

    return "\n\n".join(section.strip() for section in sections if section and section.strip()) + "\n"


def render_about(data):
    lines = ["## About", ""]

    summary_fields = [
        ("Name", data.get("name")),
        ("Description", data.get("description")),
        ("Type", describe_type(data.get("@type"))),
        ("Version", data.get("version")),
        ("Date Published", data.get("datePublished")),
        ("License", data.get("license")),
        ("URL", data.get("url")),
        ("Citation", data.get("citeAs")),
        ("Conforms To", data.get("conformsTo")),
    ]

    for label, value in summary_fields:
        if has_content(value):
            lines.append(f"**{label}:** {format_value(value)}")

    return "\n".join(lines)


def render_people_section(data):
    role_candidates = ["creator", "author", "publisher", "contributor"]
    blocks = []

    for role in role_candidates:
        values = ensure_list(data.get(role))
        if not values:
            continue

        lines = []
        for item in values:
            lines.append(format_agent(item))

        if lines:
            blocks.append(f"### {prettify_term(role)}\n" + "\n".join(lines))

    if not blocks:
        return ""

    return "## People and Organisations\n\n" + "\n\n".join(blocks)


def render_distribution_section(data):
    distribution = ensure_list(data.get("distribution"))
    if not distribution:
        return ""

    lines = ["## File Structure", ""]
    lines.append("| ID | Name | Type | Format | Location / Pattern | Description |")
    lines.append("|---|---|---|---|---|---|")

    rows = []
    for item in distribution:
        if not isinstance(item, dict):
            continue

        item_id = item.get("@id", "")
        name = item.get("name", "")
        item_type = describe_type(item.get("@type"))
        encoding_format = item.get("encodingFormat", "")
        location = item.get("contentUrl") or item.get("includes") or format_contained_in(item.get("containedIn"))
        description = item.get("description", "No description available.")

        rows.append(
            (
                str(item_id or ""),
                str(name or ""),
                str(item_type or ""),
                str(encoding_format or ""),
                str(location or ""),
                str(description or ""),
            )
        )

    rows.sort(key=lambda row: (row[2].lower(), row[1].lower(), row[0].lower()))

    for row in rows:
        safe = [escape_markdown_table_cell(value) for value in row]
        lines.append(
            f"| {safe[0]} | {safe[1]} | {safe[2]} | {safe[3]} | {safe[4]} | {safe[5]} |"
        )

    return "\n".join(lines)


def render_recordset_section(data):
    recordsets = ensure_list(data.get("recordSet"))
    if not recordsets:
        return ""

    blocks = ["## Record Sets"]

    for recordset in recordsets:
        if not isinstance(recordset, dict):
            continue

        title = recordset.get("name") or recordset.get("@id") or "Unnamed record set"
        lines = [f"### {title}", ""]

        summary_rows = []
        summary_fields = [
            ("ID", recordset.get("@id")),
            ("Description", recordset.get("description")),
            ("Key", format_key(recordset.get("key"))),
            ("Inline Data Rows", count_inline_rows(recordset.get("data"))),
            ("Fields", len([field for field in ensure_list(recordset.get("field")) if isinstance(field, dict)])),
        ]

        for label, value in summary_fields:
            if has_content(value):
                summary_rows.append((label, str(value)))

        if summary_rows:
            lines.append("| Field | Value |")
            lines.append("|---|---|")
            for label, value in summary_rows:
                lines.append(
                    f"| {escape_markdown_table_cell(label)} | {escape_markdown_table_cell(value)} |"
                )
            lines.append("")

        field_rows = collect_field_rows(recordset)
        if field_rows:
            lines.append("#### Fields")
            lines.append("")
            lines.append("| ID | Name | Data Type | Source | Description |")
            lines.append("|---|---|---|---|---|")
            for row in field_rows:
                safe = [escape_markdown_table_cell(value) for value in row]
                lines.append(f"| {safe[0]} | {safe[1]} | {safe[2]} | {safe[3]} | {safe[4]} |")

        blocks.append("\n".join(lines).strip())

    return "\n\n".join(blocks)


def render_grouped_rai_sections(data):
    rai_fields = collect_rai_fields(data)
    if not rai_fields:
        return ""

    section_definitions = [
        (
            "Data Collection",
            [
                "rai:dataCollection",
                "rai:dataCollectionType",
                "rai:dataCollectionRawData",
                "rai:dataPreprocessingProtocol",
                "rai:dataManipulationProtocol",
                "rai:dataCollectionMissingData",
            ],
        ),
        (
            "Data Annotation",
            [
                "rai:dataAnnotationProtocol",
                "rai:dataAnnotationPlatform",
                "rai:machineAnnotationTools",
                "rai:annotationsPerItem",
                "rai:annotatorDemographics",
                "rai:dataAnnotationAnalysis",
            ],
        ),
        (
            "Data Use and Purpose",
            [
                "rai:dataUseCases",
            ],
        ),
        (
            "Data Limitations and Biases",
            [
                "rai:dataBiases",
                "rai:dataLimitations",
                "rai:dataImputationProtocol",
            ],
        ),
        (
            "Personal and Social Considerations",
            [
                "rai:personalSensitiveInformation",
                "rai:dataSocialImpact",
            ],
        ),
        (
            "Data Release and Maintenance",
            [
                "rai:dataReleaseMaintenancePlan",
            ],
        ),
    ]

    sections = []
    used_keys = set()

    for heading, keys in section_definitions:
        block = render_rai_group(heading, keys, rai_fields)
        if block:
            sections.append(block)
            used_keys.update(key for key in keys if key in rai_fields)

    remaining_keys = [key for key in sorted(rai_fields.keys(), key=str.lower) if key not in used_keys]
    if remaining_keys:
        block = render_rai_group("Additional Croissant RAI Fields", remaining_keys, rai_fields)
        if block:
            sections.append(block)

    return "\n\n".join(sections)


def render_rai_group(heading, keys, rai_fields):
    items = []
    for key in keys:
        if key in rai_fields and has_content(rai_fields[key]):
            items.append((humanise_rai_label(key), rai_fields[key]))

    if not items:
        return ""

    lines = [f"## {heading}", ""]
    for label, value in items:
        lines.append(f"### {label}")
        lines.append("")
        lines.append(format_block_value(value))
        lines.append("")

    return "\n".join(lines).strip()


def render_metadata_notes(data):
    context = data.get("@context")
    distribution = ensure_list(data.get("distribution"))
    recordsets = ensure_list(data.get("recordSet"))

    lines = ["## Metadata Notes", ""]
    if has_content(context):
        if isinstance(context, dict):
            lines.append(f"- **JSON-LD Context Keys:** {len(context.keys())}")
        else:
            lines.append(f"- **JSON-LD Context:** {format_value(context)}")
    if has_content(data.get("conformsTo")):
        lines.append(f"- **Conforms To:** {format_value(data.get('conformsTo'))}")
    lines.append(f"- **Distribution Entries:** {len([item for item in distribution if isinstance(item, dict)])}")
    lines.append(f"- **Record Sets:** {len([item for item in recordsets if isinstance(item, dict)])}")
    lines.append("- **Generated By:** This README was generated automatically from the Croissant JSON metadata loaded in the GUI.")

    return "\n".join(lines)


def collect_rai_fields(data):
    return {
        key: value
        for key, value in data.items()
        if isinstance(key, str) and key.startswith("rai:") and has_content(value)
    }


def collect_field_rows(recordset):
    rows = []
    fields = ensure_list(recordset.get("field"))

    for field in fields:
        if not isinstance(field, dict):
            continue

        field_id = field.get("@id", "")
        name = field.get("name", "")
        data_type = describe_type(field.get("dataType"))
        source = describe_source(field.get("source"))
        description = field.get("description", "")

        rows.append((
            str(field_id or ""),
            str(name or ""),
            str(data_type or ""),
            str(source or ""),
            str(description or ""),
        ))

    rows.sort(key=lambda row: (row[1].lower(), row[0].lower()))
    return rows


def describe_source(source):
    if not isinstance(source, dict):
        return ""

    parts = []

    file_set = source.get("fileSet")
    if isinstance(file_set, dict) and file_set.get("@id"):
        parts.append(f"fileSet: {file_set['@id']}")
    elif isinstance(file_set, str):
        parts.append(f"fileSet: {file_set}")

    extract = source.get("extract")
    if isinstance(extract, dict):
        if extract.get("fileProperty"):
            parts.append(f"fileProperty: {extract['fileProperty']}")
        if extract.get("jsonPath"):
            parts.append(f"jsonPath: {extract['jsonPath']}")

    transform = source.get("transform")
    if isinstance(transform, dict) and transform.get("regex"):
        parts.append(f"regex: {transform['regex']}")

    return "; ".join(parts)


def format_contained_in(value):
    items = []
    for item in ensure_list(value):
        if isinstance(item, dict) and item.get("@id"):
            items.append(str(item.get("@id")))
        elif item not in (None, ""):
            items.append(str(item))
    return ", ".join(items)


def format_key(value):
    if not has_content(value):
        return ""

    if isinstance(value, list):
        return ", ".join(format_key(item) for item in value if has_content(item))

    if isinstance(value, dict):
        if value.get("@id"):
            return str(value.get("@id"))
        return json.dumps(value, ensure_ascii=False)

    return str(value)


def count_inline_rows(value):
    if isinstance(value, list):
        return len(value)
    if not has_content(value):
        return ""
    return 1


def describe_type(type_value):
    if isinstance(type_value, list):
        return ", ".join(prettify_term(v) for v in type_value if has_content(v))
    if has_content(type_value):
        return prettify_term(type_value)
    return ""


def format_agent(value):
    if isinstance(value, dict):
        name = value.get("name") or value.get("@id") or "Unnamed agent"
        parts = [f"- **{name}**"]

        entity_type = describe_type(value.get("@type"))
        if entity_type:
            parts.append(f" ({entity_type})")

        if has_content(value.get("affiliation")):
            parts.append(f" — affiliation: {format_value(value.get('affiliation'))}")

        identifier = value.get("url") or value.get("@id")
        if isinstance(identifier, str) and identifier.startswith(("http://", "https://")):
            parts.append(f" — {markdown_link_if_url(identifier, identifier)}")

        return "".join(parts)

    return f"- {format_value(value)}"


def ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def has_content(value):
    return value not in (None, "", [], {})


def format_value(value):
    if isinstance(value, list):
        return ", ".join(format_value(v) for v in value if has_content(v))

    if isinstance(value, dict):
        if "@id" in value and len(value) == 1:
            return markdown_link_if_url(value["@id"], value["@id"])
        if "name" in value and len(value) <= 4:
            label = value.get("name")
            identifier = value.get("url") or value.get("@id")
            if identifier:
                return markdown_link_if_url(label, identifier)
            return str(label)
        return json.dumps(value, ensure_ascii=False)

    if isinstance(value, str):
        return markdown_link_if_url(value, value)

    return str(value)


def format_block_value(value):
    if isinstance(value, list):
        cleaned = [item for item in value if has_content(item)]
        if not cleaned:
            return ""
        if all(not isinstance(item, (dict, list)) for item in cleaned):
            return "\n".join(f"- {format_value(item)}" for item in cleaned)
        return "\n".join(f"- {format_value(item)}" for item in cleaned)

    if isinstance(value, dict):
        simple_items = []
        for key, item in value.items():
            if has_content(item):
                simple_items.append(f"- **{prettify_term(key)}:** {format_value(item)}")
        return "\n".join(simple_items) if simple_items else json.dumps(value, ensure_ascii=False, indent=2)

    return format_value(value)


def humanise_rai_label(key):
    label = key.replace("rai:", "")
    label = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", label)
    label = label.replace("  ", " ").strip()
    if not label:
        return key
    return label[:1].upper() + label[1:]


def markdown_link_if_url(label, url):
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        safe_label = str(label) if label not in (None, "") else url
        return f"[{safe_label}]({url})"
    return str(label)


def escape_markdown_table_cell(value):
    return str(value).replace("\n", " ").replace("|", "\\|").strip()


def prettify_term(term):
    if not isinstance(term, str):
        return str(term)

    if term.startswith("http://") or term.startswith("https://"):
        final = term.rstrip("/").split("/")[-1] or term
        term = final.split("#")[-1]

    plain = term.replace("_", " ")
    plain = plain.replace("@", "")
    plain = plain.replace("sc:", "")
    plain = plain.replace("cr:", "")
    plain = plain.replace("rai:", "RAI ")
    plain = plain.replace("wd:", "")
    plain = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", plain)
    plain = re.sub(r"\s+", " ", plain).strip()

    if not plain:
        return ""

    return plain[:1].upper() + plain[1:]


def main():
    app = QApplication(sys.argv)
    window = CroissantReadmeBuilder()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
