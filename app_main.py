"""
Pingu – ICMP host monitor. Entry point.
- GUI mode (default) or --headless
- Single-instance (lock file / named mutex)
- Minimize to tray when closed (configurable)
- Run at startup (Windows Task Scheduler, no admin)
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path
from queue import Queue

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.config import load_config, get_config_dir, dict_to_target
from core.logging_setup import setup_logging
from core.monitor import MonitorState, run_monitor, MonitorUpdate


def single_instance_lock():
    """
    Cross-platform single-instance guard.

    On Windows: use a named mutex via Win32 API, which avoids stale lock files.
    On POSIX: use an advisory file lock in the app data directory.

    Returns a handle that must be kept alive; if another instance already holds
    the lock, returns None.
    """
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            CreateMutexW = kernel32.CreateMutexW
            CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
            CreateMutexW.restype = wintypes.HANDLE

            mutex_name = "Global\\PinguSingleInstanceMutex"
            handle = CreateMutexW(None, False, mutex_name)
            if not handle:
                return None

            ERROR_ALREADY_EXISTS = 183
            err = ctypes.get_last_error()
            if err == ERROR_ALREADY_EXISTS:
                # Another instance already created the mutex
                kernel32.CloseHandle(handle)
                return None

            # Keep handle open for the lifetime of the process
            return handle
        except Exception:
            # Fallback: no locking
            return None

    # POSIX: file lock
    lock_file = get_config_dir() / "pingu.lock"
    try:
        import fcntl
        import os

        fd = open(lock_file, "w")
        fd.write(str(os.getpid()))
        fd.flush()
        try:
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except (OSError, BlockingIOError):
            fd.close()
            return None
    except Exception:
        return None


def run_headless():
    config = load_config()
    log_path = config.get("log_path") or ""
    logger = setup_logging(log_path if log_path else None)
    logger.info("Pingu started (headless)")
    targets = [dict_to_target(d) for d in config.get("targets", [])]
    jitter = config.get("jitter_ms", [0, 300])
    state = MonitorState(
        targets=targets,
        concurrency=config.get("concurrency", 5),
        jitter_ms=(jitter[0], jitter[1]) if len(jitter) >= 2 else (0, 300),
        display_mode=config.get("display_mode", "latency"),
        notifications_enabled=config.get("notifications_enabled", True),
        sound_on_down=config.get("sound_on_down", True),
    )
    state.thread_safe_queue = None
    try:
        asyncio.run(run_monitor(state))
    except KeyboardInterrupt:
        pass
    logger.info("Pingu stopped (headless)")


def run_gui():
    from PySide6.QtWidgets import QApplication
    from gui.main_window import MainWindow

    lock_fd = single_instance_lock()
    if lock_fd is None:
        print("Another instance of Pingu is already running.", file=sys.stderr)
        sys.exit(1)

    config = load_config()
    log_path = config.get("log_path") or ""
    setup_logging(log_path if log_path else None)
    logging.getLogger("pingu").info("Pingu started (GUI)")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    win = MainWindow()
    win.show()
    try:
        sys.exit(app.exec())
    finally:
        if lock_fd is not None:
            try:
                if sys.platform == "win32":
                    import ctypes
                    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                    kernel32.CloseHandle(lock_fd)
                else:
                    lock_fd.close()
            except Exception:
                pass


def run_at_startup_enable(enable: bool):
    """Windows Task Scheduler: create/delete task for current user (no admin)."""
    if sys.platform != "win32":
        return
    import subprocess
    exe = sys.executable
    args = [__file__]
    work_dir = str(Path(__file__).resolve().parent)
    task_name = "Pingu"
    if enable:
        cmd = [
            "schtasks", "/Create", "/TN", task_name,
            "/TR", f'"{exe}" "{Path(__file__).resolve()}"',
            "/SC", "ONLOGON", "/RL", "HIGHEST", "/F"
        ]
        subprocess.run(cmd, capture_output=True, cwd=work_dir)
    else:
        subprocess.run(["schtasks", "/Delete", "/TN", task_name, "/F"], capture_output=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pingu – ICMP host monitor")
    parser.add_argument("--headless", action="store_true", help="Run monitoring without GUI")
    args = parser.parse_args()
    if args.headless:
        run_headless()
    else:
        run_gui()
