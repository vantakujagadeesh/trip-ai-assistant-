import logging
import os
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from fastapi import Depends, Header, HTTPException


logger = logging.getLogger(__name__)


def _read_settings() -> tuple[str, str, bool]:
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    anon_key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    parts = urlsplit(url)
    hostname = parts.hostname
    valid_url = (
        parts.scheme == "https"
        and bool(hostname)
        and not parts.username
        and not parts.password
        and parts.path in {"", "/"}
        and not parts.query
        and not parts.fragment
    ) or (
        parts.scheme == "http"
        and hostname in {"localhost", "127.0.0.1"}
        and parts.path in {"", "/"}
        and not parts.query
        and not parts.fragment
    )
    return url, anon_key, valid_url


def _settings() -> tuple[str, str]:
    url, anon_key, valid_url = _read_settings()
    if not url or not anon_key or not valid_url:
        raise HTTPException(
            status_code=503,
            detail="Saved trips are not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY.",
        )
    return url, anon_key


def public_supabase_config() -> dict[str, Any]:
    url, anon_key, valid_url = _read_settings()
    configured = bool(url and anon_key and valid_url)
    return {
        "supabase_configured": configured,
        "supabase_url": url if configured else None,
        "supabase_anon_key": anon_key if configured else None,
    }


def get_access_token(authorization: str | None = Header(default=None)) -> str:
    scheme, separator, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not separator:
        raise HTTPException(status_code=401, detail="Sign in to continue.")

    token = token.strip()
    if not token or len(token) > 8192:
        raise HTTPException(status_code=401, detail="Invalid access token.")
    return token


async def get_authenticated_user(
    token: str = Depends(get_access_token),
) -> dict[str, Any]:
    url, anon_key = _settings()
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(
                f"{url}/auth/v1/user",
                headers={"apikey": anon_key, "Authorization": f"Bearer {token}"},
            )
    except httpx.TimeoutException as exc:
        logger.warning("Supabase authentication timed out")
        raise HTTPException(status_code=503, detail="Authentication service timed out.") from exc
    except httpx.RequestError as exc:
        logger.error("Supabase authentication request failed")
        raise HTTPException(status_code=503, detail="Authentication service is unavailable.") from exc

    if response.status_code in {401, 403}:
        raise HTTPException(status_code=401, detail="Your session is invalid or expired. Sign in again.")
    if not response.is_success:
        logger.error("Supabase authentication failed with status %s", response.status_code)
        raise HTTPException(status_code=502, detail="Authentication service returned an error.")

    try:
        user = response.json()
    except ValueError as exc:
        logger.error("Supabase authentication returned invalid JSON")
        raise HTTPException(status_code=502, detail="Authentication service returned an invalid response.") from exc

    if not isinstance(user, dict) or not user.get("id"):
        raise HTTPException(status_code=401, detail="Invalid access token.")
    try:
        user["id"] = str(UUID(user["id"]))
    except (TypeError, ValueError) as exc:
        logger.error("Supabase authentication returned an invalid user ID")
        raise HTTPException(status_code=502, detail="Authentication service returned an invalid user.") from exc
    return user


async def supabase_rest(
    method: str,
    table: str,
    token: str,
    *,
    params: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    prefer: str | None = None,
) -> Any:
    url, anon_key = _settings()
    headers = {
        "apikey": anon_key,
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if prefer:
        headers["Prefer"] = prefer

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.request(
                method,
                f"{url}/rest/v1/{table}",
                headers=headers,
                params=params,
                json=payload,
            )
    except httpx.TimeoutException as exc:
        logger.warning("Supabase database request timed out")
        raise HTTPException(status_code=503, detail="Trip storage timed out. Please try again.") from exc
    except httpx.RequestError as exc:
        logger.error("Supabase database request failed")
        raise HTTPException(status_code=503, detail="Trip storage is unavailable. Please try again.") from exc

    if response.status_code == 401:
        raise HTTPException(status_code=401, detail="Your session is invalid or expired. Sign in again.")
    if response.status_code == 403:
        raise HTTPException(status_code=403, detail="You are not allowed to access this record.")
    if response.status_code == 404:
        logger.error("Supabase table %s was not found", table)
        raise HTTPException(status_code=503, detail="Trip storage is not initialized. Apply the database migration.")
    if response.status_code == 409:
        raise HTTPException(status_code=409, detail="This record cannot be changed because it has related booking requests.")
    if response.status_code == 429:
        raise HTTPException(status_code=503, detail="Trip storage is busy. Please try again shortly.")
    if response.status_code >= 500:
        logger.error("Supabase database request returned status %s", response.status_code)
        raise HTTPException(status_code=502, detail="Trip storage returned an error.")
    if not response.is_success:
        logger.info("Supabase rejected a %s request to %s with status %s", method, table, response.status_code)
        raise HTTPException(status_code=422, detail="The request does not satisfy the data rules.")
    if not response.content:
        return None

    try:
        return response.json()
    except ValueError as exc:
        logger.error("Supabase table %s returned invalid JSON", table)
        raise HTTPException(status_code=502, detail="Trip storage returned an invalid response.") from exc
