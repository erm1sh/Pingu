"""
Load/save application config (JSON) in user app data directory.
Auto-save on changes; targets with alias, host, interval, timeout, enabled.
"""
import json
import os
import sys
from pathlib import Path
from typing import Any

# Default config
DEFAULT_CONCURRENCY = 5
DEFAULT_JITTER_MS = (0, 300)
DISPLAY_MODES = ("latency", "codes")
DEFAULT_DISPLAY_MODE = "latency"
CLOSE_TO_TRAY_DEFAULT = True
RUN_AT_STARTUP_DEFAULT = False


def get_config_dir() -> Path:
    """User app data directory for config and logs."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~")
    return Path(base) / "Pingu"


def get_config_path() -> Path:
    return get_config_dir() / "config.json"


def get_default_config() -> dict[str, Any]:
    return {
        "targets": [],
        "concurrency": DEFAULT_CONCURRENCY,
        "jitter_ms": list(DEFAULT_JITTER_MS),
        "display_mode": DEFAULT_DISPLAY_MODE,
        "close_to_tray": CLOSE_TO_TRAY_DEFAULT,
        "run_at_startup": RUN_AT_STARTUP_DEFAULT,
        "log_path": "",
        "notifications_enabled": True,
        "sound_on_down": True,
    }


def ensure_config_dir() -> None:
    get_config_dir().mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    path = get_config_path()
    if not path.exists():
        return get_default_config()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Merge with defaults so new keys exist
        default = get_default_config()
        for k, v in default.items():
            if k not in data:
                data[k] = v
        return data
    except (json.JSONDecodeError, OSError):
        return get_default_config()


def save_config(config: dict[str, Any]) -> None:
    ensure_config_dir()
    path = get_config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def target_to_dict(t: "TargetConfig") -> dict[str, Any]:
    return {
        "alias": t.alias,
        "host": t.host,
        "interval": t.interval,
        "timeout": t.timeout,
        "enabled": t.enabled,
    }


def dict_to_target(d: dict[str, Any]) -> "TargetConfig":
    return TargetConfig(
        alias=str(d.get("alias", "")).strip() or "Unnamed",
        host=str(d.get("host", "")).strip(),
        interval=int(d.get("interval", 60)),
        timeout=int(d.get("timeout", 1000)),
        enabled=bool(d.get("enabled", True)),
    )


class TargetConfig:
    __slots__ = ("alias", "host", "interval", "timeout", "enabled")

    def __init__(
        self,
        alias: str,
        host: str,
        interval: int = 60,
        timeout: int = 1000,
        enabled: bool = True,
    ):
        self.alias = alias.strip() or "Unnamed"
        self.host = host.strip()
        self.interval = max(1, int(interval))
        self.timeout = max(100, int(timeout))
        self.enabled = bool(enabled)
