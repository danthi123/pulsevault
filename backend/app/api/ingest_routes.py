"""Token-authed ingestion for the desktop companion agent.

The agent pulls FIT files off the watch (USB/MTP now, BLE later) and POSTs the
raw bytes here. Auth is a static bearer token (see /api/device/config), so the
agent never needs the interactive cookie login. Uploads are idempotent — the
server-side FIT parser + upsert dedupe means re-sending a file is a no-op.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, File, UploadFile

from ..auth import get_ingest_token, require_auth, require_ingest_token
from ..sync import ingest_fit, ingest_metrics

router = APIRouter(prefix="/api", tags=["ingest"])


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
