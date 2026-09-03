"""Login / logout / whoami."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from ..auth import COOKIE_NAME, MAX_AGE, make_token, require_auth, verify_credentials

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginBody, response: Response):
    if not verify_credentials(body.username, body.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bad credentials")
    response.set_cookie(
        COOKIE_NAME, make_token(), max_age=MAX_AGE, httponly=True,
        samesite="lax", path="/",
    )
    return {"ok": True, "user": body.username}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: str = Depends(require_auth)):
    return {"user": user}
