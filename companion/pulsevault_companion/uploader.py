"""Uploads raw FIT bytes to the PulseVault server."""
from __future__ import annotations

import logging

import requests

log = logging.getLogger("pulsevault.upload")


class Uploader:
    def __init__(self, server_url: str, token: str, verify_tls: bool = True):
        self.endpoint = server_url.rstrip("/") + "/api/ingest/fit"
        self.token = token
        self.verify_tls = verify_tls

    def upload(self, files: list[tuple[str, bytes]]) -> dict:
        """POST a batch of (filename, bytes). Returns the server's JSON summary."""
        multipart = [("files", (name, data, "application/octet-stream")) for name, data in files]
        resp = requests.post(
            self.endpoint,
            files=multipart,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=120,
            verify=self.verify_tls,
        )
        resp.raise_for_status()
        return resp.json()
