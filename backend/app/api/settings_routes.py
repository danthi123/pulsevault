"""Garmin auth, manual sync, and FIT upload endpoints (Settings page)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from .. import garmin_auth
from ..auth import require_auth
from ..config import settings
from ..sync import ingest_fit, last_status, run_garmin_sync

router = APIRouter(prefix="/api", tags=["settings"], dependencies=[Depends(require_auth)])


class GarminLoginBody(BaseModel):
    email: str
    password: str


class MfaBody(BaseModel):
    code: str


@router.get("/garmin/status")
def garmin_status():
    return garmin_auth.status()


@router.post("/garmin/login")
def garmin_login(body: GarminLoginBody):
    return garmin_auth.login(body.email, body.password)


@router.post("/garmin/mfa")
def garmin_mfa(body: MfaBody):
    return garmin_auth.resume_mfa(body.code)


@router.post("/garmin/logout")
def garmin_logout():
    garmin_auth.logout()
    return {"ok": True}


@router.get("/sync/status")
def sync_status():
    return last_status


@router.post("/sync")
def sync_now(days: int | None = None):
    result = run_garmin_sync(days_back=days if days is not None else 2, fetch_details=True)
    if result.get("state") == "error":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, result.get("reason", "sync failed"))
    return result


@router.post("/backfill")
def backfill():
    return run_garmin_sync(days_back=settings.initial_backfill_days, fetch_details=True)


@router.post("/upload/fit")
async def upload_fit(files: list[UploadFile] = File(...)):
    results = []
    for f in files:
        data = await f.read()
        if not data:
            continue
        try:
            results.append(ingest_fit(data, f.filename or "upload.fit"))
        except Exception as exc:  # noqa: BLE001
            results.append({"state": "error", "file": f.filename, "reason": str(exc)})
    return {"results": results}
