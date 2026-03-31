#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
File: croissant_to_RO-Crate_gui.py
Author: Matthew Partridge
Created: 2026-03-06
Description: TBD
Version: 0.4
"""


from __future__ import annotations

import json
import re
import sys
from collections import OrderedDict
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)


ROCRATE_CONTEXT = [
    "https://w3id.org/ro/crate/1.1/context",
    {
        "croissant": "http://mlcommons.org/croissant/",
        "rai": "http://mlcommons.org/croissant/RAI/",
        "dct": "http://purl.org/dc/terms/",
    },
]

ROCRATE_SPEC_ID = "https://w3id.org/ro/crate/1.1"
ROCRATE_METADATA_ID = "ro-crate-metadata.json"


class AgentRow(QWidget):
    def __init__(self, role_label: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.role_label = role_label

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["Person", "Organization"])
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(f"{role_label} name")
        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("Optional @id / URL")
        self.remove_button = QPushButton("Remove")

        layout.addWidget(self.type_combo, 0)
        layout.addWidget(self.name_edit, 1)
        layout.addWidget(self.id_edit, 1)
        layout.addWidget(self.remove_button, 0)

    def set_values(self, name: str = "", agent_type: str = "Person", agent_id: str = ""):
        self.name_edit.setText(name)
        index = self.type_combo.findText(agent_type)
        self.type_combo.setCurrentIndex(index if index >= 0 else 0)
        self.id_edit.setText(agent_id)

    def to_dict(self) -> Optional[Dict[str, str]]:
        name = self.name_edit.text().strip()
        agent_id = self.id_edit.text().strip()
        if not name and not agent_id:
            return None
        return {
            "type": self.type_combo.currentText(),
            "name": name,
            "id": agent_id,
        }


class AgentListWidget(QWidget):
    def __init__(self, title: str, default_type: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.title = title
        self.default_type = default_type
        self.rows: List[AgentRow] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(4)
        self.rows_layout.addStretch()

        layout.addWidget(self.rows_container)

        button_row = QHBoxLayout()
        self.add_person_button = QPushButton("Add Person")
        self.add_org_button = QPushButton("Add Organisation")
        self.clear_button = QPushButton("Clear")
        self.add_person_button.clicked.connect(lambda: self.add_row(agent_type="Person"))
        self.add_org_button.clicked.connect(lambda: self.add_row(agent_type="Organization"))
        self.clear_button.clicked.connect(self.clear_rows)
        button_row.addWidget(self.add_person_button)
        button_row.addWidget(self.add_org_button)
        button_row.addWidget(self.clear_button)
        button_row.addStretch()
        layout.addLayout(button_row)

    def _remove_stretch(self):
        count = self.rows_layout.count()
        if count > 0:
            last_item = self.rows_layout.itemAt(count - 1)
            if last_item and last_item.spacerItem():
                self.rows_layout.takeAt(count - 1)

    def _add_stretch(self):
        self.rows_layout.addStretch()

    def add_row(self, name: str = "", agent_type: Optional[str] = None, agent_id: str = ""):
        self._remove_stretch()
        row = AgentRow(self.title)
        row.set_values(name=name, agent_type=agent_type or self.default_type, agent_id=agent_id)
        row.remove_button.clicked.connect(lambda: self.remove_row(row))
        self.rows.append(row)
        self.rows_layout.addWidget(row)
        self._add_stretch()

    def remove_row(self, row: AgentRow):
        if row in self.rows:
            self.rows.remove(row)
            row.setParent(None)
            row.deleteLater()

    def clear_rows(self):
        for row in self.rows[:]:
            self.remove_row(row)

    def set_agents(self, agents: List[Dict[str, str]]):
        self.clear_rows()
        for agent in agents:
            self.add_row(
                name=agent.get("name", ""),
                agent_type=agent.get("type") or self.default_type,
                agent_id=agent.get("id", ""),
            )

    def get_agents(self) -> List[Dict[str, str]]:
        agents: List[Dict[str, str]] = []
        for row in self.rows:
            item = row.to_dict()
            if item:
                agents.append(item)
        return agents


class CroissantToROCrateBuilder(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Croissant → RO-Crate JSON Generator")
        self.resize(1580, 900)

        self.current_croissant_path: Optional[str] = None
        self.current_output_path: Optional[str] = None
        self.croissant_data: Optional[dict] = None
        self.last_generated_rocrate: Optional[dict] = None
        self.current_file_entities: List[Dict[str, str]] = []

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        button_row = QHBoxLayout()
        self.load_button = QPushButton("Load Croissant JSON")
        self.save_button = QPushButton("Save RO-Crate JSON…")
        self.load_button.clicked.connect(self.load_croissant)
        self.save_button.clicked.connect(self.save_rocrate)
        self.save_button.setEnabled(False)

        button_row.addWidget(self.load_button)
        button_row.addWidget(self.save_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter, 1)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("Loaded Croissant JSON"))
        self.croissant_view = QPlainTextEdit()
        self.croissant_view.setReadOnly(True)
        self.croissant_view.setPlaceholderText("Load a Croissant JSON file.")
        left_layout.addWidget(self.croissant_view)
        splitter.addWidget(left_panel)

        middle_panel = QWidget()
        middle_layout = QVBoxLayout(middle_panel)
        middle_layout.addWidget(QLabel("Mapped RO-Crate fields"))

        form_container = QWidget()
        self.form_layout = QFormLayout(form_container)
        self.form_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.in_name = QLineEdit()
        self.in_description = QPlainTextEdit()
        self.in_description.setFixedHeight(100)
        self.in_license = QLineEdit()
        self.in_url = QLineEdit()
        self.in_identifier = QLineEdit()
        self.in_version = QLineEdit()
        self.in_keywords = QLineEdit()
        self.creators_widget = AgentListWidget("Creator", "Person")
        self.publishers_widget = AgentListWidget("Publisher", "Organization")
        self.in_date_created = QLineEdit()
        self.in_date_modified = QLineEdit()
        self.in_date_published = QLineEdit()
        self.in_main_entity_name = QLineEdit()
        self.in_main_entity_id = QLineEdit()
        self.in_main_entity_format = QLineEdit()
        self.in_main_entity_description = QPlainTextEdit()
        self.in_main_entity_description.setFixedHeight(80)

        self.form_layout.addRow("Name", self.in_name)
        self.form_layout.addRow("Description", self.in_description)
        self.form_layout.addRow("License", self.in_license)
        self.form_layout.addRow("URL", self.in_url)
        self.form_layout.addRow("Identifier", self.in_identifier)
        self.form_layout.addRow("Version", self.in_version)
        self.form_layout.addRow("Keywords", self.in_keywords)
        self.form_layout.addRow("Creators", self.creators_widget)
        self.form_layout.addRow("Publishers", self.publishers_widget)
        self.form_layout.addRow("Date created", self.in_date_created)
        self.form_layout.addRow("Date modified", self.in_date_modified)
        self.form_layout.addRow("Date published", self.in_date_published)
        self.form_layout.addRow("Main entity name", self.in_main_entity_name)
        self.form_layout.addRow("Main entity @id", self.in_main_entity_id)
        self.form_layout.addRow("Main entity format", self.in_main_entity_format)
        self.form_layout.addRow("Main entity description", self.in_main_entity_description)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_container)
        middle_layout.addWidget(scroll, 1)

        self.regenerate_button = QPushButton("Regenerate RO-Crate")
        self.regenerate_button.clicked.connect(self.regenerate_rocrate)
        self.regenerate_button.setEnabled(False)
        middle_layout.addWidget(self.regenerate_button)

        splitter.addWidget(middle_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(QLabel("Generated RO-Crate JSON"))
        self.rocrate_view = QPlainTextEdit()
        self.rocrate_view.setReadOnly(True)
        self.rocrate_view.setPlaceholderText("Generated RO-Crate JSON will appear here.")
        right_layout.addWidget(self.rocrate_view)
        splitter.addWidget(right_panel)

        splitter.setSizes([470, 540, 570])

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

    def _clear_form(self):
        for widget in [
            self.in_name,
            self.in_license,
            self.in_url,
            self.in_identifier,
            self.in_version,
            self.in_keywords,
            self.in_date_created,
            self.in_date_modified,
            self.in_date_published,
            self.in_main_entity_name,
            self.in_main_entity_id,
            self.in_main_entity_format,
        ]:
            widget.clear()

        self.in_description.clear()
        self.in_main_entity_description.clear()
        self.creators_widget.clear_rows()
        self.publishers_widget.clear_rows()
        self.current_file_entities = []

    def load_croissant(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Croissant JSON",
            "",
            "JSON files (*.json);;All files (*)",
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception as exc:
            QMessageBox.critical(self, "Load failed", f"Could not load Croissant JSON.\n\n{exc}")
            return

        if not isinstance(data, dict):
            QMessageBox.critical(self, "Load failed", "The Croissant JSON root must be an object.")
            return

        self.current_croissant_path = file_path
        self.current_output_path = str(Path(file_path).with_name("ro-crate-metadata.json"))
        self.croissant_data = data
        self.croissant_view.setPlainText(json.dumps(data, indent=2, ensure_ascii=False))

        self._clear_form()
        self._populate_form_from_croissant(data)
        self.regenerate_button.setEnabled(True)
        self.save_button.setEnabled(True)
        self.regenerate_rocrate()
        self.statusBar().showMessage(f"Loaded {file_path}")

    def _populate_form_from_croissant(self, data: dict):
        self.in_name.setText(self._first_string(data.get("name"), fallback=""))
        self.in_description.setPlainText(self._first_string(data.get("description"), fallback=""))
        self.in_license.setText(self._extract_reference(data.get("license")))
        self.in_url.setText(self._first_string(data.get("url"), fallback=""))
        self.in_identifier.setText(self._extract_reference(data.get("identifier")))
        self.in_version.setText(self._first_string(data.get("version"), fallback=""))
        self.in_keywords.setText(self._format_keywords(data.get("keywords")))
        self.creators_widget.set_agents(self._extract_agents(data.get("creator"), default_type="Person"))
        self.publishers_widget.set_agents(self._extract_agents(data.get("publisher"), default_type="Organization"))
        self.in_date_created.setText(self._first_string(data.get("dateCreated"), fallback=""))
        self.in_date_modified.setText(self._first_string(data.get("dateModified"), fallback=""))
        self.in_date_published.setText(self._first_string(data.get("datePublished"), fallback=""))

        self.current_file_entities = self._extract_file_entities(data)
        distribution = self.current_file_entities[0] if self.current_file_entities else {}
        self.in_main_entity_name.setText(self._first_string(distribution.get("name"), fallback=""))
        self.in_main_entity_id.setText(self._extract_distribution_id(distribution))
        self.in_main_entity_format.setText(
            self._first_string(distribution.get("encodingFormat"), fallback="")
            or self._first_string(distribution.get("format"), fallback="")
        )
        self.in_main_entity_description.setPlainText(
            self._first_string(distribution.get("description"), fallback="")
        )

    def regenerate_rocrate(self):
        try:
            rocrate = self._build_rocrate_from_form()
        except Exception as exc:
            QMessageBox.critical(self, "Generation failed", f"Could not generate RO-Crate JSON.\n\n{exc}")
            return

        self.last_generated_rocrate = rocrate
        self.rocrate_view.setPlainText(json.dumps(rocrate, indent=2, ensure_ascii=False))
        self.statusBar().showMessage("RO-Crate regenerated")

    def save_rocrate(self):
        if not self.last_generated_rocrate:
            QMessageBox.information(self, "Nothing to save", "There is no generated RO-Crate JSON to save.")
            return

        default_name = self.current_output_path or "ro-crate-metadata.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save RO-Crate JSON",
            default_name,
            "JSON files (*.json);;All files (*)",
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(self.last_generated_rocrate, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", f"Could not save RO-Crate JSON.\n\n{exc}")
            return

        self.current_output_path = file_path
        self.statusBar().showMessage(f"Saved {file_path}")

    def _build_rocrate_from_form(self) -> dict:
        root_dataset: Dict[str, Any] = OrderedDict()
        root_dataset["@id"] = "./"
        root_dataset["@type"] = "Dataset"

        self._set_if_text(root_dataset, "name", self.in_name.text())
        self._set_if_text(root_dataset, "description", self.in_description.toPlainText())
        self._set_if_text(root_dataset, "license", self.in_license.text())
        self._set_if_text(root_dataset, "url", self.in_url.text())
        self._set_if_text(root_dataset, "identifier", self.in_identifier.text())
        self._set_if_text(root_dataset, "version", self.in_version.text())
        self._set_if_keywords(root_dataset, "keywords", self.in_keywords.text())
        self._set_if_text(root_dataset, "dateCreated", self.in_date_created.text())
        self._set_if_text(root_dataset, "dateModified", self.in_date_modified.text())
        self._set_if_text(root_dataset, "datePublished", self.in_date_published.text())

        graph: List[Dict[str, Any]] = []
        metadata_entity = OrderedDict([
            ("@id", ROCRATE_METADATA_ID),
            ("@type", "CreativeWork"),
            ("conformsTo", {"@id": ROCRATE_SPEC_ID}),
            ("about", {"@id": "./"}),
        ])
        graph.append(metadata_entity)

        linked_entities: List[Dict[str, Any]] = []

        creator_refs = self._build_agent_entities(
            self.creators_widget.get_agents(),
            base_id="creator",
            default_type="Person",
            linked_entities=linked_entities,
        )
        if creator_refs:
            root_dataset["creator"] = creator_refs[0] if len(creator_refs) == 1 else creator_refs

        publisher_refs = self._build_agent_entities(
            self.publishers_widget.get_agents(),
            base_id="publisher",
            default_type="Organization",
            linked_entities=linked_entities,
        )
        if publisher_refs:
            root_dataset["publisher"] = publisher_refs[0] if len(publisher_refs) == 1 else publisher_refs

        file_entities = self._build_file_entities_from_form()
        if file_entities:
            linked_entities.extend(file_entities)
            root_dataset["mainEntity"] = {"@id": file_entities[0]["@id"]}
            root_dataset["hasPart"] = [{"@id": entity["@id"]} for entity in file_entities]

        graph.append(root_dataset)
        graph.extend(linked_entities)

        return OrderedDict([
            ("@context", ROCRATE_CONTEXT),
            ("@graph", graph),
        ])

    @staticmethod
    def _build_agent_entities(
        agents: List[Dict[str, str]],
        base_id: str,
        default_type: str,
        linked_entities: List[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        refs: List[Dict[str, str]] = []
        seen_ids = set()
        counter = 1

        for agent in agents:
            name = agent.get("name", "").strip()
            agent_id = agent.get("id", "").strip()
            agent_type = agent.get("type") or default_type

            if not name and not agent_id:
                continue

            if not agent_id:
                safe_name = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
                suffix = safe_name or str(counter)
                candidate_id = f"#{base_id}-{suffix}"
                while candidate_id in seen_ids:
                    counter += 1
                    candidate_id = f"#{base_id}-{suffix}-{counter}"
                agent_id = candidate_id
            seen_ids.add(agent_id)
            counter += 1

            entity = OrderedDict()
            entity["@id"] = agent_id
            entity["@type"] = agent_type
            if name:
                entity["name"] = name
            linked_entities.append(entity)
            refs.append({"@id": agent_id})

        return refs

    @staticmethod
    def _set_if_text(target: Dict[str, Any], key: str, value: str):
        text = value.strip()
        if text:
            target[key] = text

    @staticmethod
    def _set_if_keywords(target: Dict[str, Any], key: str, value: str):
        items = [part.strip() for part in value.split(",") if part.strip()]
        if items:
            target[key] = items

    @staticmethod
    def _first_string(value: Any, fallback: str = "") -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    return item
                if isinstance(item, dict):
                    nested = item.get("name") or item.get("@id") or item.get("url")
                    if isinstance(nested, str) and nested.strip():
                        return nested
        if isinstance(value, dict):
            for key in ("name", "@id", "url", "value"):
                nested = value.get(key)
                if isinstance(nested, str) and nested.strip():
                    return nested
        return fallback

    @staticmethod
    def _extract_reference(value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            for key in ("@id", "url", "name"):
                nested = value.get(key)
                if isinstance(nested, str):
                    return nested
        if isinstance(value, list):
            parts = []
            for item in value:
                text = CroissantToROCrateBuilder._extract_reference(item)
                if text:
                    parts.append(text)
            return ", ".join(parts)
        return ""

    @staticmethod
    def _format_keywords(value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            parts = []
            for item in value:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("name") or item.get("@id")
                    if isinstance(text, str):
                        parts.append(text)
            return ", ".join(parts)
        return ""

    @staticmethod
    def _extract_agents(value: Any, default_type: str = "Person") -> List[Dict[str, str]]:
        agents: List[Dict[str, str]] = []

        def add_agent(item: Any):
            if isinstance(item, str):
                if item.strip():
                    agents.append({"name": item.strip(), "type": default_type, "id": ""})
                return

            if not isinstance(item, dict):
                return

            agent_type = item.get("@type") or item.get("type") or default_type
            if isinstance(agent_type, list):
                agent_type = next((x for x in agent_type if isinstance(x, str) and x in ("Person", "Organization")), default_type)
            if agent_type not in ("Person", "Organization"):
                if any(term in str(agent_type).lower() for term in ["org", "institution", "publisher"]):
                    agent_type = "Organization"
                else:
                    agent_type = default_type

            name = ""
            for key in ("name", "legalName", "alternateName"):
                candidate = item.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    name = candidate.strip()
                    break

            agent_id = ""
            for key in ("@id", "id", "url"):
                candidate = item.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    agent_id = candidate.strip()
                    break

            if name or agent_id:
                agents.append({"name": name, "type": agent_type, "id": agent_id})

        if isinstance(value, list):
            for item in value:
                add_agent(item)
        else:
            add_agent(value)

        return agents

    @staticmethod
    def _normalise_file_candidate(candidate: dict) -> Optional[Dict[str, str]]:
        if not isinstance(candidate, dict):
            return None

        identifier = ""
        for key in ("contentUrl", "@id", "id", "path", "name"):
            value = candidate.get(key)
            if isinstance(value, str) and value.strip():
                identifier = value.strip()
                break

        name = CroissantToROCrateBuilder._first_string(candidate.get("name"), fallback="")
        description = CroissantToROCrateBuilder._first_string(candidate.get("description"), fallback="")
        encoding_format = (
            CroissantToROCrateBuilder._first_string(candidate.get("encodingFormat"), fallback="")
            or CroissantToROCrateBuilder._first_string(candidate.get("format"), fallback="")
        )

        if not any([identifier, name, description, encoding_format]):
            return None

        return {
            "id": identifier,
            "name": name,
            "description": description,
            "format": encoding_format,
        }

    @staticmethod
    def _extract_file_entities(data: dict) -> List[Dict[str, str]]:
        files: List[Dict[str, str]] = []
        seen_ids = set()

        def add_candidate(item: Any):
            candidate = CroissantToROCrateBuilder._normalise_file_candidate(item)
            if not candidate:
                return
            unique_key = candidate["id"] or f'{candidate["name"]}|{candidate["description"]}|{candidate["format"]}'
            if unique_key in seen_ids:
                return
            seen_ids.add(unique_key)
            files.append(candidate)

        for key in ("distribution", "fileObject", "fileSet"):
            value = data.get(key)
            if isinstance(value, dict):
                add_candidate(value)
            elif isinstance(value, list):
                for item in value:
                    add_candidate(item)

        record_set = data.get("recordSet")
        if isinstance(record_set, dict):
            source = record_set.get("source")
            if isinstance(source, list):
                for item in source:
                    add_candidate(item)
            else:
                add_candidate(source)
        elif isinstance(record_set, list):
            for item in record_set:
                if isinstance(item, dict):
                    source = item.get("source")
                    if isinstance(source, list):
                        for source_item in source:
                            add_candidate(source_item)
                    else:
                        add_candidate(source)

        return files

    @staticmethod
    def _extract_distribution_id(distribution: Any) -> str:
        if not isinstance(distribution, dict):
            return ""

        for key in ("id", "contentUrl", "@id", "path", "name"):
            value = distribution.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        return ""


    def _build_file_entities_from_form(self) -> List[Dict[str, Any]]:
        file_entities: List[Dict[str, Any]] = []
        seen_ids = set()

        primary = {
            "id": self.in_main_entity_id.text().strip(),
            "name": self.in_main_entity_name.text().strip(),
            "description": self.in_main_entity_description.toPlainText().strip(),
            "format": self.in_main_entity_format.text().strip(),
        }

        combined_files: List[Dict[str, str]] = []
        if any(primary.values()):
            combined_files.append(primary)

        for item in self.current_file_entities:
            same_as_primary = (
                item.get("id", "") == primary.get("id", "")
                and item.get("name", "") == primary.get("name", "")
                and item.get("description", "") == primary.get("description", "")
                and item.get("format", "") == primary.get("format", "")
            )
            if not same_as_primary:
                combined_files.append(item)

        counter = 1
        for item in combined_files:
            identifier = (item.get("id") or "").strip()
            name = (item.get("name") or "").strip()
            description = (item.get("description") or "").strip()
            encoding_format = (item.get("format") or "").strip()

            if not any([identifier, name, description, encoding_format]):
                continue

            if not identifier:
                safe_name = re.sub(r"[^a-zA-Z0-9._/-]+", "-", name).strip("-")
                identifier = safe_name or f"data/file-{counter}"
            if identifier in seen_ids:
                counter += 1
                continue
            seen_ids.add(identifier)
            counter += 1

            entity = OrderedDict()
            entity["@id"] = identifier
            entity["@type"] = "File"
            if name:
                entity["name"] = name
            if description:
                entity["description"] = description
            if encoding_format:
                entity["encodingFormat"] = encoding_format
            file_entities.append(entity)

        return file_entities


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CroissantToROCrateBuilder()
    window.show()
    sys.exit(app.exec_())
