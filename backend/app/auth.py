"""Minimal single-user session auth using a signed cookie."""
from __future__ import annotations

import hmac
import os
import secrets

from fastapi import Cookie, Header, HTTPException, status
from itsdangerous import BadSignature, URLSafeTimedSerializer

from .config import settings

COOKIE_NAME = "pulsevault_session"
MAX_AGE = 60 * 60 * 24 * 30  # 30 days

_serializer = URLSafeTimedSerializer(settings.app_secret_key, salt="pulsevault-session")


def verify_credentials(username: str, password: str) -> bool:
    return hmac.compare_digest(username, settings.app_username) and hmac.compare_digest(
        password, settings.app_password
    )


def make_token() -> str:
    return _serializer.dumps({"u": settings.app_username})


def require_auth(session: str | None = Cookie(default=None, alias=COOKIE_NAME)) -> str:
    if not session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        data = _serializer.loads(session, max_age=MAX_AGE)
    except BadSignature:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session")
    return data.get("u", "")


# --- companion-agent ingest token -------------------------------------------
def get_ingest_token() -> str:
    """Static bearer token the desktop companion agent uses to push FIT files.
    From env, else generated once and persisted to the token volume so it
    survives restarts."""
    if settings.ingest_token:
        return settings.ingest_token
    path = os.path.join(settings.garth_home, ".ingest_token")
    try:
        os.makedirs(settings.garth_home, exist_ok=True)
        if os.path.exists(path):
            with open(path) as f:
                tok = f.read().strip()
                if tok:
                    return tok
        tok = secrets.token_urlsafe(24)
        with open(path, "w") as f:
            f.write(tok)
        return tok
    except OSError:
        # Last resort: process-local (changes on restart).
        return "insecure-ephemeral-token"


def require_ingest_token(
    authorization: str | None = Header(default=None),
    x_ingest_token: str | None = Header(default=None),
) -> bool:
    expected = get_ingest_token()
    provided = x_ingest_token
    if not provided and authorization and authorization.lower().startswith("bearer "):
        provided = authorization[7:].strip()
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bad ingest token")
    return True
