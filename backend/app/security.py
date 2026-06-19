from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse

from . import store

TOKEN_PATH = store.STORAGE / "access_token.txt"
PUBLIC_PATHS = {"/api/health"}
DEFAULT_ALLOWED_ORIGIN_REGEX = (
    r"^https?://("
    r"localhost|127\.0\.0\.1|"
    r"192\.168\.\d+\.\d+|"
    r"10\.\d+\.\d+\.\d+|"
    r"172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+"
    r")(:\d+)?$"
)


def auth_disabled() -> bool:
    return os.getenv("FRAMECRAFT_DISABLE_AUTH", "").strip() in {"1", "true", "yes"}


def get_access_token() -> str:
    env_token = os.getenv("FRAMECRAFT_ACCESS_TOKEN", "").strip()
    if env_token:
        return env_token
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    if TOKEN_PATH.is_file():
        token = TOKEN_PATH.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = secrets.token_urlsafe(32)
    TOKEN_PATH.write_text(token + "\n", encoding="utf-8")
    try:
        TOKEN_PATH.chmod(0o600)
    except OSError:
        pass
    return token


def cors_origins() -> list[str]:
    raw = os.getenv("FRAMECRAFT_ALLOWED_ORIGINS", "").strip()
    return [item.strip() for item in raw.split(",") if item.strip()]


def cors_origin_regex() -> str | None:
    return os.getenv("FRAMECRAFT_ALLOWED_ORIGIN_REGEX", DEFAULT_ALLOWED_ORIGIN_REGEX).strip() or None


def _request_token(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return (
        request.headers.get("x-framecraft-token", "").strip()
        or request.query_params.get("access_token", "").strip()
        or request.query_params.get("framecraft_token", "").strip()
    )


async def require_access_token(request: Request, call_next):
    if request.method == "OPTIONS" or request.url.path in PUBLIC_PATHS or auth_disabled():
        return await call_next(request)
    expected = get_access_token()
    if not expected or not secrets.compare_digest(_request_token(request), expected):
        return JSONResponse(
            status_code=401,
            content={
                "detail": "FrameCraft access token required",
                "code": "access_token_required",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await call_next(request)


def token_help() -> str:
    if os.getenv("FRAMECRAFT_ACCESS_TOKEN", "").strip():
        return "FRAMECRAFT_ACCESS_TOKEN"
    return str(TOKEN_PATH)
