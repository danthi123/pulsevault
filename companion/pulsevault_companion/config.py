"""Companion configuration: a TOML file, overridable by environment variables.

Kept deliberately small and OS-neutral. Source backends read their own options
out of the per-source ``[sources.*]`` tables.
"""
from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _base_dir() -> Path:
    """The folder the app lives in — next to the exe when frozen, else cwd."""
    if getattr(sys, "frozen", False):
        return Path(os.path.dirname(sys.executable))
    return Path.cwd()


@dataclass
class Config:
    server_url: str = "http://localhost:8080"
    token: str = ""
    poll_interval: int = 60  # seconds between cycles
    verify_tls: bool = True
    log_level: str = "INFO"
    state_file: str = ""  # default computed under the user state dir
    # Inbox folder: drained on every cycle — each .fit is uploaded, then DELETED
    # on success. Default is "FIT" next to the executable.
    fit_dir: str = ""
    # Auto-pull new .fit files off the connected watch into the inbox each cycle
    # (Linux: MTP auto-detect; Windows: experimental; else off).
    auto_pull: bool = True
    # Advanced: extra source specs, each {"type": "folder"|"mtp"|"ble", ...opts}.
    sources: list[dict[str, Any]] = field(default_factory=list)

    def resolved_fit_dir(self) -> Path:
        # A relative fit_dir (e.g. the default "FIT") is anchored to the app's own
        # folder — NOT the process CWD — and always returned ABSOLUTE. Windows'
        # Shell.Namespace() (used by the MTP auto-pull) returns null for a
        # relative path, so this must be absolute or auto-pull silently no-ops.
        raw = Path(self.fit_dir).expanduser() if self.fit_dir else Path("FIT")
        p = raw if raw.is_absolute() else _base_dir() / raw
        p = p.resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    def resolved_state_file(self) -> Path:
        if self.state_file:
            return Path(self.state_file).expanduser()
        base = os.environ.get("XDG_STATE_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "state"
        )
        d = Path(base) / "pulsevault-companion"
        d.mkdir(parents=True, exist_ok=True)
        return d / "state.json"


def _exe_dir_config() -> str:
    # When packaged as a PyInstaller binary, look for config.toml next to the exe
    # (so the downloaded zip's config.toml is picked up automatically).
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), "config.toml")
    return ""


DEFAULT_PATHS = [
    os.environ.get("PV_CONFIG", ""),
    _exe_dir_config(),
    os.path.join(os.getcwd(), "config.toml"),
    os.path.join(os.path.expanduser("~"), ".config", "pulsevault-companion", "config.toml"),
]


def load(path: str | None = None) -> Config:
    cfg = Config()
    chosen = path or next((p for p in DEFAULT_PATHS if p and os.path.isfile(p)), None)
    if chosen:
        with open(chosen, "rb") as f:
            data = tomllib.load(f)
        for key in ("server_url", "token", "poll_interval", "verify_tls",
                    "log_level", "state_file", "fit_dir", "auto_pull"):
            if key in data:
                setattr(cfg, key, data[key])
        cfg.sources = data.get("sources", cfg.sources)

    # Environment overrides (handy for systemd / containers).
    cfg.server_url = os.environ.get("PV_SERVER_URL", cfg.server_url)
    cfg.token = os.environ.get("PV_TOKEN", cfg.token)
    if os.environ.get("PV_POLL_INTERVAL"):
        cfg.poll_interval = int(os.environ["PV_POLL_INTERVAL"])
    return cfg
