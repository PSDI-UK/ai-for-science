#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
File: croissant_gui.py
Author: Matthew Partridge
Created: 2026-02-06
Description: TBD
Version: 0.3
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import List, Optional, Tuple

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
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

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


@dataclass
class FieldMeta:
    name: str
    data_type: str = "sc:Text"
    description: str = ""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Croissant CSV Metadata Generator")
        self.resize(1500, 850)

        self.csv_path: Optional[str] = None
        self.csv_sha256: Optional[str] = None
        self.csv_columns: List[str] = []
        self.preview_df: Optional[pd.DataFrame] = None

        self.last_generated: Optional[dict] = None
        self.last_generated_pretty: str = ""

        root = QWidget()
        self.setCentralWidget(root)
        main_layout = QVBoxLayout(root)

        # Top bar
        top_bar = QHBoxLayout()
        self.btn_load = QPushButton("Load CSV…")
        self.btn_load.clicked.connect(self.load_csv)

        self.lbl_file = QLabel("No CSV loaded")
        self.lbl_file.setTextInteractionFlags(Qt.TextSelectableByMouse)

        top_bar.addWidget(self.btn_load)
        top_bar.addWidget(self.lbl_file, 1)
        main_layout.addLayout(top_bar)

        # Preview controls
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

        # Three-pane splitter
        splitter = QSplitter()
        splitter.setOrientation(Qt.Horizontal)
        main_layout.addWidget(splitter, 1)

        # Pane 1: Metadata

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

        # Optional metadata (scrollable)
        optional_group = QGroupBox("Optional metadata (schema.org fields)")
        form_opt = QFormLayout(optional_group)

        self.in_identifier = QLineEdit()
        self.in_identifier.setPlaceholderText("Any identifier (DOI/UUID/local).")

        self.in_sameas = QLineEdit()
        self.in_sameas.setPlaceholderText("Comma-separated URLs that describe the same dataset.")

        self.in_language = QLineEdit()
        self.in_language.setPlaceholderText("e.g. en-GB")

        self.in_date_created = QLineEdit()
        self.in_date_created.setPlaceholderText("YYYY-MM-DD (or ISO datetime).")

        self.in_date_modified = QLineEdit()
        self.in_date_modified.setPlaceholderText("YYYY-MM-DD (or ISO datetime).")

        self.in_publisher = QLineEdit()
        self.in_publisher.setPlaceholderText("Publisher organisation name.")

        self.in_creator_type = QComboBox()
        self.in_creator_type.addItems(["sc:Person", "sc:Organization"])
        self.in_creator_name = QLineEdit()
        self.in_creator_name.setPlaceholderText("Creator name (person or organisation).")

        self.in_contact_email = QLineEdit()
        self.in_contact_email.setPlaceholderText("Contact email")

        self.in_funding = QLineEdit()
        self.in_funding.setPlaceholderText("Funding text (e.g. 'EPSRC EP/XXXX').")

        self.in_recordset_name = QLineEdit()
        self.in_recordset_name.setText("default")
        self.in_recordset_desc = QTextEdit()
        self.in_recordset_desc.setFixedHeight(60)

        self.in_citations = QTextEdit()
        self.in_citations.setFixedHeight(70)
        self.in_citations.setPlaceholderText("One citation per line")

        form_opt.addRow("identifier", self.in_identifier)
        form_opt.addRow("sameAs", self.in_sameas)
        form_opt.addRow("inLanguage", self.in_language)
        form_opt.addRow("dateCreated", self.in_date_created)
        form_opt.addRow("dateModified", self.in_date_modified)
        form_opt.addRow("publisher", self.in_publisher)
        form_opt.addRow("creator type", self.in_creator_type)
        form_opt.addRow("creator name", self.in_creator_name)
        form_opt.addRow("contact email", self.in_contact_email)
        form_opt.addRow("funding", self.in_funding)
        form_opt.addRow("recordSet name", self.in_recordset_name)
        form_opt.addRow("recordSet desc", self.in_recordset_desc)
        form_opt.addRow("citation", self.in_citations)

        optional_scroll = QScrollArea()
        optional_scroll.setWidgetResizable(True)
        optional_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        optional_scroll.setWidget(optional_group)
        meta_layout.addWidget(optional_scroll)

        # Output buttons
        out_group = QGroupBox("Output")
        out_layout = QHBoxLayout(out_group)

        self.btn_generate = QPushButton("Generate")
        self.btn_generate.clicked.connect(self.generate_clicked)
        self.btn_generate.setEnabled(False)

        self.btn_save = QPushButton("Save Croissant JSON…")
        self.btn_save.clicked.connect(self.save_json)
        self.btn_save.setEnabled(False)

        out_layout.addWidget(self.btn_generate)
        out_layout.addWidget(self.btn_save)
        meta_layout.addWidget(out_group)

        meta_layout.addStretch(1)
        splitter.addWidget(meta_panel)

        # Pane 2: Data preview + fields

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

        # Pane 3: Generated JSON + validation

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

        val_group = QGroupBox("mlcroissant validation")
        val_layout = QVBoxLayout(val_group)

        self.validation_pane = QTextEdit()
        self.validation_pane.setReadOnly(True)
        self.validation_pane.setFixedHeight(170)
        self.validation_pane.setPlaceholderText("Validation results will appear here after Generate.")
        val_layout.addWidget(self.validation_pane)

        json_layout.addWidget(val_group)

        splitter.addWidget(json_panel)
        splitter.setSizes([520, 620, 360])

    # CSV loading + preview

    def load_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV file", "", "CSV files (*.csv);;All files (*.*)"
        )
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

        if not self.in_name.text().strip():
            base = os.path.splitext(os.path.basename(path))[0]
            self.in_name.setText(base)

        if not self.in_recordset_desc.toPlainText().strip():
            self.in_recordset_desc.setPlainText("Records extracted from the CSV file, with their schema.")

        self.refresh_preview()
        self.populate_fields_table()

        self.json_preview.setPlainText("Nothing generated yet.")
        self.validation_pane.clear()
        self.lbl_sha.setText("CSV sha256: (not computed)")

    def refresh_preview(self):
        if not self.csv_path:
            return

        start = 0
        nrows = int(self.spin_rows.value())

        try:
            skip = range(1, start + 1) if start > 0 else None
            df = pd.read_csv(self.csv_path, skiprows=skip, nrows=nrows)
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

    # JSON generation + validation

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
                rel = os.path.relpath(csv_abs, out_dir)
                content_url = rel.replace("\\", "/")
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
            "distribution": [
                {
                    "@type": "cr:FileObject",
                    "@id": csv_filename,
                    "name": csv_filename,
                    "contentUrl": content_url,
                    "encodingFormat": "text/csv",
                    "sha256": self.csv_sha256,
                }
            ],
            "recordSet": [
                {
                    "@type": "cr:RecordSet",
                    "name": recordset_name,
                    **({"description": recordset_desc} if recordset_desc else {}),
                    "field": [
                        {
                            "@type": "cr:Field",
                            "name": f.name,
                            **({"description": f.description} if f.description else {}),
                            "dataType": f.data_type,
                            "source": {
                                "fileObject": {"@id": csv_filename},
                                "extract": {"column": f.name},
                            },
                        }
                        for f in fields
                    ],
                }
            ],
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
                "mlcroissant CLI not found.\n\nInstall with:\n  pip install mlcroissant\n"
                "and make sure your venv/bin is on PATH.",
                False,
            )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp:
            tmp_path = tmp.name
            tmp.write(jsonld_text)

        try:
            proc = subprocess.run(
                [exe, "validate", "--jsonld", tmp_path],
                capture_output=True,
                text=True,
            )
            out = (proc.stdout or "").strip()
            err = (proc.stderr or "").strip()

            ok = (proc.returncode == 0)
            parts = []
            parts.append(f"Command: mlcroissant validate --jsonld {os.path.basename(tmp_path)}")
            parts.append(f"Exit code: {proc.returncode} ({'OK' if ok else 'ERRORS'})")
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

            # Validate with mlcroissant
            validation_text, ok = self.run_mlcroissant_validate(pretty)
            self.validation_pane.setPlainText(validation_text)

            if ok:
                self.validation_pane.append("\n\nResult: ✅ Valid (mlcroissant exited 0)")
            else:
                self.validation_pane.append("\n\nResult: ❌ Not valid (see output above)")

        except Exception as e:
            self.last_generated = None
            self.last_generated_pretty = ""
            self.json_preview.setPlainText(f"Cannot generate valid Croissant JSON yet:\n\n{e}")
            self.validation_pane.setPlainText("")
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

        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Croissant JSON-LD",
            os.path.join(start_dir, default_name),
            "JSON files (*.json);;All files (*.*)",
        )
        if not out_path:
            return

        try:
            data = self.build_croissant_json(output_path=out_path)
            pretty = json.dumps(data, indent=2, ensure_ascii=False)

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(pretty)

            # Update the preview
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

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import List, Optional, Tuple

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
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

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


@dataclass
class FieldMeta:
    name: str
    data_type: str = "sc:Text"
    description: str = ""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Croissant CSV Metadata Generator")
        self.resize(1500, 850)

        self.csv_path: Optional[str] = None
        self.csv_sha256: Optional[str] = None
        self.csv_columns: List[str] = []
        self.preview_df: Optional[pd.DataFrame] = None

        self.last_generated: Optional[dict] = None
        self.last_generated_pretty: str = ""

        root = QWidget()
        self.setCentralWidget(root)
        main_layout = QVBoxLayout(root)

        # Top bar
        top_bar = QHBoxLayout()
        self.btn_load = QPushButton("Load CSV…")
        self.btn_load.clicked.connect(self.load_csv)

        self.lbl_file = QLabel("No CSV loaded")
        self.lbl_file.setTextInteractionFlags(Qt.TextSelectableByMouse)

        top_bar.addWidget(self.btn_load)
        top_bar.addWidget(self.lbl_file, 1)
        main_layout.addLayout(top_bar)

        # Preview controls
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

        # Three-pane splitter
        splitter = QSplitter()
        splitter.setOrientation(Qt.Horizontal)
        main_layout.addWidget(splitter, 1)

        # Pane 1: Metadata

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

        # Optional metadata (scrollable)
        optional_group = QGroupBox("Optional metadata (schema.org fields)")
        form_opt = QFormLayout(optional_group)

        self.in_identifier = QLineEdit()
        self.in_identifier.setPlaceholderText("Any identifier (DOI/UUID/local).")

        self.in_sameas = QLineEdit()
        self.in_sameas.setPlaceholderText("Comma-separated URLs that describe the same dataset.")

        self.in_language = QLineEdit()
        self.in_language.setPlaceholderText("e.g. en-GB")

        self.in_date_created = QLineEdit()
        self.in_date_created.setPlaceholderText("YYYY-MM-DD (or ISO datetime).")

        self.in_date_modified = QLineEdit()
        self.in_date_modified.setPlaceholderText("YYYY-MM-DD (or ISO datetime).")

        self.in_publisher = QLineEdit()
        self.in_publisher.setPlaceholderText("Publisher organisation name.")

        self.in_creator_type = QComboBox()
        self.in_creator_type.addItems(["sc:Person", "sc:Organization"])
        self.in_creator_name = QLineEdit()
        self.in_creator_name.setPlaceholderText("Creator name (person or organisation).")

        self.in_contact_email = QLineEdit()
        self.in_contact_email.setPlaceholderText("Contact email")

        self.in_funding = QLineEdit()
        self.in_funding.setPlaceholderText("Funding text (e.g. 'EPSRC EP/XXXX').")

        self.in_recordset_name = QLineEdit()
        self.in_recordset_name.setText("default")
        self.in_recordset_desc = QTextEdit()
        self.in_recordset_desc.setFixedHeight(60)

        self.in_citations = QTextEdit()
        self.in_citations.setFixedHeight(70)
        self.in_citations.setPlaceholderText("One citation per line")

        form_opt.addRow("identifier", self.in_identifier)
        form_opt.addRow("sameAs", self.in_sameas)
        form_opt.addRow("inLanguage", self.in_language)
        form_opt.addRow("dateCreated", self.in_date_created)
        form_opt.addRow("dateModified", self.in_date_modified)
        form_opt.addRow("publisher", self.in_publisher)
        form_opt.addRow("creator type", self.in_creator_type)
        form_opt.addRow("creator name", self.in_creator_name)
        form_opt.addRow("contact email", self.in_contact_email)
        form_opt.addRow("funding", self.in_funding)
        form_opt.addRow("recordSet name", self.in_recordset_name)
        form_opt.addRow("recordSet desc", self.in_recordset_desc)
        form_opt.addRow("citation", self.in_citations)

        optional_scroll = QScrollArea()
        optional_scroll.setWidgetResizable(True)
        optional_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        optional_scroll.setWidget(optional_group)
        meta_layout.addWidget(optional_scroll)

        # Output buttons
        out_group = QGroupBox("Output")
        out_layout = QHBoxLayout(out_group)

        self.btn_generate = QPushButton("Generate")
        self.btn_generate.clicked.connect(self.generate_clicked)
        self.btn_generate.setEnabled(False)

        self.btn_save = QPushButton("Save Croissant JSON…")
        self.btn_save.clicked.connect(self.save_json)
        self.btn_save.setEnabled(False)

        out_layout.addWidget(self.btn_generate)
        out_layout.addWidget(self.btn_save)
        meta_layout.addWidget(out_group)

        meta_layout.addStretch(1)
        splitter.addWidget(meta_panel)

        # Pane 2: Data preview + fields

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

        # Pane 3: Generated JSON + validation

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

        val_group = QGroupBox("mlcroissant validation")
        val_layout = QVBoxLayout(val_group)

        self.validation_pane = QTextEdit()
        self.validation_pane.setReadOnly(True)
        self.validation_pane.setFixedHeight(170)
        self.validation_pane.setPlaceholderText("Validation results will appear here after Generate.")
        val_layout.addWidget(self.validation_pane)

        json_layout.addWidget(val_group)

        splitter.addWidget(json_panel)
        splitter.setSizes([520, 620, 360])

    # CSV loading + preview

    def load_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV file", "", "CSV files (*.csv);;All files (*.*)"
        )
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

        if not self.in_name.text().strip():
            base = os.path.splitext(os.path.basename(path))[0]
            self.in_name.setText(base)

        if not self.in_recordset_desc.toPlainText().strip():
            self.in_recordset_desc.setPlainText("Records extracted from the CSV file, with their schema.")

        self.refresh_preview()
        self.populate_fields_table()

        self.json_preview.setPlainText("Nothing generated yet.")
        self.validation_pane.clear()
        self.lbl_sha.setText("CSV sha256: (not computed)")

    def refresh_preview(self):
        if not self.csv_path:
            return

        start = 0
        nrows = int(self.spin_rows.value())

        try:
            skip = range(1, start + 1) if start > 0 else None
            df = pd.read_csv(self.csv_path, skiprows=skip, nrows=nrows)
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

    # JSON generation + validation

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
                rel = os.path.relpath(csv_abs, out_dir)
                content_url = rel.replace("\\", "/")
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
            "distribution": [
                {
                    "@type": "cr:FileObject",
                    "@id": csv_filename,
                    "name": csv_filename,
                    "contentUrl": content_url,
                    "encodingFormat": "text/csv",
                    "sha256": self.csv_sha256,
                }
            ],
            "recordSet": [
                {
                    "@type": "cr:RecordSet",
                    "name": recordset_name,
                    **({"description": recordset_desc} if recordset_desc else {}),
                    "field": [
                        {
                            "@type": "cr:Field",
                            "name": f.name,
                            **({"description": f.description} if f.description else {}),
                            "dataType": f.data_type,
                            "source": {
                                "fileObject": {"@id": csv_filename},
                                "extract": {"column": f.name},
                            },
                        }
                        for f in fields
                    ],
                }
            ],
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
                "mlcroissant CLI not found.\n\nInstall with:\n  pip install mlcroissant\n"
                "and make sure your venv/bin is on PATH.",
                False,
            )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp:
            tmp_path = tmp.name
            tmp.write(jsonld_text)

        try:
            proc = subprocess.run(
                [exe, "validate", "--jsonld", tmp_path],
                capture_output=True,
                text=True,
            )
            out = (proc.stdout or "").strip()
            err = (proc.stderr or "").strip()

            ok = (proc.returncode == 0)
            parts = []
            parts.append(f"Command: mlcroissant validate --jsonld {os.path.basename(tmp_path)}")
            parts.append(f"Exit code: {proc.returncode} ({'OK' if ok else 'ERRORS'})")
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

            # Validate with mlcroissant
            validation_text, ok = self.run_mlcroissant_validate(pretty)
            self.validation_pane.setPlainText(validation_text)

            if ok:
                self.validation_pane.append("\n\nResult: ✅ Valid (mlcroissant exited 0)")
            else:
                self.validation_pane.append("\n\nResult: ❌ Not valid (see output above)")

        except Exception as e:
            self.last_generated = None
            self.last_generated_pretty = ""
            self.json_preview.setPlainText(f"Cannot generate valid Croissant JSON yet:\n\n{e}")
            self.validation_pane.setPlainText("")
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

        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Croissant JSON-LD",
            os.path.join(start_dir, default_name),
            "JSON files (*.json);;All files (*.*)",
        )
        if not out_path:
            return

        try:
            data = self.build_croissant_json(output_path=out_path)
            pretty = json.dumps(data, indent=2, ensure_ascii=False)

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(pretty)

            # Update the preview
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