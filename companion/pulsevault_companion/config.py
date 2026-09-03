"""Companion configuration: a TOML file, overridable by environment variables.

Kept deliberately small and OS-neutral. Source backends read their own options
out of the per-source ``[sources.*]`` tables.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Config:
    server_url: str = "http://localhost:8080"
    token: str = ""
    poll_interval: int = 300  # seconds between scans
    verify_tls: bool = True
    log_level: str = "INFO"
    state_file: str = ""  # default computed under the user state dir
    # Ordered list of source specs, each {"type": "folder"|"mtp"|"ble", ...opts}.
    sources: list[dict[str, Any]] = field(default_factory=list)

    def resolved_state_file(self) -> Path:
        if self.state_file:
            return Path(self.state_file).expanduser()
        base = os.environ.get("XDG_STATE_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "state"
        )
        d = Path(base) / "pulsevault-companion"
        d.mkdir(parents=True, exist_ok=True)
        return d / "state.json"


DEFAULT_PATHS = [
    os.environ.get("PV_CONFIG", ""),
    os.path.join(os.getcwd(), "config.toml"),
    os.path.join(os.path.expanduser("~"), ".config", "pulsevault-companion", "config.toml"),
]


def load(path: str | None = None) -> Config:
    cfg = Config()
    chosen = path or next((p for p in DEFAULT_PATHS if p and os.path.isfile(p)), None)
    if chosen:
        with open(chosen, "rb") as f:
            data = tomllib.load(f)
        for key in ("server_url", "token", "poll_interval", "verify_tls", "log_level", "state_file"):
            if key in data:
                setattr(cfg, key, data[key])
        cfg.sources = data.get("sources", cfg.sources)

    # Environment overrides (handy for systemd / containers).
    cfg.server_url = os.environ.get("PV_SERVER_URL", cfg.server_url)
    cfg.token = os.environ.get("PV_TOKEN", cfg.token)
    if os.environ.get("PV_POLL_INTERVAL"):
        cfg.poll_interval = int(os.environ["PV_POLL_INTERVAL"])

    # Sensible default: if no sources configured, try MTP auto-detect.
    if not cfg.sources:
        cfg.sources = [{"type": "mtp"}]
    return cfg
