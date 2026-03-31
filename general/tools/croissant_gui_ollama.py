#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
File: croissant_gui_ollama.py
Author: Matthew Partridge
Created: 2026-03-06
Description: TBD
Version: 0.1
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

import pandas as pd
from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QScrollArea,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    import ollama
except Exception:
    ollama = None

# Croissant 1.0 JSON-LD context
CROISSANT_CONTEXT = {
    "@language": "en",
    "@vocab": "https://schema.org/",
    "sc": "https://schema.org/",
    "cr": "http://mlcommons.org/croissant/",
    "rai": "http://mlcommons.org/croissant/RAI/",
    "dct": "http://purl.org/dc/terms/",
    "citeAs": "cr:citeAs",
    "column": "cr:column",
    "conformsTo": "dct:conformsTo",
    "data": {"@id": "cr:data", "@type": "@json"},
    "dataType": {"@id": "cr:dataType", "@type": "@vocab"},
    "examples": {"@id": "cr:examples", "@type": "@json"},
    "extract": "cr:extract",
    "field": "cr:field",
    "fileProperty": "cr:fileProperty",
    "fileObject": "cr:fileObject",
    "fileSet": "cr:fileSet",
    "format": "cr:format",
    "includes": "cr:includes",
    "isLiveDataset": "cr:isLiveDataset",
    "jsonPath": "cr:jsonPath",
    "key": "cr:key",
    "md5": "cr:md5",
    "parentField": "cr:parentField",
    "path": "cr:path",
    "recordSet": "cr:recordSet",
    "references": "cr:references",
    "regex": "cr:regex",
    "repeated": "cr:repeated",
    "replace": "cr:replace",
    "separator": "cr:separator",
    "source": "cr:source",
    "subField": "cr:subField",
    "transform": "cr:transform",
}

SCHEMA_DATATYPES = ["sc:Text", "sc:Boolean", "sc:Integer", "sc:Number", "sc:Date", "sc:DateTime"]
MATCHER_VERSION = "MATCHING-VOCAB-LEAN-SINGLE-PASS-OLLAMA-GEMMA3-4B-PROMPTLOG-FIXED-2026-03-06"



def sha256_file(path: str, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def guess_datatype(series: pd.Series) -> str:
    try:
        if pd.api.types.is_bool_dtype(series):
            return "sc:Boolean"
        if pd.api.types.is_integer_dtype(series):
            return "sc:Integer"
        if pd.api.types.is_float_dtype(series):
            return "sc:Number"

        sample = series.dropna().astype(str).head(50)
        if len(sample) > 0:
            parsed = pd.to_datetime(sample, errors="coerce", utc=False)
            ok = parsed.notna().sum()
            if ok >= max(3, int(0.8 * len(sample))):
                if (parsed.dt.hour.fillna(0) != 0).any() or (parsed.dt.minute.fillna(0) != 0).any():
                    return "sc:DateTime"
                return "sc:Date"
    except Exception:
        pass
    return "sc:Text"


def split_camel_case(text: str) -> str:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text or "")
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)
    return text


def extract_header_core_and_units(text: str) -> Tuple[str, List[str]]:
    raw = split_camel_case(text or "")
    unit_parts: List[str] = []

    for inside in re.findall(r"\(([^)]*)\)", raw):
        inside = inside.strip()
        if inside:
            unit_parts.append(inside)
    raw = re.sub(r"\([^)]*\)", " ", raw)

    pieces = [p.strip() for p in re.split(r"[/|]", text or "") if p.strip()]
    if len(pieces) > 1:
        unit_parts.extend(pieces[1:])

    return raw, unit_parts


def normalise_text(text: str) -> str:
    core, _ = extract_header_core_and_units(text)
    t = (core or "").strip()
    t = split_camel_case(t)
    t = t.lower()
    t = t.replace("μ", "u").replace("°", " ")
    t = t.replace("-", " ").replace("_", " ").replace("/", " ")
    t = re.sub(r"[^a-z0-9]+", " ", t)
    t = re.sub(r"\btemp\b", "temperature", t)
    t = re.sub(r"\bpres\b", "pressure", t)
    t = re.sub(r"\bconc\b", "concentration", t)
    t = re.sub(r"\brefs?\b", "reference", t)
    t = re.sub(r"\bcitations?\b", "citation", t)
    t = re.sub(r"\bsrc\b", "source", t)
    t = re.sub(r"\bvers\b", "version", t)
    return re.sub(r"\s+", " ", t).strip()


def normalise_unit_text(text: str) -> str:
    t = split_camel_case(text or "")
    t = t.lower().replace("μ", "u").replace("°", " ")
    t = t.replace("-", " ").replace("_", " ").replace("/", " per ")
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def tokenise(text: str) -> List[str]:
    return [tok for tok in normalise_text(text).split() if tok]


def unit_tokens(text: str) -> List[str]:
    _, units = extract_header_core_and_units(text)
    joined = " ".join(units)
    return [tok for tok in normalise_unit_text(joined).split() if tok]


@dataclass
class FieldMeta:
    name: str
    data_type: str = "sc:Text"
    description: str = ""



@dataclass
class VocabEntry:
    vocab_id: str
    section: str
    label: str
    definition: str
    value_type: str = ""
    category: str = ""
    source_token: str = ""
    possible_headings: List[str] = None
    allowed_units: List[str] = None
    expected_unit_type: str = ""

    @property
    def search_blob(self) -> str:
        heading_blob = " ".join(self.possible_headings or [])
        units_blob = " ".join(self.allowed_units or [])
        return f"{self.vocab_id} {self.label} {self.definition} {self.value_type} {self.category} {self.source_token} {heading_blob} {units_blob}"


class PandasTableModel(QAbstractTableModel):
    def __init__(self, df: pd.DataFrame):
        super().__init__()
        self._df = df

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._df.index)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._df.columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        if role in (Qt.DisplayRole, Qt.EditRole):
            val = self._df.iat[index.row(), index.column()]
            if pd.isna(val):
                return ""
            return str(val)
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return str(self._df.columns[section])
        return str(section)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Croissant CSV Metadata Generator [matching vocab, single-pass Ollama matcher + real prompt logging]")
        self.resize(1600, 900)

        self.csv_path: Optional[str] = None
        self.csv_sha256: Optional[str] = None
        self.csv_columns: List[str] = []
        self.preview_df: Optional[pd.DataFrame] = None
        self.last_generated: Optional[dict] = None
        self.last_generated_pretty: str = ""

        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.default_model_name = "gemma3:4b"
        self.default_vocab_path = os.path.join(self.script_dir, "pchprop_matching_vocab.json")
        self.model_name = self.default_model_name
        self.vocab_path = self.default_vocab_path
        self.llm = None
        self.vocab_entries: List[VocabEntry] = []
        self.vocab_lookup: Dict[str, VocabEntry] = {}
        self.vocab_label_lookup: Dict[str, VocabEntry] = {}
        self.log_lines: List[str] = []
        self.current_log_path: Optional[str] = None
        self.log_lines = [f"Initialised matcher version: {MATCHER_VERSION}"]

        root = QWidget()
        self.setCentralWidget(root)
        main_layout = QVBoxLayout(root)

        top_bar = QHBoxLayout()
        self.btn_load = QPushButton("Load CSV…")
        self.btn_load.clicked.connect(self.load_csv)
        self.lbl_file = QLabel("No CSV loaded")
        self.lbl_file.setTextInteractionFlags(Qt.TextSelectableByMouse)
        top_bar.addWidget(self.btn_load)
        top_bar.addWidget(self.lbl_file, 1)
        main_layout.addLayout(top_bar)

        preview_controls = QHBoxLayout()
        preview_controls.addWidget(QLabel("Rows to show:"))
        self.spin_rows = QSpinBox()
        self.spin_rows.setMinimum(5)
        self.spin_rows.setMaximum(5000)
        self.spin_rows.setValue(15)
        preview_controls.addWidget(self.spin_rows)
        self.btn_refresh = QPushButton("Refresh preview")
        self.btn_refresh.clicked.connect(self.refresh_preview)
        self.btn_refresh.setEnabled(False)
        preview_controls.addWidget(self.btn_refresh)
        preview_controls.addStretch(1)
        main_layout.addLayout(preview_controls)

        splitter = QSplitter()
        splitter.setOrientation(Qt.Horizontal)
        main_layout.addWidget(splitter, 1)

        meta_panel = QWidget()
        meta_layout = QVBoxLayout(meta_panel)

        required_group = QGroupBox("Required / common dataset metadata")
        form_req = QFormLayout(required_group)
        self.in_name = QLineEdit()
        self.in_desc = QTextEdit()
        self.in_desc.setFixedHeight(90)
        self.in_license = QLineEdit()
        self.in_license.setPlaceholderText("e.g. https://creativecommons.org/licenses/by/4.0/")
        self.in_url = QLineEdit()
        self.in_url.setPlaceholderText("Dataset landing page (recommended).")
        self.in_version = QLineEdit()
        self.in_version.setPlaceholderText("e.g. 1.0")
        self.in_keywords = QLineEdit()
        self.in_keywords.setPlaceholderText("Comma-separated keywords.")
        self.in_citeas = QTextEdit()
        self.in_citeas.setFixedHeight(70)
        self.in_citeas.setPlaceholderText("Citation string (DOI/BibTeX/plain text).")
        self.chk_live = QCheckBox("isLiveDataset")
        form_req.addRow("Name*", self.in_name)
        form_req.addRow("Description*", self.in_desc)
        form_req.addRow("License URL*", self.in_license)
        form_req.addRow("URL", self.in_url)
        form_req.addRow("Version", self.in_version)
        form_req.addRow("Keywords", self.in_keywords)
        form_req.addRow("Cite as", self.in_citeas)
        form_req.addRow("", self.chk_live)
        meta_layout.addWidget(required_group)

        optional_group = QGroupBox("Optional metadata (schema.org fields)")
        form_opt = QFormLayout(optional_group)
        self.in_identifier = QLineEdit()
        self.in_sameas = QLineEdit()
        self.in_language = QLineEdit()
        self.in_date_created = QLineEdit()
        self.in_date_modified = QLineEdit()
        self.in_publisher = QLineEdit()
        self.in_creator_name = QLineEdit()
        self.in_creator_type = QComboBox()
        self.in_creator_type.addItems(["sc:Person", "sc:Organization"])
        self.in_contact_email = QLineEdit()
        self.in_funding = QLineEdit()
        form_opt.addRow("Identifier", self.in_identifier)
        form_opt.addRow("sameAs URLs", self.in_sameas)
        form_opt.addRow("inLanguage", self.in_language)
        form_opt.addRow("dateCreated", self.in_date_created)
        form_opt.addRow("dateModified", self.in_date_modified)
        form_opt.addRow("Publisher", self.in_publisher)
        form_opt.addRow("Creator name", self.in_creator_name)
        form_opt.addRow("Creator type", self.in_creator_type)
        form_opt.addRow("Contact email", self.in_contact_email)
        form_opt.addRow("Funding", self.in_funding)
        meta_layout.addWidget(optional_group)

        record_group = QGroupBox("RecordSet metadata")
        form_rec = QFormLayout(record_group)
        self.in_recordset_name = QLineEdit()
        self.in_recordset_name.setText("default")
        self.in_recordset_desc = QTextEdit()
        self.in_recordset_desc.setFixedHeight(70)
        self.in_citations = QTextEdit()
        self.in_citations.setFixedHeight(70)
        form_rec.addRow("RecordSet name", self.in_recordset_name)
        form_rec.addRow("RecordSet description", self.in_recordset_desc)
        form_rec.addRow("Citation lines", self.in_citations)
        meta_layout.addWidget(record_group)

        llm_group = QGroupBox("Controlled vocabulary description matching")
        llm_layout = QFormLayout(llm_group)
        self.in_model_path = QLineEdit(self.model_name)
        self.in_vocab_path = QLineEdit(self.vocab_path)
        self.btn_model = QPushButton("Set…")
        self.btn_vocab = QPushButton("Browse…")
        self.btn_suggest = QPushButton("Suggest descriptions from vocab")
        self.btn_suggest.clicked.connect(self.suggest_descriptions_from_vocab)
        self.btn_suggest.setEnabled(False)

        row_model = QHBoxLayout()
        row_model.addWidget(self.in_model_path, 1)
        row_model.addWidget(self.btn_model)
        row_vocab = QHBoxLayout()
        row_vocab.addWidget(self.in_vocab_path, 1)
        row_vocab.addWidget(self.btn_vocab)
        llm_layout.addRow("Ollama model", row_model)
        llm_layout.addRow("Vocab JSON", row_vocab)
        llm_layout.addRow("", self.btn_suggest)
        self.btn_model.clicked.connect(self.choose_model)
        self.btn_vocab.clicked.connect(self.choose_vocab)
        meta_layout.addWidget(llm_group)

        out_group = QGroupBox("Actions")
        out_layout = QVBoxLayout(out_group)
        self.btn_generate = QPushButton("Generate JSON")
        self.btn_generate.clicked.connect(self.generate_clicked)
        self.btn_generate.setEnabled(False)
        self.btn_save = QPushButton("Save JSON…")
        self.btn_save.clicked.connect(self.save_json)
        self.btn_save.setEnabled(False)
        out_layout.addWidget(self.btn_generate)
        out_layout.addWidget(self.btn_save)
        meta_layout.addWidget(out_group)
        meta_layout.addStretch(1)

        meta_scroll = QScrollArea()
        meta_scroll.setWidgetResizable(True)
        meta_scroll.setFrameShape(QScrollArea.NoFrame)
        meta_scroll.setWidget(meta_panel)
        splitter.addWidget(meta_scroll)

        data_panel = QWidget()
        data_layout = QVBoxLayout(data_panel)
        prev_group = QGroupBox("CSV preview")
        prev_layout = QVBoxLayout(prev_group)
        self.table_preview = QTableView()
        self.table_preview.setAlternatingRowColors(True)
        self.table_preview.setSelectionBehavior(QTableView.SelectRows)
        prev_layout.addWidget(self.table_preview, 1)
        data_layout.addWidget(prev_group, 1)

        fields_group = QGroupBox("Fields (one per CSV column)")
        fields_layout = QVBoxLayout(fields_group)
        self.fields_table = QTableWidget(0, 3)
        self.fields_table.setHorizontalHeaderLabels(["Column", "dataType", "Description"])
        self.fields_table.horizontalHeader().setStretchLastSection(True)
        self.fields_table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed)
        fields_layout.addWidget(self.fields_table, 1)
        data_layout.addWidget(fields_group, 1)
        splitter.addWidget(data_panel)

        json_panel = QWidget()
        json_layout = QVBoxLayout(json_panel)
        json_group = QGroupBox("Generated Croissant JSON")
        json_group_layout = QVBoxLayout(json_group)
        self.json_preview = QTextEdit()
        self.json_preview.setReadOnly(True)
        self.json_preview.setPlaceholderText("Nothing generated yet.")
        json_group_layout.addWidget(self.json_preview, 1)
        json_layout.addWidget(json_group, 1)
        self.lbl_sha = QLabel("CSV sha256: (not computed)")
        self.lbl_sha.setTextInteractionFlags(Qt.TextSelectableByMouse)
        json_layout.addWidget(self.lbl_sha)
        val_group = QGroupBox("Validation and LLM log")
        val_layout = QVBoxLayout(val_group)
        self.validation_pane = QTextEdit()
        self.validation_pane.setReadOnly(True)
        self.validation_pane.setFixedHeight(260)
        self.validation_pane.setPlaceholderText("Validation results and matcher log will appear here.")
        val_layout.addWidget(self.validation_pane)
        json_layout.addWidget(val_group)

        json_scroll = QScrollArea()
        json_scroll.setWidgetResizable(True)
        json_scroll.setFrameShape(QScrollArea.NoFrame)
        json_scroll.setWidget(json_panel)
        splitter.addWidget(json_scroll)
        splitter.setChildrenCollapsible(False)
        splitter.setSizes([430, 620, 380])

        self.try_load_vocab(silent=True)

    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}"
        self.log_lines.append(line)
        self.validation_pane.append(line)
        if self.current_log_path:
            try:
                with open(self.current_log_path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception:
                pass

    def choose_model(self):
        model_name, ok = QInputDialog.getText(
            self,
            "Ollama model",
            "Model name:",
            text=self.in_model_path.text().strip() or self.default_model_name,
        )
        if ok and model_name.strip():
            self.in_model_path.setText(model_name.strip())
            self.model_name = model_name.strip()
            self.llm = None

    def choose_vocab(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select vocab JSON", self.script_dir, "JSON files (*.json);;All files (*.*)")
        if path:
            self.in_vocab_path.setText(path)
            self.vocab_path = path
            self.try_load_vocab(silent=False)


    def try_load_vocab(self, silent: bool = False) -> bool:
        self.vocab_path = self.in_vocab_path.text().strip() or self.default_vocab_path
        if not os.path.exists(self.vocab_path):
            if not silent:
                QMessageBox.warning(self, "Vocab not found", f"Could not find vocab file:\n{self.vocab_path}")
            self.vocab_entries = []
            self.vocab_lookup = {}
            self.vocab_label_lookup = {}
            self.btn_suggest.setEnabled(False)
            return False

        try:
            with open(self.vocab_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            entries: List[VocabEntry] = []
            for payload in data.get("field_candidates", []):
                if not isinstance(payload, dict):
                    continue
                label = str(payload.get("label", "")).strip()
                definition = str(payload.get("definition", "")).strip()
                vocab_id = str(payload.get("id", "")).strip()
                if not label or not definition or not vocab_id:
                    continue
                entries.append(
                    VocabEntry(
                        vocab_id=vocab_id,
                        section="field_candidates",
                        label=label,
                        definition=definition,
                        value_type=str(payload.get("value_type", "")).strip(),
                        category=str(payload.get("category", "")).strip(),
                        source_token=str(payload.get("source_token", "")).strip(),
                        possible_headings=[str(x).strip() for x in payload.get("possible_headings", []) if str(x).strip()],
                        allowed_units=[str(x).strip() for x in payload.get("allowed_units", []) if str(x).strip()],
                        expected_unit_type=str(payload.get("expected_unit_type", "")).strip(),
                    )
                )

            self.vocab_entries = entries
            self.vocab_lookup = {e.vocab_id: e for e in entries}
            self.vocab_label_lookup = {normalise_text(e.label): e for e in entries}
            self.btn_suggest.setEnabled(bool(entries))
            if not silent:
                QMessageBox.information(self, "Vocab loaded", f"Loaded {len(entries)} field candidates from matching vocab.")
            return True
        except Exception as e:
            self.vocab_entries = []
            self.vocab_lookup = {}
            self.vocab_label_lookup = {}
            self.btn_suggest.setEnabled(False)
            if not silent:
                QMessageBox.critical(self, "Vocab error", f"Could not load vocab JSON.\n\n{e}")
            return False

    def ensure_llm(self):
        if ollama is None:
            raise RuntimeError("The ollama Python package is not installed in this environment.")
        self.model_name = self.in_model_path.text().strip() or self.default_model_name
        if self.llm is None:
            self.log(f"Connecting to Ollama model: {self.model_name}")
            try:
                ollama.list()
            except Exception as e:
                raise RuntimeError(f"Could not connect to Ollama. Is the Ollama app/service running?\n\n{e}")
            self.llm = self.model_name
            self.log("Ollama ready.")
        return self.llm

    def call_ollama(self, prompt: str, max_tokens: int = 8) -> str:
        model_name = self.ensure_llm()
        try:
            response = ollama.chat(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "temperature": 0,
                    "num_predict": max_tokens,
                    "top_p": 0.9,
                },
            )
        except Exception as e:
            raise RuntimeError(f"Ollama request failed for model '{model_name}'.\n\n{e}")
        return response.get("message", {}).get("content", "").strip()

    def load_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select CSV file", "", "CSV files (*.csv);;All files (*.*)")
        if not path:
            return
        try:
            cols = pd.read_csv(path, nrows=0).columns.tolist()
            if not cols:
                raise ValueError("No columns found.")
        except Exception as e:
            QMessageBox.critical(self, "CSV error", f"Could not read CSV headers.\n\n{e}")
            return

        self.csv_path = path
        self.csv_columns = cols
        self.csv_sha256 = None
        self.last_generated = None
        self.last_generated_pretty = ""
        self.lbl_file.setText(path)
        self.btn_refresh.setEnabled(True)
        self.btn_generate.setEnabled(True)
        self.btn_save.setEnabled(True)
        self.btn_suggest.setEnabled(bool(self.vocab_entries))

        if not self.in_name.text().strip():
            self.in_name.setText(os.path.splitext(os.path.basename(path))[0])
        if not self.in_recordset_desc.toPlainText().strip():
            self.in_recordset_desc.setPlainText("Records extracted from the CSV file, with their schema.")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_log_path = os.path.join(os.path.dirname(path), f"croissant_vocab_match_log_{timestamp}.txt")
        self.validation_pane.clear()
        self.log_lines = []
        self.log(f"Loaded CSV: {path}")
        self.log(f"Found {len(cols)} columns.")

        self.refresh_preview()
        self.populate_fields_table()
        self.json_preview.setPlainText("Nothing generated yet.")
        self.lbl_sha.setText("CSV sha256: (not computed)")

    def refresh_preview(self):
        if not self.csv_path:
            return
        try:
            df = pd.read_csv(self.csv_path, nrows=int(self.spin_rows.value()))
            self.preview_df = df
            self.table_preview.setModel(PandasTableModel(df))
            self.table_preview.resizeColumnsToContents()
            self.apply_type_guesses_from_preview(df)
        except Exception as e:
            QMessageBox.critical(self, "Preview error", f"Could not load preview.\n\n{e}")

    def populate_fields_table(self):
        self.fields_table.blockSignals(True)
        try:
            self.fields_table.setRowCount(0)
            for col in self.csv_columns:
                r = self.fields_table.rowCount()
                self.fields_table.insertRow(r)
                item_col = QTableWidgetItem(col)
                item_col.setFlags(item_col.flags() & ~Qt.ItemIsEditable)
                self.fields_table.setItem(r, 0, item_col)
                combo = QComboBox()
                combo.addItems(SCHEMA_DATATYPES)
                combo.setCurrentText("sc:Text")
                self.fields_table.setCellWidget(r, 1, combo)
                self.fields_table.setItem(r, 2, QTableWidgetItem(""))
        finally:
            self.fields_table.blockSignals(False)
        self.fields_table.resizeColumnsToContents()

    def apply_type_guesses_from_preview(self, df: pd.DataFrame):
        col_to_guess = {c: guess_datatype(df[c]) for c in df.columns}
        for row in range(self.fields_table.rowCount()):
            col_item = self.fields_table.item(row, 0)
            if not col_item:
                continue
            col_name = col_item.text()
            guess = col_to_guess.get(col_name)
            widget = self.fields_table.cellWidget(row, 1)
            if isinstance(widget, QComboBox) and guess in SCHEMA_DATATYPES:
                if widget.currentText() == "sc:Text":
                    widget.setCurrentText(guess)

    def collect_fields(self) -> List[FieldMeta]:
        fields: List[FieldMeta] = []
        for r in range(self.fields_table.rowCount()):
            col_name = self.fields_table.item(r, 0).text()
            combo = self.fields_table.cellWidget(r, 1)
            data_type = combo.currentText() if isinstance(combo, QComboBox) else "sc:Text"
            desc_item = self.fields_table.item(r, 2)
            desc = desc_item.text().strip() if desc_item else ""
            fields.append(FieldMeta(name=col_name, data_type=data_type, description=desc))
        return fields


    def index_to_letters(self, index: int) -> str:
        result = ""
        n = index + 1
        while n > 0:
            n, remainder = divmod(n - 1, 26)
            result = chr(65 + remainder) + result
        return result

    def build_lettered_options(self, target_column: str, entries: List[VocabEntry], salt: str = "") -> List[Tuple[str, VocabEntry]]:
        shuffled_entries = list(entries)
        rng = random.Random(hashlib.sha1(f"{target_column}|{salt}".encode("utf-8")).hexdigest())
        rng.shuffle(shuffled_entries)
        return [(self.index_to_letters(i), entry) for i, entry in enumerate(shuffled_entries)]

    def parse_letter_choices(self, raw_text: str, valid_letters: List[str], allow_multiple: bool, limit: int = 1) -> List[str]:
        text = (raw_text or "").upper().strip()
        if not text:
            return []
        if "NO_MATCH" in text or "NONE" in text or text == "Z":
            return []
        valid_set = {v.upper() for v in valid_letters}
        tokens = re.findall(r"\b[A-Z]{1,3}\b", text)
        found: List[str] = []
        seen = set()
        for tok in tokens:
            if tok in valid_set and tok not in seen:
                found.append(tok)
                seen.add(tok)
                if not allow_multiple or len(found) >= limit:
                    break
        return found

    def make_option_code(self, target_column: str, label: str, salt: str = "") -> str:
        base = f"{target_column}|{label}|{salt}"
        digest = hashlib.sha1(base.encode("utf-8")).hexdigest().upper()
        return "C" + digest[:6]

    def build_coded_options(self, target_column: str, entries: List[VocabEntry], salt: str = "") -> List[Tuple[str, VocabEntry]]:
        pairs = [(self.make_option_code(target_column, e.label, salt=f"{salt}|{i}"), e) for i, e in enumerate(entries)]
        rng = random.Random(hashlib.sha1(f"{target_column}|{salt}".encode("utf-8")).hexdigest())
        rng.shuffle(pairs)
        return pairs

    def format_vocab_entry_for_prompt(self, code: str, entry: VocabEntry) -> str:
        headings = "; ".join(entry.possible_headings[:4]) if entry.possible_headings else ""
        parts = [f"{code} | {entry.label}"]
        if headings:
            parts.append(f"headings: {headings}")
        parts.append("definition: " + entry.definition)
        return "\n".join(parts)

    def chunk_vocab_entries(self, chunk_size: int = 8) -> List[List[VocabEntry]]:
        return [self.vocab_entries[i:i + chunk_size] for i in range(0, len(self.vocab_entries), chunk_size)]

    def build_single_pass_prompt(self, target_column: str, lettered_subset: List[Tuple[str, VocabEntry]]) -> str:
        normalised_target = normalise_text(target_column)
        option_lines = "\n\n".join(f"{letter} | {entry.label}" for letter, entry in lettered_subset)
        return (
            "Choose the best matching label for this header.\n"
            "Only use labels from the options below.\n"
            "Return only the option letter or NO_MATCH.\n"
            "If nothing fits, return NO_MATCH.\n\n"
            f"Target header:\n{target_column}\n\n"
            f"Normalised header:\n{normalised_target}\n\n"
            f"Options:\n{option_lines}\n\n"
            "Answer:"
        )

    def query_model_for_choice(self, target_column: str) -> Tuple[str, str, str, List[Tuple[str, VocabEntry]], List[str]]:
        self.ensure_llm()
        lettered_candidates = self.build_lettered_options(target_column, self.vocab_entries, salt="single_pass")
        prompt = self.build_single_pass_prompt(target_column, lettered_candidates)
        raw = self.call_ollama(prompt, max_tokens=8)
        valid_letters = [letter for letter, _ in lettered_candidates]
        choice_letters = self.parse_letter_choices(raw, valid_letters=valid_letters, allow_multiple=False, limit=1)
        if not choice_letters:
            return raw, "NO_MATCH", prompt, lettered_candidates, []
        letter_map = {letter: entry for letter, entry in lettered_candidates}
        return raw, letter_map[choice_letters[0]].label, prompt, lettered_candidates, choice_letters

    def match_unit_from_header(self, column_name: str) -> Optional[str]:
        try:
            with open(self.vocab_path, "r", encoding="utf-8") as f:
                vocab_data = json.load(f)
        except Exception:
            return None
        units = vocab_data.get("unit_candidates", [])
        _, raw_units = extract_header_core_and_units(column_name)
        header_unit_text = normalise_unit_text(" ".join(raw_units))
        if not header_unit_text:
            return None
        for unit in units:
            for variant in unit.get("possible_headings", []):
                if normalise_unit_text(variant) == header_unit_text:
                    return unit.get("label") or unit.get("symbol")
        return None

    def suggest_descriptions_from_vocab(self):
        if not self.csv_path:
            QMessageBox.information(self, "No CSV", "Load a CSV first.")
            return
        if not self.try_load_vocab(silent=False):
            return
        try:
            self.ensure_llm()
        except Exception as e:
            QMessageBox.critical(self, "Model error", str(e))
            return

        matched = 0
        no_match = 0
        self.log("Starting controlled-vocabulary matching. Matcher mode: lean single-pass Ollama label selection with matching vocab and deterministic normalisation.")

        for row in range(self.fields_table.rowCount()):
            col_name = self.fields_table.item(row, 0).text()
            desc_item = self.fields_table.item(row, 2)
            self.log(f"Column: {col_name}")
            self.log(f"Normalised header: {normalise_text(col_name)}")
            detected_unit = self.match_unit_from_header(col_name)
            if detected_unit:
                self.log(f"Detected unit from header: {detected_unit}")
            try:
                raw_output, choice, prompt_text, option_pairs, parsed_letters = self.query_model_for_choice(col_name)
                self.log("Ollama prompt start >>>")
                self.log(prompt_text)
                self.log("<<< Ollama prompt end")
                self.log("Option mapping: " + "; ".join(f"{letter} -> {entry.label} [{entry.vocab_id}]" for letter, entry in option_pairs))
                self.log(f"Single-pass raw choice output: {raw_output}")
                self.log("Single-pass parsed letter(s): " + (", ".join(parsed_letters) if parsed_letters else "NO_MATCH"))
                self.log(f"Single-pass parsed choice: {choice}")
                if choice != "NO_MATCH":
                    chosen_entry = self.vocab_label_lookup.get(normalise_text(choice))
                    if chosen_entry:
                        desc_item.setText(chosen_entry.definition)
                        matched += 1
                        self.log(f"Applied description from label '{chosen_entry.label}' [{chosen_entry.vocab_id}]")
                    else:
                        no_match += 1
                        self.log("Chosen label could not be resolved back to a vocab entry.")
                else:
                    no_match += 1
                    self.log("No match applied.")
            except Exception as e:
                no_match += 1
                self.log(f"Error while matching column '{col_name}': {e}")
            self.log("-")

        QMessageBox.information(
            self,
            "Description matching complete",
            f"Finished matching.\n\nMatched: {matched}\nNo match / failed: {no_match}\n\nLog file:\n{self.current_log_path}",
        )

    def build_croissant_json(self, output_path: Optional[str] = None) -> dict:
        if not self.csv_path:
            raise ValueError("No CSV loaded.")
        name = self.in_name.text().strip()
        desc = self.in_desc.toPlainText().strip()
        lic = self.in_license.text().strip()
        if not name:
            raise ValueError("Dataset name is required.")
        if not desc:
            raise ValueError("Dataset description is required.")
        if not lic:
            raise ValueError("License URL is required.")

        csv_filename = os.path.basename(self.csv_path)
        if output_path:
            out_dir = os.path.dirname(os.path.abspath(output_path))
            csv_abs = os.path.abspath(self.csv_path)
            try:
                content_url = os.path.relpath(csv_abs, out_dir).replace("\\", "/")
            except Exception:
                content_url = csv_abs.replace("\\", "/")
        else:
            content_url = csv_filename

        if not self.csv_sha256:
            self.csv_sha256 = sha256_file(self.csv_path)

        keywords = [k.strip() for k in self.in_keywords.text().split(",") if k.strip()]
        version = self.in_version.text().strip()
        url = self.in_url.text().strip()
        cite_as = self.in_citeas.toPlainText().strip()
        identifier = self.in_identifier.text().strip()
        same_as = [s.strip() for s in self.in_sameas.text().split(",") if s.strip()]
        in_language = self.in_language.text().strip()
        date_created = self.in_date_created.text().strip()
        date_modified = self.in_date_modified.text().strip()
        publisher = self.in_publisher.text().strip()
        creator_name = self.in_creator_name.text().strip()
        creator_type = self.in_creator_type.currentText().strip()
        contact_email = self.in_contact_email.text().strip()
        funding = self.in_funding.text().strip()
        recordset_name = self.in_recordset_name.text().strip() or "default"
        recordset_desc = self.in_recordset_desc.toPlainText().strip()
        citations = [line.strip() for line in self.in_citations.toPlainText().splitlines() if line.strip()]
        fields = self.collect_fields()

        metadata: dict = {
            "@context": CROISSANT_CONTEXT,
            "@type": "sc:Dataset",
            "conformsTo": "http://mlcommons.org/croissant/1.0",
            "name": name,
            "description": desc,
            "license": lic,
            "isLiveDataset": bool(self.chk_live.isChecked()),
            "distribution": [{
                "@type": "cr:FileObject",
                "@id": csv_filename,
                "name": csv_filename,
                "contentUrl": content_url,
                "encodingFormat": "text/csv",
                "sha256": self.csv_sha256,
            }],
            "recordSet": [{
                "@type": "cr:RecordSet",
                "name": recordset_name,
                **({"description": recordset_desc} if recordset_desc else {}),
                "field": [{
                    "@type": "cr:Field",
                    "name": f.name,
                    **({"description": f.description} if f.description else {}),
                    "dataType": f.data_type,
                    "source": {
                        "fileObject": {"@id": csv_filename},
                        "extract": {"column": f.name},
                    },
                } for f in fields],
            }],
        }

        if url:
            metadata["url"] = url
        if version:
            metadata["version"] = version
        if keywords:
            metadata["keywords"] = keywords
        if cite_as:
            metadata["citeAs"] = cite_as
        if identifier:
            metadata["identifier"] = identifier
        if same_as:
            metadata["sameAs"] = same_as
        if in_language:
            metadata["inLanguage"] = in_language
        if date_created:
            metadata["dateCreated"] = date_created
        if date_modified:
            metadata["dateModified"] = date_modified
        if publisher:
            metadata["publisher"] = [{"@type": "sc:Organization", "name": publisher}]
        if creator_name:
            metadata["creator"] = [{"@type": creator_type, "name": creator_name}]
        if contact_email:
            metadata["contactPoint"] = [{"@type": "sc:ContactPoint", "email": contact_email}]
        if funding:
            metadata["funding"] = funding
        if citations:
            metadata["citation"] = citations
        return metadata

    def run_mlcroissant_validate(self, jsonld_text: str) -> Tuple[str, bool]:
        exe = shutil.which("mlcroissant")
        if not exe:
            return (
                "mlcroissant CLI not found.\n\nInstall with:\n  pip install mlcroissant\nand make sure your venv/bin is on PATH.",
                False,
            )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp:
            tmp_path = tmp.name
            tmp.write(jsonld_text)
        try:
            proc = subprocess.run([exe, "validate", "--jsonld", tmp_path], capture_output=True, text=True)
            out = (proc.stdout or "").strip()
            err = (proc.stderr or "").strip()
            ok = proc.returncode == 0
            parts = [f"Command: mlcroissant validate --jsonld {os.path.basename(tmp_path)}", f"Exit code: {proc.returncode} ({'OK' if ok else 'ERRORS'})"]
            if out:
                parts.append("\n--- stdout ---\n" + out)
            if err:
                parts.append("\n--- stderr ---\n" + err)
            if not out and not err:
                parts.append("\n(No output returned)")
            return "\n".join(parts), ok
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    def generate_clicked(self):
        if not self.csv_path:
            QMessageBox.information(self, "No CSV", "Load a CSV first.")
            return
        try:
            data = self.build_croissant_json(output_path=None)
            pretty = json.dumps(data, indent=2, ensure_ascii=False)
            self.last_generated = data
            self.last_generated_pretty = pretty
            self.json_preview.setPlainText(pretty)
            self.lbl_sha.setText(f"CSV sha256: {self.csv_sha256}")
            validation_text, ok = self.run_mlcroissant_validate(pretty)
            self.validation_pane.append("\n=== mlcroissant validation ===\n")
            self.validation_pane.append(validation_text)
            if ok:
                self.validation_pane.append("\n\nResult: ✅ Valid (mlcroissant exited 0)")
            else:
                self.validation_pane.append("\n\nResult: ❌ Not valid (see output above)")
        except Exception as e:
            self.last_generated = None
            self.last_generated_pretty = ""
            self.json_preview.setPlainText(f"Cannot generate valid Croissant JSON yet:\n\n{e}")
            self.lbl_sha.setText("CSV sha256: (not computed)")

    def save_json(self):
        if not self.csv_path:
            QMessageBox.information(self, "No CSV", "Load a CSV first.")
            return
        if not self.last_generated_pretty:
            QMessageBox.information(self, "Not generated", "Click Generate first, then Save.")
            return
        default_name = "croissant.json"
        start_dir = os.path.dirname(os.path.abspath(self.csv_path))
        out_path, _ = QFileDialog.getSaveFileName(self, "Save Croissant JSON-LD", os.path.join(start_dir, default_name), "JSON files (*.json);;All files (*.*)")
        if not out_path:
            return
        try:
            data = self.build_croissant_json(output_path=out_path)
            pretty = json.dumps(data, indent=2, ensure_ascii=False)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(pretty)
            self.last_generated = data
            self.last_generated_pretty = pretty
            self.json_preview.setPlainText(pretty)
            self.lbl_sha.setText(f"CSV sha256: {self.csv_sha256}")
            QMessageBox.information(self, "Saved", f"Croissant JSON saved:\n{out_path}")
        except Exception as e:
            QMessageBox.critical(self, "Save error", str(e))


def main():
    app = QApplication([])
    w = MainWindow()
    w.show()
    app.exec_()


if __name__ == "__main__":
    main()
