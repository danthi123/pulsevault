"""Token-authed ingestion for the desktop companion agent.

The agent pulls FIT files off the watch (USB/MTP now, BLE later) and POSTs the
raw bytes here. Auth is a static bearer token (see /api/device/config), so the
agent never needs the interactive cookie login. Uploads are idempotent — the
server-side FIT parser + upsert dedupe means re-sending a file is a no-op.
"""
from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from ..auth import get_ingest_token, require_auth, require_ingest_token
from ..config import settings
from ..sync import ingest_fit, ingest_metrics

router = APIRouter(prefix="/api", tags=["ingest"])

# Devices the builder (and manifest) support; keep in sync with builder/server.py.
WATCH_DEVICES = {
    "fenix7": "Fenix 7", "fenix7s": "Fenix 7S", "fenix7x": "Fenix 7X",
    "fenix7pro": "Fenix 7 Pro", "fenix7spro": "Fenix 7S Pro", "fenix7xpro": "Fenix 7X Pro",
    "fenix7pronowifi": "Fenix 7 Pro (no WiFi)", "fenix7xpronowifi": "Fenix 7X Pro (no WiFi)",
}
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
