"""
Notifications and sound. First DOWN of an outage: notification WITH sound (play wav once).
Subsequent DOWN: notification WITHOUT sound. DOWN -> UP: "reachable again" once.
Uses system tray balloon when available; no extra dependency (PySide6 QSystemTrayIcon).
"""
import logging
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("pingu.notify")

# Callback for "show notification" - set by GUI (tray or in-app toast)
_notify_callback: Optional[Callable[[str, str, bool], None]] = None


def set_notify_callback(cb: Callable[[str, str, bool], None]) -> None:
    """cb(title, message, play_sound)."""
    global _notify_callback
    _notify_callback = cb


def notify(title: str, message: str, play_sound: bool = False) -> None:
    if play_sound:
        play_alert_sound()
    if _notify_callback:
        try:
            _notify_callback(title, message, play_sound)
        except Exception as e:
            logger.exception("Notification failed: %s", e)
    else:
        logger.info("Notify [sound=%s]: %s - %s", play_sound, title, message)


def play_alert_sound() -> None:
    """Play alert.wav once. Cross-platform via QSoundEffect or winsound / afplay."""
    path = _get_alert_path()
    if not path or not path.exists():
        logger.debug("No alert sound at %s", path)
        return
    try:
        import sys
        if sys.platform == "win32":
            import winsound
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_NOSTOP)
        elif sys.platform == "darwin":
            import subprocess
            subprocess.run(["afplay", str(path)], capture_output=True, timeout=2)
        else:
            import subprocess
            subprocess.run(["aplay", str(path)], capture_output=True, timeout=2)
    except Exception as e:
        logger.debug("Could not play sound: %s", e)


def _get_alert_path() -> Optional[Path]:
    # App dir next to package, then config dir
    base = Path(__file__).resolve().parent.parent
    for name in ("resources/alert.wav", "alert.wav"):
        p = base / name
        if p.exists():
            return p
    return get_config_alert_path()


def get_config_alert_path() -> Path:
    from core.config import get_config_dir
    return get_config_dir() / "alert.wav"
