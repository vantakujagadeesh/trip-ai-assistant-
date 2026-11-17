"""
MCP Tool: Weather Forecast
Uses Open-Meteo API — completely FREE, no API key required.
"""
from __future__ import annotations

import httpx
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mcp_tools.location import resolve_location


# City coordinates lookup (expanded for common travel destinations)
CITY_COORDS = {
    # India
    "goa": (15.2993, 74.1240), "goi": (15.2993, 74.1240),
    "delhi": (28.6139, 77.2090), "new delhi": (28.6139, 77.2090), "del": (28.6139, 77.2090),
    "mumbai": (19.0760, 72.8777), "bom": (19.0760, 72.8777),
    "bangalore": (12.9716, 77.5946), "bengaluru": (12.9716, 77.5946), "blr": (12.9716, 77.5946),
    "kerala": (10.8505, 76.2711), "kochi": (9.9312, 76.2673),
    "rajasthan": (27.0238, 74.2179), "jaipur": (26.9124, 75.7873),
    "agra": (27.1767, 78.0081),
    # Europe
    "rome": (41.9028, 12.4964), "italy": (41.9028, 12.4964),
    "paris": (48.8566, 2.3522), "france": (48.8566, 2.3522),
    "barcelona": (41.3851, 2.1734), "spain": (40.4168, -3.7038),
    "portofino": (44.3033, 9.2107),
    "cinque terre": (44.1461, 9.6439),
    # Asia
    "tokyo": (35.6762, 139.6503), "japan": (35.6762, 139.6503),
    "kyoto": (35.0116, 135.7681),
    "bangkok": (13.7563, 100.5018), "thailand": (13.7563, 100.5018),
    "bali": (-8.3405, 115.0920), "indonesia": (-8.3405, 115.0920),
    "singapore": (1.3521, 103.8198),
}

WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Icy fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail",
}


async def get_weather(location: str, start_date: str, end_date: Optional[str] = None) -> dict:
    """
    Get weather forecast for a travel destination.

    Args:
        location: city name or IATA code (e.g., 'Goa', 'Paris', 'Tokyo')
        start_date: YYYY-MM-DD
        end_date: YYYY-MM-DD (defaults to 7 days from start_date)

    Returns:
        dict with daily weather forecast including temperature, rain probability, conditions
    """
    loc_key = location.lower().strip()
    resolved = await resolve_location(location)
    if not resolved:
        coords = CITY_COORDS.get(loc_key)
        if not coords:
            return {
                "status": "location_not_found",
                "source": "Open-Meteo",
                "location": location,
                "forecast": [],
                "summary": "",
            }
        resolved = {"latitude": coords[0], "longitude": coords[1], "timezone": None}

    try:
        requested_start = date.fromisoformat(start_date)
        requested_end = date.fromisoformat(end_date) if end_date else requested_start + timedelta(days=6)
    except ValueError:
        return {
            "status": "invalid_date",
            "source": "Open-Meteo",
            "location": location,
            "forecast": [],
            "summary": "",
        }

    if requested_end < requested_start:
        return {
            "status": "invalid_date_range",
            "source": "Open-Meteo",
            "location": location,
            "forecast": [],
            "summary": "",
        }

    try:
        local_today = datetime.now(ZoneInfo(resolved["timezone"])).date()
    except (ZoneInfoNotFoundError, TypeError, KeyError):
        local_today = datetime.now(timezone.utc).date()
    max_forecast_date = local_today + timedelta(days=15)
    if requested_start < local_today:
        return {
            "status": "past_date",
            "source": "Open-Meteo",
            "location": location,
            "forecast": [],
            "summary": "",
            "note": "A live forecast is not available for past travel dates.",
        }
    if requested_start > max_forecast_date:
        return {
            "status": "out_of_range",
            "source": "Open-Meteo",
            "location": location,
            "forecast": [],
            "summary": "",
            "forecast_available_through": max_forecast_date.isoformat(),
            "note": "A reliable daily forecast is available only up to 16 days ahead.",
        }

    forecast_end = min(requested_end, max_forecast_date)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": resolved["latitude"],
                    "longitude": resolved["longitude"],
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
                    "start_date": requested_start.isoformat(),
                    "end_date": forecast_end.isoformat(),
                    "timezone": "auto",
                },
            )
            resp.raise_for_status()

            data = resp.json()
            daily = data.get("daily", {})
            dates = daily.get("time", [])
            forecast = []
            for i, forecast_date in enumerate(dates):
                wcode = _at(daily.get("weather_code") or daily.get("weathercode"), i)
                rain_probability = _at(daily.get("precipitation_probability_max"), i)
                forecast.append({
                    "date": forecast_date,
                    "max_temp_c": _at(daily.get("temperature_2m_max"), i),
                    "min_temp_c": _at(daily.get("temperature_2m_min"), i),
                    "rain_probability": rain_probability,
                    "condition": WMO_CODES.get(wcode, "Unavailable"),
                    "icon": _weather_icon(wcode) if wcode is not None else "",
                    "travel_tip": _weather_tip(wcode, rain_probability)
                    if wcode is not None and rain_probability is not None else "",
                })
            status = "live" if forecast and forecast_end == requested_end else "partial"
            return {
                "status": status if forecast else "unavailable",
                "source": "Open-Meteo",
                "location": location,
                "forecast": forecast,
                "summary": _weather_summary(forecast),
                "requested_start": requested_start.isoformat(),
                "requested_end": requested_end.isoformat(),
                "forecast_available_through": forecast_end.isoformat() if forecast else None,
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "note": (
                    "The forecast ends before the full trip dates."
                    if forecast and forecast_end < requested_end else None
                ),
            }
    except (httpx.HTTPError, ValueError):
        return {
            "status": "provider_error",
            "source": "Open-Meteo",
            "location": location,
            "forecast": [],
            "summary": "",
            "note": "Weather data is temporarily unavailable.",
        }


def _at(values, index: int, default=None):
    return values[index] if isinstance(values, list) and index < len(values) else default


def _weather_icon(wcode: int | None) -> str:
    if wcode is None:
        return ""
    if wcode == 0: return "☀️"
    if wcode in [1, 2]: return "🌤️"
    if wcode == 3: return "☁️"
    if wcode in [45, 48]: return "🌫️"
    if wcode in range(51, 68): return "🌧️"
    if wcode in range(71, 78): return "🌨️"
    if wcode in range(80, 83): return "🌦️"
    if wcode >= 95: return "⛈️"
    return "🌡️"


def _weather_tip(wcode: int, rain_prob: float) -> str:
    if rain_prob > 70: return "Pack rain gear — high chance of rain"
    if rain_prob > 40: return "Consider light rain jacket"
    if wcode == 0: return "Perfect beach/outdoor day ☀️"
    if wcode in [1, 2]: return "Great day for sightseeing"
    return "Mild conditions — good for most activities"


def _weather_summary(forecast: list) -> str:
    if not forecast:
        return "Weather data unavailable"
    temperatures = [
        day["max_temp_c"] for day in forecast
        if isinstance(day.get("max_temp_c"), (int, float))
    ]
    if not temperatures:
        return "Weather data unavailable"
    avg_temp = sum(temperatures) / len(temperatures)
    rainy_days = sum(
        1 for day in forecast
        if isinstance(day.get("rain_probability"), (int, float)) and day["rain_probability"] > 50
    )
    season = "warm" if avg_temp > 28 else "pleasant" if avg_temp > 20 else "cool"
    rain_txt = f", {rainy_days} rainy day{'s' if rainy_days != 1 else ''}" if rainy_days > 0 else ", mostly dry"
    return f"{season.capitalize()} weather (avg {avg_temp:.0f}°C){rain_txt}"
