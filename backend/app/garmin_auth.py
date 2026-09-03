"""Garmin Connect authentication and client management.

Garmin uses a mobile SSO flow (via ``garth``). We log in **once** (optionally
answering an MFA prompt), then persist the OAuth token bundle to a mounted
volume. Those tokens auto-refresh indefinitely, so subsequent syncs never need
the password again. The Garmin password is never written to disk by this app.
"""
from __future__ import annotations

import os
import threading
from typing import Any

from garminconnect import Garmin

from .config import settings

_lock = threading.Lock()
# Holds a half-finished login awaiting an MFA code (single-user app → one slot).
_pending: dict[str, Any] = {}


def _token_dir() -> str:
    os.makedirs(settings.garth_home, exist_ok=True)
    return settings.garth_home


def has_tokens() -> bool:
    d = settings.garth_home
    if not os.path.isdir(d):
        return False
    return any(os.scandir(d)) if os.path.exists(d) else False


def status() -> dict[str, Any]:
    """Report auth state for the Settings page without leaking secrets."""
    if not has_tokens():
        return {"authenticated": False, "reason": "no_tokens"}
    try:
        client = get_client()
        name = None
        try:
            name = client.get_full_name()
        except Exception:  # noqa: BLE001 — display-only
            pass
        return {"authenticated": True, "display_name": name}
    except Exception as exc:  # noqa: BLE001
        return {"authenticated": False, "reason": f"token_error: {exc}"}


def get_client() -> Garmin:
    """Return a logged-in Garmin client, loading tokens from the cache dir."""
    client = Garmin()
    client.login(_token_dir())  # loads persisted tokens; refreshes if needed
    return client


def login(email: str, password: str) -> dict[str, Any]:
    """Begin (and usually complete) a login.

    Returns {"status": "ok"} on success, or {"status": "needs_mfa"} if Garmin
    requires a one-time code — then call :func:`resume_mfa` with it.
    """
    with _lock:
        try:
            client = Garmin(email=email, password=password, return_on_mfa=True)
            result = client.login()
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "reason": _friendly(exc)}
        # Newer garminconnect returns a (marker, state) tuple when MFA is needed.
        if isinstance(result, tuple) and result and result[0] == "needs_mfa":
            _pending["client"] = client
            _pending["state"] = result[1]
            return {"status": "needs_mfa"}
        client.garth.dump(_token_dir())
        return {"status": "ok"}


def _friendly(exc: Exception) -> str:
    msg = str(exc)
    low = msg.lower()
    if "429" in low or "too many" in low or "rate limit" in low:
        return ("Garmin rate-limited this server's IP (HTTP 429). Wait ~30–60 min "
                "and try once — repeated attempts extend the block. If it persists, "
                "use token import (see docs).")
    if "cloudflare" in low or "403" in low or "bot" in low:
        return ("Garmin's Cloudflare bot protection blocked the login from this "
                "server (HTTP 403). Server-IP logins are often gated; use token "
                "import instead.")
    if "401" in low or "invalid" in low or "credential" in low:
        return "Garmin rejected the credentials (check email/password)."
    return f"Garmin login failed: {msg[:300]}"


def resume_mfa(mfa_code: str) -> dict[str, Any]:
    with _lock:
        client = _pending.get("client")
        state = _pending.get("state")
        if client is None:
            return {"status": "error", "reason": "no_pending_login"}
        try:
            client.resume_login(state, mfa_code)
            client.garth.dump(_token_dir())
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "reason": _friendly(exc)}
        _pending.clear()
        return {"status": "ok"}


def logout() -> None:
    """Delete the persisted token cache."""
    d = settings.garth_home
    if os.path.isdir(d):
        for entry in os.scandir(d):
            try:
                if entry.is_file():
                    os.remove(entry.path)
            except OSError:
                pass
    _pending.clear()
