"""Main window: tabs (Targets, Live Monitor, Settings, Log Viewer), Start/Stop, tray."""
import asyncio
import logging
from queue import Queue
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QTabWidget,
    QPushButton,
    QHBoxLayout,
    QSystemTrayIcon,
    QApplication,
    QMenu,
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon, QAction

from core.config import (
    load_config,
    save_config,
    TargetConfig,
    dict_to_target,
    target_to_dict,
    get_config_dir,
)
from core.monitor import MonitorState, MonitorUpdate, run_monitor
from core import notify

from gui.targets_tab import TargetsTab
from gui.monitor_tab import MonitorTab
from gui.settings_tab import SettingsTab
from gui.log_viewer import LogViewer
from gui.credits_tab import CreditsTab

logger = logging.getLogger("pingu.gui")


class MainWindow(QMainWindow):
    def __init__(self, close_to_tray: bool | None = None):
        super().__init__()
        self.setWindowTitle("Pingu – Host Monitor")
        self._config = load_config()
        self.close_to_tray = (close_to_tray if close_to_tray is not None else self._config.get("close_to_tray", True))
        self._monitor_state = self._state_from_config()
        self._thread_safe_queue: Queue = Queue()
        self._monitor_state.thread_safe_queue = self._thread_safe_queue
        self._monitor_task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._monitor_thread = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Start/Stop
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start monitoring")
        self.start_btn.clicked.connect(self._start_monitor)
        self.stop_btn = QPushButton("Stop monitoring")
        self.stop_btn.clicked.connect(self._stop_monitor)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Tabs
        tabs = QTabWidget()
        self.targets_tab = TargetsTab(
            get_targets_cb=self._get_targets,
            set_targets_cb=self._set_targets,
            on_config_change=self._on_config_change,
        )
        self.monitor_tab = MonitorTab()
        self.settings_tab = SettingsTab(
            get_config_cb=lambda: self._config,
            set_config_cb=self._set_config,
            on_startup_toggle=self._on_startup_toggle_cb,
        )
        self.log_viewer = LogViewer(self._config.get("log_path") or None)
        self.credits_tab = CreditsTab()

        tabs.addTab(self.targets_tab, "Targets")
        tabs.addTab(self.monitor_tab, "Live Monitor")
        tabs.addTab(self.settings_tab, "Settings")
        tabs.addTab(self.log_viewer, "Log Viewer")
        tabs.addTab(self.credits_tab, "Credits")
        layout.addWidget(tabs)

        self.targets_tab.refresh_table()
        self._sync_monitor_display_targets()
        self.settings_tab.load_from_config(self._config)

        # Tray + application icon (app-local only, so it ships cleanly)
        self.tray_icon = QSystemTrayIcon(self)
        if self.tray_icon.isSystemTrayAvailable():
            icon_path = Path(__file__).parent.parent / "resources" / "icon.png"
            if icon_path.exists():
                icon = QIcon(str(icon_path))
                self.tray_icon.setIcon(icon)
                self.setWindowIcon(icon)
            tray_menu = QMenu()
            show_action = QAction("Show", self)
            show_action.triggered.connect(self.show_from_tray)
            quit_action = QAction("Quit", self)
            quit_action.triggered.connect(self._quit_app)
            tray_menu.addAction(show_action)
            tray_menu.addAction(quit_action)
            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.activated.connect(self._on_tray_activated)
            self.tray_icon.show()
        else:
            self.tray_icon = None

        notify.set_notify_callback(self._show_notification)

        # Drain monitor queue on timer (UI thread)
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._drain_monitor_queue)
        self._poll_timer.start(200)

    def _state_from_config(self) -> MonitorState:
        targets = [dict_to_target(d) for d in self._config.get("targets", [])]
        jitter = self._config.get("jitter_ms", [0, 300])
        jitter_t = (jitter[0], jitter[1]) if len(jitter) >= 2 else (0, 300)
        return MonitorState(
            targets=targets,
            concurrency=self._config.get("concurrency", 5),
            jitter_ms=jitter_t,
            display_mode=self._config.get("display_mode", "latency"),
            notifications_enabled=self._config.get("notifications_enabled", True),
            sound_on_down=self._config.get("sound_on_down", True),
        )

    def _get_targets(self):
        return self._monitor_state.targets

    def _set_targets(self, targets: list):
        self._monitor_state.targets = targets
        self._config["targets"] = [target_to_dict(t) for t in targets]
        save_config(self._config)
        self._sync_monitor_display_targets()

    def _set_config(self, config: dict):
        self._config = config
        self.close_to_tray = config.get("close_to_tray", True)
        save_config(self._config)
        # Update monitor state for display_mode, concurrency, etc.
        self._monitor_state.concurrency = config.get("concurrency", 5)
        j = config.get("jitter_ms", [0, 300])
        self._monitor_state.jitter_ms = (j[0], j[1]) if len(j) >= 2 else (0, 300)
        self._monitor_state.display_mode = config.get("display_mode", "latency")
        self._monitor_state.notifications_enabled = config.get("notifications_enabled", True)
        self._monitor_state.sound_on_down = config.get("sound_on_down", True)
        if config.get("log_path"):
            self.log_viewer.set_log_path(config["log_path"])

    def _on_config_change(self):
        self._config["targets"] = [target_to_dict(t) for t in self._monitor_state.targets]
        save_config(self._config)
        self._sync_monitor_display_targets()

    def _sync_monitor_display_targets(self):
        self.monitor_tab.set_targets([(t.alias, t.host) for t in self._monitor_state.targets])

    def _on_startup_toggle_cb(self, enabled: bool):
        try:
            from app_main import run_at_startup_enable
            run_at_startup_enable(enabled)
        except Exception as e:
            logger.warning("Run at startup toggle failed: %s", e)

    def _show_notification(self, title: str, message: str, play_sound: bool):
        if self.tray_icon and self.tray_icon.isSystemTrayAvailable():
            self.tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Warning, 3000)

    def _drain_monitor_queue(self):
        while True:
            try:
                update = self._thread_safe_queue.get_nowait()
            except Exception:
                break
            if isinstance(update, MonitorUpdate):
                self.monitor_tab.apply_update(update)

    def _start_monitor(self):
        if self._monitor_task is not None:
            return
        self._monitor_state.targets = self._get_targets()
        self._monitor_state.ensure_structures()
        self._loop = asyncio.new_event_loop()
        self._monitor_task = self._loop.create_task(run_monitor(self._monitor_state))
        self._monitor_thread = __import__("threading").Thread(target=self._run_loop, daemon=True)
        self._monitor_thread.start()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        logger.info("Monitoring started")

    def _run_loop(self):
        # Capture loop/task locally so _stop_monitor can safely clear attributes
        loop = self._loop
        task = self._monitor_task
        if loop is None or task is None:
            return

        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(task)
        except asyncio.CancelledError:
            pass
        finally:
            try:
                if not loop.is_closed():
                    loop.close()
            except Exception:
                pass

    def _stop_monitor(self):
        if self._loop is None or self._monitor_task is None:
            return
        # Ask the background loop to cancel the task; the thread will close the loop.
        try:
            self._loop.call_soon_threadsafe(self._monitor_task.cancel)
        except Exception:
            pass
        self._monitor_task = None
        self._loop = None
        self._monitor_thread = None
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        logger.info("Monitoring stopped")

    def show_from_tray(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_from_tray()

    def closeEvent(self, event):
        if self.close_to_tray and self.tray_icon and self.tray_icon.isSystemTrayAvailable():
            self.hide()
            event.ignore()
        else:
            self._stop_monitor()
            event.accept()

    def _quit_app(self):
        self._stop_monitor()
        QApplication.quit()
