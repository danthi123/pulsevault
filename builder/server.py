#!/usr/bin/env python3
"""Tiny internal build service: compiles the Vaultwrist Connect IQ app with a
caller-supplied server URL + ingest token baked in, and returns the .prg.

Internal-only (not exposed publicly); the PulseVault backend calls it and passes
the instance's own URL + ingest token. Inputs are strictly validated because the
URL/token are substituted into a source file before compiling.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

APP_DIR = "/app/watchapp"
KEY = "/app/developer_key.der"
MONKEYC = os.environ.get("MONKEYC", "/root/.Garmin/ConnectIQ/Sdks/current/bin/monkeyc")

ALLOWED_DEVICES = {
    "fenix7", "fenix7s", "fenix7x",
    "fenix7pro", "fenix7pronowifi", "fenix7spro", "fenix7xpro", "fenix7xpronowifi",
}
_URL_RE = re.compile(r"^https://[A-Za-z0-9._\-]+(:[0-9]{1,5})?(/[A-Za-z0-9._\-/]*)?$")
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_\-]{8,256}$")


def build(device: str, url: str, token: str) -> bytes:
    tmp = tempfile.mkdtemp(prefix="vwbuild-")
    try:
        for item in ("source", "resources", "manifest.xml", "monkey.jungle"):
            src, dst = os.path.join(APP_DIR, item), os.path.join(tmp, item)
            (shutil.copytree if os.path.isdir(src) else shutil.copy)(src, dst)
        cfg = os.path.join(tmp, "source", "Config.mc")
        s = open(cfg).read()
        s = s.replace('const DEFAULT_SERVER = "";', 'const DEFAULT_SERVER = "%s";' % url)
        s = s.replace('const DEFAULT_TOKEN = "";', 'const DEFAULT_TOKEN = "%s";' % token)
        open(cfg, "w").write(s)
        out = os.path.join(tmp, "out.prg")
        r = subprocess.run(
            [MONKEYC, "-d", device, "-f", os.path.join(tmp, "monkey.jungle"),
             "-o", out, "-y", KEY, "-w"],
            cwd=tmp, capture_output=True, text=True, timeout=180,
        )
        if r.returncode != 0 or not os.path.exists(out):
            raise RuntimeError("monkeyc failed: " + ((r.stderr or r.stdout)[-600:]))
        with open(out, "rb") as f:
            return f.read()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        u = urllib.parse.urlparse(self.path)
        if u.path == "/health":
            return self._send(200, b"ok")
        if u.path != "/build":
            return self._send(404, b"not found")
        q = urllib.parse.parse_qs(u.query)
        device = (q.get("device") or [""])[0]
        url = (q.get("url") or [""])[0]
        token = (q.get("token") or [""])[0]
        if device not in ALLOWED_DEVICES:
            return self._send(400, b"unknown device")
        if not _URL_RE.match(url) or not _TOKEN_RE.match(token):
            return self._send(400, b"invalid url/token")
        try:
            data = build(device, url, token)
        except Exception as exc:  # noqa: BLE001
            return self._send(500, str(exc).encode()[:600])
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", 'attachment; filename="Vaultwrist-%s.prg"' % device)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send(self, code: int, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # quiet
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
