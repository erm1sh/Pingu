"""Live Monitor tab: list by alias with '<ALIAS> - OK <DETAIL>' / '<ALIAS> - DOWN <DETAIL>'."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView
from PySide6.QtCore import Qt

from core.monitor import MonitorUpdate


class MonitorTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Status", "Host"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)
        self._rows: dict[str, int] = {}  # alias -> row index

    def apply_update(self, update: MonitorUpdate):
        """Update or add row for this alias. First column is exactly '<ALIAS> - OK <DETAIL>' or DOWN."""
        alias = update.alias
        if alias not in self._rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._rows[alias] = row
        row = self._rows[alias]
        self.table.setItem(row, 0, QTableWidgetItem(update.line))
        self.table.setItem(row, 1, QTableWidgetItem(update.host))

    def set_targets(self, aliases_with_hosts: list[tuple[str, str]]):
        """Reset display to match current target list (alias, host). Clears status until updates arrive."""
        self.table.setRowCount(0)
        self._rows.clear()
        for alias, host in aliases_with_hosts:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._rows[alias] = row
            self.table.setItem(row, 0, QTableWidgetItem(f"{alias} - ..."))
            self.table.setItem(row, 1, QTableWidgetItem(host))
