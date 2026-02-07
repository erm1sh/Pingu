"""Targets tab: CRUD table (alias, host, interval, timeout, enabled), import/export JSON."""
import json
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QHeaderView,
    QMessageBox,
    QFileDialog,
)
from PySide6.QtCore import Qt

from core.config import TargetConfig, dict_to_target, target_to_dict, load_config, save_config


class TargetsTab(QWidget):
    def __init__(self, get_targets_cb, set_targets_cb, on_config_change=None):
        super().__init__()
        self.get_targets = get_targets_cb
        self.set_targets = set_targets_cb
        self.on_config_change = on_config_change or (lambda: None)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Alias", "Host", "Interval (s)", "Timeout (ms)", "Enabled"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add target")
        add_btn.clicked.connect(self._add_row)
        edit_btn = QPushButton("Edit selected")
        edit_btn.clicked.connect(self._edit_row)
        remove_btn = QPushButton("Remove selected")
        remove_btn.clicked.connect(self._remove_row)
        import_btn = QPushButton("Import JSON...")
        import_btn.clicked.connect(self._import_json)
        export_btn = QPushButton("Export JSON...")
        export_btn.clicked.connect(self._export_json)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(remove_btn)
        btn_layout.addWidget(import_btn)
        btn_layout.addWidget(export_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def refresh_table(self):
        try:
            self.table.cellChanged.disconnect(self._on_cell_changed)
        except Exception:
            pass
        targets = self.get_targets()
        self.table.setRowCount(len(targets))
        for i, t in enumerate(targets):
            self.table.setItem(i, 0, QTableWidgetItem(t.alias))
            self.table.setItem(i, 1, QTableWidgetItem(t.host))
            self.table.setItem(i, 2, QTableWidgetItem(str(t.interval)))
            self.table.setItem(i, 3, QTableWidgetItem(str(t.timeout)))
            en = QTableWidgetItem("Yes" if t.enabled else "No")
            en.setFlags(en.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 4, en)
        self.table.cellChanged.connect(self._on_cell_changed)

    def _on_cell_changed(self, row: int, col: int):
        self.table.cellChanged.disconnect(self._on_cell_changed)
        targets = self.get_targets()
        if 0 <= row < len(targets):
            t = targets[row]
            try:
                if col == 0:
                    t.alias = self.table.item(row, 0).text().strip() or "Unnamed"
                elif col == 1:
                    t.host = self.table.item(row, 1).text().strip()
                elif col == 2:
                    t.interval = max(1, int(self.table.item(row, 2).text()))
                elif col == 3:
                    t.timeout = max(100, int(self.table.item(row, 3).text()))
            except (ValueError, AttributeError):
                pass
            self.set_targets(targets)
            self.on_config_change()
        self.table.cellChanged.connect(self._on_cell_changed)

    def _add_row(self):
        targets = self.get_targets()
        targets.append(TargetConfig(alias="New", host="127.0.0.1", interval=60, timeout=1000, enabled=True))
        self.set_targets(targets)
        self.refresh_table()
        self.on_config_change()

    def _edit_row(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Edit", "Select a row first.")
            return
        targets = self.get_targets()
        if row >= len(targets):
            return
        t = targets[row]
        # Toggle enabled on double-click or provide a simple way
        t.enabled = not t.enabled
        self.set_targets(targets)
        self.refresh_table()
        self.on_config_change()

    def _remove_row(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Remove", "Select a row first.")
            return
        targets = self.get_targets()
        if 0 <= row < len(targets):
            targets.pop(row)
            self.set_targets(targets)
            self.refresh_table()
            self.on_config_change()

    def _import_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import targets", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            targets_list = data if isinstance(data, list) else data.get("targets", [])
            targets = [dict_to_target(d) for d in targets_list]
            self.set_targets(targets)
            self.refresh_table()
            self.on_config_change()
            QMessageBox.information(self, "Import", f"Imported {len(targets)} targets.")
        except Exception as e:
            QMessageBox.warning(self, "Import error", str(e))

    def _export_json(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export targets", "", "JSON (*.json)")
        if not path:
            return
        try:
            targets = self.get_targets()
            data = [target_to_dict(t) for t in targets]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            QMessageBox.information(self, "Export", f"Exported {len(targets)} targets.")
        except Exception as e:
            QMessageBox.warning(self, "Export error", str(e))
