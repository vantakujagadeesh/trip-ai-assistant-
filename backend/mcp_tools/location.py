"""Location lookup shared by weather and place providers."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)
_LOCATION_CACHE: dict[str, dict] = {}


async def resolve_location(location: str) -> dict | None:
    """Resolve a city or region to coordinates using Open-Meteo geocoding."""
    query = location.strip()
    if not query:
        return None

    cache_key = query.casefold()
    if cache_key in _LOCATION_CACHE:
        return _LOCATION_CACHE[cache_key]

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": query, "count": 5, "language": "en", "format": "json"},
            )
            response.raise_for_status()
            results = response.json().get("results") or []
    except (httpx.HTTPError, ValueError):
        logger.warning("Open-Meteo geocoding request failed")
        return None

    if not results:
        return None

    exact_match = next(
        (item for item in results if item.get("name", "").casefold() == cache_key),
        None,
    )
    match = exact_match or results[0]
    try:
        resolved = {
            "name": match["name"],
            "latitude": float(match["latitude"]),
            "longitude": float(match["longitude"]),
            "timezone": match.get("timezone"),
            "country": match.get("country"),
            "admin1": match.get("admin1"),
        }
    except (KeyError, TypeError, ValueError):
        logger.warning("Open-Meteo geocoding returned an invalid location result")
        return None

    _LOCATION_CACHE[cache_key] = resolved
    return resolved
