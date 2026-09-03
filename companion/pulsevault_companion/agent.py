"""The sync agent.

Each cycle: (1) auto-pull new .fit files off the connected watch into the inbox
folder, then (2) drain the inbox — upload each file and delete it on success.
Manual drops into the inbox are handled the same way. Idempotent and safe to run
continuously.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from . import inbox
from .config import Config
from .pull import platform_puller
from .sources import build_source
from .state import State
from .uploader import Uploader

log = logging.getLogger("pulsevault.agent")


class Agent:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.state = State(cfg.resolved_state_file())
        self.uploader = Uploader(cfg.server_url, cfg.token, cfg.verify_tls)
        self.fit_dir = cfg.resolved_fit_dir()
        self.puller = platform_puller() if cfg.auto_pull else None
        # Advanced: any explicitly-configured sources also feed the inbox.
        self.extra = [build_source(spec) for spec in cfg.sources]

    def _pull(self) -> int:
        pulled = 0
        if self.puller is not None:
            try:
                if self.puller.available():
                    pulled += self.puller.copy_new(self.fit_dir, self.state)
            except Exception as exc:  # noqa: BLE001
                log.warning("auto-pull failed: %s", exc)
        for src in self.extra:
            try:
                if not src.available():
                    continue
                for f in src.list_files():
                    if self.state.is_new(f.key, f.size):
                        (self.fit_dir / Path(f.key).name).write_bytes(f.read())
                        self.state.mark(f.key, f.size)
                        pulled += 1
            except NotImplementedError:
                continue
            except Exception as exc:  # noqa: BLE001
                log.warning("source %s failed: %s", getattr(src, "name", "?"), exc)
        return pulled

    def cycle(self) -> tuple[int, int]:
        """One pull + drain. Returns (pulled, uploaded)."""
        pulled = self._pull()
        uploaded = inbox.drain(self.fit_dir, self.uploader)
        return pulled, uploaded

    def sync_once(self) -> int:
        pulled, uploaded = self.cycle()
        log.info("pulled %d, uploaded %d", pulled, uploaded)
        return uploaded

    def run_forever(self) -> None:
        log.info("agent started — server=%s inbox=%s interval=%ds auto_pull=%s",
                 self.cfg.server_url, self.fit_dir, self.cfg.poll_interval,
                 self.puller.name if self.puller else "off")
        while True:
            try:
                pulled, uploaded = self.cycle()
                if pulled or uploaded:
                    log.info("cycle: pulled %d, uploaded %d", pulled, uploaded)
            except Exception as exc:  # noqa: BLE001
                log.exception("cycle error: %s", exc)
            time.sleep(max(15, self.cfg.poll_interval))
