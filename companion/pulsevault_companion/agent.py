"""The sync agent: detect the watch through each configured source and push new
FIT files to the server. Idempotent and safe to run continuously."""
from __future__ import annotations

import logging
import time

from .config import Config
from .sources import build_source
from .state import State
from .uploader import Uploader

log = logging.getLogger("pulsevault.agent")

BATCH = 15  # files per upload request


class Agent:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.state = State(cfg.resolved_state_file())
        self.uploader = Uploader(cfg.server_url, cfg.token, cfg.verify_tls)
        self.sources = [build_source(spec) for spec in cfg.sources]

    def sync_once(self) -> int:
        """Scan all sources once; upload new files. Returns files uploaded."""
        uploaded = 0
        for source in self.sources:
            try:
                if not source.available():
                    continue
                files = source.list_files()
            except NotImplementedError:
                continue
            except Exception as exc:  # noqa: BLE001
                log.warning("source %s scan failed: %s", source.name, exc)
                continue

            new = [f for f in files if self.state.is_new(f.key, f.size)]
            if not new:
                log.info("source %s: nothing new (%d files on device)", source.name, len(files))
                continue
            log.info("source %s: %d new file(s) to upload", source.name, len(new))

            for i in range(0, len(new), BATCH):
                batch = new[i : i + BATCH]
                try:
                    payload = [(f.key.replace("/", "_"), f.read()) for f in batch]
                    summary = self.uploader.upload(payload)
                    log.info("uploaded %d/%d (server accepted %s)",
                             len(batch), len(new), summary.get("accepted"))
                    for f in batch:
                        self.state.mark(f.key, f.size)
                        uploaded += 1
                except Exception as exc:  # noqa: BLE001
                    log.error("upload failed for batch: %s", exc)
                    break
        return uploaded

    def run_forever(self) -> None:
        log.info("agent started — server=%s interval=%ds sources=%s",
                 self.cfg.server_url, self.cfg.poll_interval,
                 [s.name for s in self.sources])
        while True:
            try:
                n = self.sync_once()
                if n:
                    log.info("cycle complete: %d file(s) uploaded", n)
            except Exception as exc:  # noqa: BLE001
                log.exception("sync cycle error: %s", exc)
            time.sleep(max(15, self.cfg.poll_interval))
