"""Log viewer panel: last ~200 lines from current log file."""
import logging
from pathlib import Path

from PySide6.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit, QPushButton, QHBoxLayout
from PySide6.QtCore import QTimer

from core.config import get_config_dir


class LogViewer(QWidget):
    LINES = 200

    def __init__(self, log_path: str | None = None):
        super().__init__()
        # In settings we treat this as a *directory*; default is AppData/Pingu/logs/pingu.log
        self._log_dir = Path(log_path) if log_path else get_config_dir() / "logs"
        layout = QVBoxLayout(self)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        layout.addWidget(self.text)
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(5000)
        self.refresh()

    def _current_log_file(self) -> Path:
        """
        Resolve the actual log file.

        If the configured path is a directory (recommended), we look for
        '<dir>/pingu.log'. If it's already a file path, we use it directly.
        """
        base = self._log_dir
        # If it looks like a directory (no suffix or exists as dir), treat as dir
        if base.is_dir() or base.suffix == "":
            return base / "pingu.log"
        return base

    def refresh(self):
        log_file = self._current_log_file()
        if not log_file.exists():
            self.text.setPlainText(f"(Log file not found: {log_file})")
            return
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            tail = lines[-self.LINES:] if len(lines) > self.LINES else lines
            self.text.setPlainText("".join(tail))
            self.text.verticalScrollBar().setValue(self.text.verticalScrollBar().maximum())
        except Exception as e:
            self.text.setPlainText(f"Error reading log: {e}")

    def set_log_path(self, path: str):
        # Store as directory-or-file; _current_log_file will resolve correctly
        self._log_dir = Path(path) if path else get_config_dir() / "logs"
        self.refresh()
