"""Token-authed ingestion for the desktop companion agent.

The agent pulls FIT files off the watch (USB/MTP now, BLE later) and POSTs the
raw bytes here. Auth is a static bearer token (see /api/device/config), so the
agent never needs the interactive cookie login. Uploads are idempotent — the
server-side FIT parser + upsert dedupe means re-sending a file is a no-op.
"""
from __future__ import annotations

import io
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from typing import Any

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from ..auth import get_ingest_token, require_auth, require_ingest_token
from ..config import settings
from ..sync import ingest_fit, ingest_metrics

router = APIRouter(prefix="/api", tags=["ingest"])

# Offered watch models (id -> display name), generated from the SDK device DB
# (backend/app/watch_devices.json). These are the models the app compiles for;
# the builder itself accepts any installed device id.
_DEV_FILE = os.path.join(os.path.dirname(__file__), "..", "watch_devices.json")
try:
    with open(_DEV_FILE, encoding="utf-8") as _f:
        WATCH_DEVICES: dict[str, str] = json.load(_f)
except Exception:  # noqa: BLE001
    WATCH_DEVICES = {}
_SERVER_RE = re.compile(r"^https://[A-Za-z0-9._\-]+(:[0-9]{1,5})?$")


@router.post("/ingest/fit", dependencies=[Depends(require_ingest_token)])
async def ingest_fit_push(files: list[UploadFile] = File(...)):
    """Companion agent uploads one or more raw .fit files."""
    results = []
    for f in files:
        data = await f.read()
        if not data:
            continue
        try:
            results.append(ingest_fit(data, f.filename or "device.fit"))
        except Exception as exc:  # noqa: BLE001
            results.append({"state": "error", "file": f.filename, "reason": str(exc)})
    ok = sum(1 for r in results if r.get("state") == "ok")
    return {"accepted": ok, "total": len(results), "results": results}


@router.post("/ingest/metrics", dependencies=[Depends(require_ingest_token)])
def ingest_metrics_push(payload: dict[str, Any] = Body(...)):
    """On-watch Connect IQ app pushes recent live metrics (HR, stress, Body
    Battery, SpO2, respiration, today's totals)."""
    return ingest_metrics(payload)


@router.get("/device/config")
def device_config(user: str = Depends(require_auth)):
    """Return the values a user pastes into the companion agent's config.
    Cookie-authed so only the logged-in owner can read the token."""
    return {"ingest_token": get_ingest_token(), "ingest_path": "/api/ingest/fit"}


@router.get("/watchapp/devices")
def watchapp_devices(user: str = Depends(require_auth)):
    """Devices the pre-configured Vaultwrist build supports (id -> label)."""
    return {"devices": WATCH_DEVICES}


_COMPANION_BIN = {"linux": "pulsevault-companion", "windows": "pulsevault-companion.exe"}


def _companion_config(target: str, server: str, token: str) -> str:
    if target == "windows":
        source = (
            '# Windows: point this at a folder where you copy the watch\'s FIT files\n'
            '# (open the Fenix in Explorer -> Internal Storage/GARMIN, copy ACTIVITY +\n'
            '# MONITOR + SLEEP into this folder). MTP auto-detect is Linux-only for now.\n'
            '[[sources]]\n'
            'type = "folder"\n'
            'path = "C:\\\\Users\\\\Public\\\\PulseVaultFit"\n'
        )
    else:
        source = (
            '# Linux: auto-detects the watch when plugged in (gvfs MTP mount).\n'
            '[[sources]]\n'
            'type = "mtp"\n'
        )
    return (
        f'server_url = "{server}"\n'
        f'token = "{token}"\n'
        'poll_interval = 300\n\n'
        f'{source}'
    )


def _companion_readme(target: str) -> str:
    run = ("Double-click pulsevault-companion.exe (or run it in a terminal)."
           if target == "windows"
           else "chmod +x pulsevault-companion && ./pulsevault-companion")
    return (
        "PulseVault companion\n"
        "====================\n\n"
        "Keep this binary and config.toml in the SAME folder, then run it:\n"
        f"  {run}\n\n"
        "config.toml is already filled in with your server URL and token.\n"
        "It syncs FIT files from your watch to PulseVault (idempotent — safe to\n"
        "re-run). Use `... once` for a single pass, `... status` to check.\n"
    )


@router.get("/companion/download")
def companion_download(
    target: str = Query(..., pattern="^(linux|windows)$"),
    server: str = Query(...),
    user: str = Depends(require_auth),
):
    """Zip the prebuilt companion binary for the OS together with a config.toml
    pre-filled for this instance, so it's download-extract-run."""
    if not _SERVER_RE.match(server):
        raise HTTPException(400, "server must be an https:// origin")
    binname = _COMPANION_BIN[target]
    binpath = os.path.join(settings.companion_dist_dir, binname)
    if not os.path.isfile(binpath):
        raise HTTPException(503, "companion binary not available yet (CI build pending)")

    cfg = _companion_config(target, server, get_ingest_token())
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        info = zipfile.ZipInfo(binname)
        info.external_attr = (0o755 << 16)  # executable bit for the Linux binary
        with open(binpath, "rb") as f:
            z.writestr(info, f.read())
        z.writestr("config.toml", cfg)
        z.writestr("README.txt", _companion_readme(target))
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="pulsevault-companion-{target}.zip"'},
    )


@router.get("/watchapp/build")
def watchapp_build(
    device: str = Query(...),
    server: str = Query(...),
    user: str = Depends(require_auth),
):
    """Compile a Vaultwrist .prg pre-baked with this instance's URL + ingest
    token, so it can be sideloaded and works with no on-device configuration."""
    if device not in WATCH_DEVICES:
        raise HTTPException(400, "unknown device")
    if not _SERVER_RE.match(server):
        raise HTTPException(400, "server must be an https:// origin")
    qs = urllib.parse.urlencode({"device": device, "url": server, "token": get_ingest_token()})
    try:
        with urllib.request.urlopen(f"{settings.builder_url}/build?{qs}", timeout=180) as r:
            data = r.read()
    except urllib.error.HTTPError as exc:
        raise HTTPException(502, f"build failed: {exc.read()[:300].decode(errors='replace')}")
    except Exception:  # noqa: BLE001
        raise HTTPException(503, "watch-app build service is unavailable")
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="Vaultwrist-{device}.prg"'},
    )
