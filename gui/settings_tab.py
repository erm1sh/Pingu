"""Settings: concurrency, jitter, notifications, display mode, tray/close, startup, log path."""
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QSpinBox,
    QComboBox,
    QCheckBox,
    QLineEdit,
    QLabel,
    QPushButton,
    QFileDialog,
    QGroupBox,
)
from PySide6.QtCore import Qt

from core.config import (
    DISPLAY_MODES,
    DEFAULT_CONCURRENCY,
    DEFAULT_JITTER_MS,
    get_config_dir,
)


class SettingsTab(QWidget):
    def __init__(self, get_config_cb, set_config_cb, on_startup_toggle=None):
        super().__init__()
        self.get_config = get_config_cb
        self.set_config = set_config_cb
        self.on_startup_toggle = on_startup_toggle or (lambda v: None)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Monitoring
        grp = QGroupBox("Monitoring")
        form = QFormLayout(grp)
        self.concurrency = QSpinBox()
        self.concurrency.setRange(1, 50)
        self.concurrency.setValue(DEFAULT_CONCURRENCY)
        form.addRow("Global concurrency limit:", self.concurrency)
        self.jitter_min = QSpinBox()
        self.jitter_min.setRange(0, 2000)
        self.jitter_min.setSuffix(" ms")
        self.jitter_min.setValue(DEFAULT_JITTER_MS[0])
        self.jitter_max = QSpinBox()
        self.jitter_max.setRange(0, 2000)
        self.jitter_max.setSuffix(" ms")
        self.jitter_max.setValue(DEFAULT_JITTER_MS[1])
        jitter_layout = QHBoxLayout()
        jitter_layout.addWidget(self.jitter_min)
        jitter_layout.addWidget(QLabel("–"))
        jitter_layout.addWidget(self.jitter_max)
        form.addRow("Jitter range:", jitter_layout)
        layout.addWidget(grp)

        # Display
        grp2 = QGroupBox("Display")
        form2 = QFormLayout(grp2)
        self.display_mode = QComboBox()
        self.display_mode.addItems(DISPLAY_MODES)
        form2.addRow("Display mode:", self.display_mode)
        layout.addWidget(grp2)

        # Notifications
        grp3 = QGroupBox("Notifications")
        form3 = QFormLayout(grp3)
        self.notifications_enabled = QCheckBox("Enable notifications")
        self.notifications_enabled.setChecked(True)
        form3.addRow(self.notifications_enabled)
        self.sound_on_down = QCheckBox("Play sound on first DOWN of an outage")
        self.sound_on_down.setChecked(True)
        form3.addRow(self.sound_on_down)
        layout.addWidget(grp3)

        # Behavior
        grp4 = QGroupBox("Behavior")
        form4 = QFormLayout(grp4)
        self.close_to_tray = QCheckBox("Minimize to tray when window is closed")
        self.close_to_tray.setChecked(True)
        form4.addRow(self.close_to_tray)
        self.run_at_startup = QCheckBox("Run at startup (Windows Task Scheduler)")
        self.run_at_startup.setChecked(False)
        self.run_at_startup.toggled.connect(self._on_startup_changed)
        form4.addRow(self.run_at_startup)
        layout.addWidget(grp4)

        # Log path
        grp5 = QGroupBox("Logging")
        form5 = QFormLayout(grp5)
        path_layout = QHBoxLayout()
        self.log_path = QLineEdit()
        self.log_path.setPlaceholderText("(default: AppData/Pingu/logs)")
        path_layout.addWidget(self.log_path)
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._browse_log_path)
        path_layout.addWidget(browse)
        form5.addRow("Log directory:", path_layout)
        layout.addWidget(grp5)

        layout.addStretch()

        # Connect apply
        for w in (self.concurrency, self.jitter_min, self.jitter_max, self.display_mode,
                  self.notifications_enabled, self.sound_on_down, self.close_to_tray,
                  self.run_at_startup, self.log_path):
            if hasattr(w, "valueChanged"):
                w.valueChanged.connect(self._apply)
            elif hasattr(w, "currentIndexChanged"):
                w.currentIndexChanged.connect(self._apply)
            elif hasattr(w, "stateChanged"):
                w.stateChanged.connect(self._apply)
            elif hasattr(w, "textChanged"):
                w.textChanged.connect(self._apply)

    def _on_startup_changed(self, checked: bool):
        self.on_startup_toggle(checked)
        self._apply()

    def _browse_log_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select log directory", str(get_config_dir()))
        if path:
            self.log_path.setText(path)

    def _apply(self):
        c = self.get_config()
        c["concurrency"] = self.concurrency.value()
        c["jitter_ms"] = [self.jitter_min.value(), self.jitter_max.value()]
        c["display_mode"] = self.display_mode.currentText()
        c["notifications_enabled"] = self.notifications_enabled.isChecked()
        c["sound_on_down"] = self.sound_on_down.isChecked()
        c["close_to_tray"] = self.close_to_tray.isChecked()
        c["run_at_startup"] = self.run_at_startup.isChecked()
        c["log_path"] = self.log_path.text().strip()
        self.set_config(c)

    def load_from_config(self, config: dict):
        self.concurrency.setValue(config.get("concurrency", DEFAULT_CONCURRENCY))
        j = config.get("jitter_ms", list(DEFAULT_JITTER_MS))
        self.jitter_min.setValue(j[0] if len(j) > 0 else DEFAULT_JITTER_MS[0])
        self.jitter_max.setValue(j[1] if len(j) > 1 else DEFAULT_JITTER_MS[1])
        mode = config.get("display_mode", "latency")
        idx = self.display_mode.findText(mode)
        if idx >= 0:
            self.display_mode.setCurrentIndex(idx)
        self.notifications_enabled.setChecked(config.get("notifications_enabled", True))
        self.sound_on_down.setChecked(config.get("sound_on_down", True))
        self.close_to_tray.setChecked(config.get("close_to_tray", True))
        self.run_at_startup.setChecked(config.get("run_at_startup", False))
        self.log_path.setText(config.get("log_path", ""))
