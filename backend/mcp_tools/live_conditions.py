"""
MCP Tool: Live Weather + Road Conditions
- Current weather (temp, feels-like, UV index, humidity, wind) via Open-Meteo (FREE, no API key)
- Hourly weather for next 12h (rain probability, visibility, wind)
- 7-day daily forecast with travel suitability rating
- Air Quality Index via Open-Meteo AQ endpoint
- Road condition analysis: highway alerts, blockage risk, fog/rain hazards, mountain warnings
- Smart travel advisories: best departure time, best travel window, packing list
"""
from __future__ import annotations

import httpx
import asyncio
from typing import Optional
from datetime import datetime, timezone

from mcp_tools.location import resolve_location


# ── City Coordinates (lat, lon) ────────────────────────────────────────────────
CITY_COORDS = {
    # India
    "goa": (15.2993, 74.1240), "panaji": (15.4909, 73.8278),
    "delhi": (28.6139, 77.2090), "new delhi": (28.6139, 77.2090),
    "mumbai": (19.0760, 72.8777), "pune": (18.5204, 73.8567),
    "bangalore": (12.9716, 77.5946), "bengaluru": (12.9716, 77.5946),
    "hyderabad": (17.3850, 78.4867), "chennai": (13.0827, 80.2707),
    "kolkata": (22.5726, 88.3639), "kochi": (9.9312, 76.2673),
    "jaipur": (26.9124, 75.7873), "jodhpur": (26.2389, 73.0243),
    "udaipur": (24.5854, 73.7125), "pushkar": (26.4897, 74.5511),
    "agra": (27.1767, 78.0081), "varanasi": (25.3176, 82.9739),
    "lucknow": (26.8467, 80.9462), "bhopal": (23.2599, 77.4126),
    "ahmedabad": (23.0225, 72.5714), "surat": (21.1702, 72.8311),
    "amritsar": (31.6340, 74.8723), "shimla": (31.1048, 77.1734),
    "manali": (32.2396, 77.1887), "leh": (34.1526, 77.5771),
    "darjeeling": (27.0360, 88.2627), "gangtok": (27.3389, 88.6065),
    "mysore": (12.2958, 76.6394), "ooty": (11.4102, 76.6950),
    "pondicherry": (11.9416, 79.8083), "andaman": (11.7401, 92.6586),
    "kerala": (10.8505, 76.2711), "munnar": (10.0889, 77.0595),
    "coorg": (12.3375, 75.8069), "kodaikanal": (10.2381, 77.4892),
    # Europe
    "paris": (48.8566, 2.3522), "rome": (41.9028, 12.4964),
    "barcelona": (41.3851, 2.1734), "amsterdam": (52.3676, 4.9041),
    "london": (51.5074, -0.1278), "berlin": (52.5200, 13.4050),
    # Asia
    "tokyo": (35.6762, 139.6503), "kyoto": (35.0116, 135.7681),
    "bangkok": (13.7563, 100.5018), "bali": (-8.3405, 115.0920),
    "singapore": (1.3521, 103.8198), "dubai": (25.2048, 55.2708),
}

# WMO Weather interpretation codes → (description, emoji, activity_type)
WMO_CODES = {
    0: ("Clear sky", "☀️", "outdoor"), 1: ("Mainly clear", "🌤️", "outdoor"),
    2: ("Partly cloudy", "⛅", "outdoor"), 3: ("Overcast", "☁️", "outdoor"),
    45: ("Fog", "🌫️", "indoor"), 48: ("Icy fog", "🌫️", "indoor"),
    51: ("Light drizzle", "🌦️", "indoor"), 53: ("Moderate drizzle", "🌧️", "indoor"),
    55: ("Dense drizzle", "🌧️", "indoor"),
    61: ("Slight rain", "🌧️", "indoor"), 63: ("Moderate rain", "🌧️", "indoor"),
    65: ("Heavy rain", "⛈️", "indoor"),
    71: ("Slight snow", "🌨️", "outdoor"), 73: ("Moderate snow", "❄️", "indoor"),
    75: ("Heavy snow", "❄️", "indoor"),
    80: ("Slight showers", "🌦️", "indoor"), 81: ("Moderate showers", "🌧️", "indoor"),
    82: ("Violent showers", "⛈️", "indoor"),
    95: ("Thunderstorm", "⛈️", "indoor"), 96: ("Thunderstorm+hail", "🌩️", "indoor"),
}

# Major Indian highway route map (origin → dest → route info)
HIGHWAY_ROUTES = {
    ("delhi", "jaipur"): {
        "highways": ["NH-48 (Delhi–Jaipur Expressway)"],
        "distance_km": 282, "normal_duration": "4h 30m",
        "via": "Gurugram → Kotputli → Shahpura",
        "mountain": False,
    },
    ("delhi", "agra"): {
        "highways": ["Yamuna Expressway (E005)"],
        "distance_km": 206, "normal_duration": "3h 15m",
        "via": "Mathura", "mountain": False,
    },
    ("delhi", "mumbai"): {
        "highways": ["NH-48 (Delhi–Mumbai Expressway)"],
        "distance_km": 1425, "normal_duration": "20h",
        "via": "Jaipur → Ahmedabad → Vadodara", "mountain": False,
    },
    ("delhi", "manali"): {
        "highways": ["NH-3 / Chandigarh–Manali Highway"],
        "distance_km": 540, "normal_duration": "12h",
        "via": "Chandigarh → Mandi → Kullu (Mountain passes)", "mountain": True,
    },
    ("delhi", "shimla"): {
        "highways": ["NH-5 / Kalka–Shimla Highway"],
        "distance_km": 365, "normal_duration": "7h",
        "via": "Chandigarh → Kalka", "mountain": True,
    },
    ("mumbai", "goa"): {
        "highways": ["NH-66 (Mumbai–Goa Coastal Highway)"],
        "distance_km": 590, "normal_duration": "10h",
        "via": "Pune → Kolhapur → Belgaum", "mountain": False,
    },
    ("mumbai", "pune"): {
        "highways": ["NH-48 / Expressway"],
        "distance_km": 148, "normal_duration": "2h 30m",
        "via": "Lonavala", "mountain": False,
    },
    ("bangalore", "mysore"): {
        "highways": ["NH-275"],
        "distance_km": 143, "normal_duration": "2h 45m",
        "via": "Mandya", "mountain": False,
    },
    ("bangalore", "ooty"): {
        "highways": ["NH-181 + Ghat Road"],
        "distance_km": 268, "normal_duration": "5h 30m",
        "via": "Mysore → Gudalur (Ghat section)", "mountain": True,
    },
    ("bangalore", "coorg"): {
        "highways": ["NH-275 + SH-88"],
        "distance_km": 249, "normal_duration": "4h 30m",
        "via": "Mysore → Hunsur → Madikeri", "mountain": True,
    },
    ("delhi", "goa"): {
        "highways": ["NH-48 → NH-66"],
        "distance_km": 1850, "normal_duration": "28h road",
        "via": "Pune → Kolhapur", "mountain": False,
    },
}


async def get_live_conditions(
    destination: str,
    origin: Optional[str] = None,
) -> dict:
    """
    Fetch live weather + road conditions for a destination (and optionally a route).

    Returns:
        - current_weather: temp, feels_like, humidity, wind, UV, condition
        - hourly_forecast: next 12h hour-by-hour weather
        - daily_forecast: 7-day outlook with travel suitability
        - air_quality: US AQI, PM2.5, health advice
        - road_conditions: highway status, alerts, detour advice, risk level
        - travel_advisories: packing list, best timing, best travel days
        - best_travel_window: optimal departure time
    """
    dest_key = destination.lower().strip()
    resolved = await resolve_location(destination)
    coords = (
        (resolved["latitude"], resolved["longitude"])
        if resolved else _get_coords(dest_key)
    )

    if not coords:
        # Return minimal data with no-coord fallback
        return {
            "destination": destination, "origin": origin,
            "status": "location_not_found",
            "source": "Open-Meteo",
            "current_weather": {},
            "hourly_forecast": [],
            "daily_forecast": [],
            "air_quality": {},
            "road_conditions": {
                "status": "unavailable",
                "risk_level": "UNKNOWN",
                "alerts": [],
                "conditions": [],
                "traffic_data_connected": False,
            },
            "travel_advisories": [],
            "best_travel_window": {},
            "data_sources": {
                "weather": "location_not_found",
                "air_quality": "location_not_found",
                "traffic": "not_connected",
            },
            "note": "Current weather and forecast data could not be resolved for this location.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    lat, lon = coords
    origin_key = origin.lower().strip() if origin else None

    # Run weather + AQ in parallel
    tasks = [
        _fetch_current_and_hourly(lat, lon),
        _fetch_daily(lat, lon),
        _fetch_air_quality(lat, lon),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    current_hourly = results[0] if not isinstance(results[0], Exception) else {}
    daily = results[1] if not isinstance(results[1], Exception) else {}
    aq = results[2] if not isinstance(results[2], Exception) else {}

    # Road condition analysis
    road = (
        _get_road_conditions(origin_key, dest_key, current_hourly)
        if current_hourly.get("current") else {
            "status": "unavailable",
            "risk_level": "UNKNOWN",
            "alerts": [],
            "conditions": [],
            "traffic_data_connected": False,
            "note": "No current weather data is available to assess weather-related driving risk.",
        }
    )

    # Smart combined advisories
    advisories = _generate_advisories(current_hourly, road)

    return {
        "destination": destination,
        "origin": origin,
        "status": current_hourly.get("status", "unavailable"),
        "source": "Open-Meteo",
        "current_weather": current_hourly.get("current", {}),
        "hourly_forecast": current_hourly.get("hourly", [])[:12],
        "daily_forecast": daily.get("forecast", []),
        "air_quality": aq,
        "road_conditions": road,
        "travel_advisories": advisories,
        "best_travel_window": _best_travel_window(current_hourly.get("hourly", [])),
        "data_sources": {
            "weather": current_hourly.get("status", "unavailable"),
            "forecast": daily.get("status", "unavailable"),
            "air_quality": aq.get("status", "unavailable"),
            "traffic": "not_connected",
        },
        "note": (
            "Live route traffic and road closures are not connected."
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── API Fetchers ──────────────────────────────────────────────────────────────

async def _fetch_current_and_hourly(lat: float, lon: float) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat, "longitude": lon,
                    "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation,weathercode,uv_index,surface_pressure",
                    "hourly": "temperature_2m,apparent_temperature,precipitation_probability,weathercode,wind_speed_10m,visibility",
                    "timezone": "auto",
                    "forecast_days": 2,
                }
            )
            resp.raise_for_status()

            data = resp.json()
            cr = data.get("current", {})
            hr = data.get("hourly", {})

            wc = cr.get("weather_code", cr.get("weathercode"))
            wi = WMO_CODES.get(wc, ("Unavailable", "", "unknown"))

            current = {
                "temp_c": cr.get("temperature_2m"),
                "feels_like_c": cr.get("apparent_temperature"),
                "humidity_pct": cr.get("relative_humidity_2m"),
                "wind_kmh": cr.get("wind_speed_10m"),
                "wind_direction": _wind_dir(cr.get("wind_direction_10m")),
                "precipitation_mm": cr.get("precipitation"),
                "uv_index": cr.get("uv_index"),
                "pressure_hpa": cr.get("surface_pressure"),
                "condition": wi[0],
                "icon": wi[1],
                "activity_type": wi[2],
                "weathercode": wc,
            }

            times = hr.get("time", [])
            hourly = []
            for i, t in enumerate(times[:24]):
                hwc = _at(hr.get("weather_code") or hr.get("weathercode"), i)
                hwi = WMO_CODES.get(hwc, ("Unavailable", "", "unknown"))
                vis_raw = _at(hr.get("visibility"), i)
                hourly.append({
                    "time": t,
                    "hour": t[11:16] if len(t) > 10 else t,
                    "temp_c": _at(hr.get("temperature_2m"), i),
                    "feels_like_c": _at(hr.get("apparent_temperature"), i),
                    "rain_prob": _at(hr.get("precipitation_probability"), i),
                    "wind_kmh": _at(hr.get("wind_speed_10m"), i),
                    "visibility_km": round(vis_raw / 1000, 1) if isinstance(vis_raw, (int, float)) else None,
                    "condition": hwi[0],
                    "icon": hwi[1],
                    "weathercode": hwc,
                })

            return {"status": "live", "source": "Open-Meteo", "current": current, "hourly": hourly}
    except httpx.HTTPError:
        return {"status": "provider_error", "current": {}, "hourly": []}


async def _fetch_daily(lat: float, lon: float) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat, "longitude": lon,
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weathercode,uv_index_max,wind_speed_10m_max,sunrise,sunset",
                    "timezone": "auto",
                }
            )
            resp.raise_for_status()
            dr = resp.json().get("daily", {})
            forecast = []
            for i, d in enumerate(dr.get("time", [])):
                wc = _at(dr.get("weather_code") or dr.get("weathercode"), i)
                wi = WMO_CODES.get(wc, ("Unavailable", "", "unknown"))
                rain = _at(dr.get("precipitation_probability_max"), i)
                max_temp = _at(dr.get("temperature_2m_max"), i)
                min_temp = _at(dr.get("temperature_2m_min"), i)
                forecast.append({
                    "date": d,
                    "max_temp_c": max_temp,
                    "min_temp_c": min_temp,
                    "rain_probability": rain,
                    "condition": wi[0],
                    "icon": wi[1],
                    "activity_suitability": wi[2],
                    "uv_max": _at(dr.get("uv_index_max"), i),
                    "max_wind_kmh": _at(dr.get("wind_speed_10m_max"), i),
                    "sunrise": (_at(dr.get("sunrise"), i, "") or "")[-5:],
                    "sunset": (_at(dr.get("sunset"), i, "") or "")[-5:],
                    "is_good_travel_day": (
                        isinstance(rain, (int, float)) and rain < 40 and wc is not None and wc < 61
                    ),
                    "travel_tip": _daily_tip(wc, rain) if wc is not None and rain is not None else "",
                })
            return {"status": "live" if forecast else "unavailable", "source": "Open-Meteo", "forecast": forecast}
    except httpx.HTTPError:
        return {"status": "provider_error", "forecast": []}


async def _fetch_air_quality(lat: float, lon: float) -> dict:
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(
                "https://air-quality-api.open-meteo.com/v1/air-quality",
                params={
                    "latitude": lat, "longitude": lon,
                    "current": "pm10,pm2_5,european_aqi,us_aqi",
                }
            )
            resp.raise_for_status()
            c = resp.json().get("current", {})
            us = c.get("us_aqi")
            return {
                "status": "live" if c else "unavailable",
                "source": "Open-Meteo",
                "observed_at": c.get("time"),
                "pm2_5": c.get("pm2_5"),
                "pm10": c.get("pm10"),
                "us_aqi": us,
                "eu_aqi": c.get("european_aqi"),
                "level": _aqi_level(us),
                "health_advice": _aqi_advice(us),
            }
    except httpx.HTTPError:
        return {"status": "provider_error"}


# ── Road Conditions Analyzer ──────────────────────────────────────────────────

def _get_road_conditions(origin_key, dest_key, weather_data: dict) -> dict:
    alerts = []
    conditions = []
    detour_advice = []
    current = weather_data.get("current", {})
    hourly = weather_data.get("hourly", [])
    wcode = current.get("weathercode")
    wind = current.get("wind_kmh")
    visibility = _at(hourly[0], "visibility_km") if hourly else None
    risk_level = "UNKNOWN"

    if current:
        risk_level = "LOW"
        if wcode is not None and wcode >= 95:
            risk_level = "HIGH"
            alerts.append("Thunderstorm conditions are reported at the destination; avoid exposed outdoor activities.")
        elif wcode in [63, 65, 80, 81, 82]:
            risk_level = "HIGH"
            alerts.append("Heavy rain is reported at the destination; allow for reduced visibility and wet roads.")
        elif wcode in [51, 53, 55, 61]:
            risk_level = "MODERATE"
            alerts.append("Rain is reported at the destination; use caution on wet roads.")

        if isinstance(wind, (int, float)) and wind > 60:
            risk_level = "HIGH" if risk_level not in ["HIGH"] else risk_level
            alerts.append(f"Strong winds ({wind:.0f} km/h) are reported at the destination.")
        if isinstance(visibility, (int, float)) and visibility < 1.5:
            risk_level = "HIGH" if visibility < 0.5 else "MODERATE"
            alerts.append(f"Reduced visibility ({visibility:.1f} km) is forecast for the destination.")

        conditions.append(
            "Weather-based destination advisory only. Live route traffic, road closures, and local authority alerts are not connected."
        )
        if risk_level == "LOW":
            conditions.append("No severe weather signal was detected in the current destination data; this does not confirm that roads are clear.")

    return {
        "status": "weather_based" if current else "unavailable",
        "risk_level": risk_level,
        "risk_color": {"LOW": "green", "MODERATE": "amber", "HIGH": "red", "CRITICAL": "red", "UNKNOWN": "gray"}[risk_level],
        "risk_icon": {"LOW": "✅", "MODERATE": "⚠️", "HIGH": "🔴", "CRITICAL": "🚨", "UNKNOWN": "ℹ️"}[risk_level],
        "alerts": alerts,
        "conditions": conditions,
        "detour_advice": detour_advice,
        "route_info": None,
        "best_departure_time": None,
        "traffic_data_connected": False,
        "updated_at": current.get("time"),
    }


# ── Smart Advisories Builder ──────────────────────────────────────────────────

def _generate_advisories(current_hourly: dict, road: dict) -> list:
    advisories = []
    current = current_hourly.get("current", {})
    hourly = current_hourly.get("hourly", [])
    wcode = current.get("weathercode")
    temp = current.get("temp_c")
    uv = current.get("uv_index")

    # Packing advice
    packing = []
    if wcode is not None and wcode >= 51:
        packing += ["☂️ Compact rain jacket / umbrella", "💧 Waterproof bag cover"]
    if (temp is not None and temp > 35) or (uv is not None and uv > 7):
        packing += ["🧴 Sunscreen SPF 50+", "🕶️ UV-blocking sunglasses", "🎩 Wide-brim hat"]
    if temp is not None and temp < 15:
        packing += ["🧥 Warm jacket / thermal layers", "🧤 Gloves"]
    if uv is not None and uv > 9:
        packing.append(f"☀️ Extreme UV ({uv:.0f}) — reapply sunscreen every 90 min")
    if packing:
        advisories.append({"type": "packing", "icon": "🎒", "title": "What to Pack", "items": packing})

    # Best activity hours
    good = [
        h for h in hourly[:12]
        if isinstance(h.get("rain_prob"), (int, float))
        and h.get("weathercode") is not None
        and h["rain_prob"] < 30
        and h["weathercode"] < 61
    ]
    if good:
        advisories.append({
            "type": "timing", "icon": "⏰", "title": "Best Activity Window",
            "items": [f"Clear skies expected around {good[0]['hour']} — ideal for outdoor sightseeing"]
        })

    # Road alerts
    if road.get("alerts"):
        advisories.append({
            "type": "road_alert", "icon": "🚗",
            "title": f"Road Conditions ({road['risk_level']} Risk)",
            "items": road["alerts"][:3]
        })
    if road.get("detour_advice"):
        advisories.append({
            "type": "detour", "icon": "↩️", "title": "Detour / Timing Advice",
            "items": road["detour_advice"]
        })

    return advisories


def _best_travel_window(hourly: list) -> dict:
    if not hourly:
        return {}
    scored = []
    for h in hourly[:12]:
        rain = h.get("rain_prob")
        wc = h.get("weathercode")
        vis = h.get("visibility_km")
        wind = h.get("wind_kmh")
        if not all(isinstance(value, (int, float)) for value in (rain, wc, vis, wind)):
            continue
        score = (100 - rain) * 0.4 + min(vis, 10) * 3 - max(0, wind - 30) * 0.5 - (wc > 60) * 30
        scored.append((score, h["hour"], h["condition"], h["icon"], rain))
    if not scored:
        return {}
    best = max(scored, key=lambda x: x[0])
    return {
        "start": best[1], "condition": best[2], "icon": best[3],
        "rain_prob": best[4],
        "reason": f"Lowest rain & best visibility around {best[1]}"
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _best_departure(wcode: int | None, now_hour: int) -> str:
    if wcode is None:
        return "Check local traffic and road-authority alerts; live road data is not connected."
    if wcode >= 95:
        return "🚨 Wait for storm to clear — depart 2–3h after storm ends"
    if wcode in [63, 65, 80, 81, 82]:
        return "⚠️ Depart before 7 AM (beat rain) or after 4 PM"
    if wcode in [45, 48]:
        return "🌫️ Depart after 9 AM when fog typically lifts"
    if 7 <= now_hour <= 9:
        return "✅ Leave now — avoid peak city traffic (10 AM–12 PM)"
    if now_hour >= 22:
        return "🌙 Early morning departure (5–6 AM) recommended"
    return "✅ Good to go — normal driving conditions"


def _aqi_level(us_aqi) -> str:
    if us_aqi is None:
        return "Unknown"
    if us_aqi <= 50: return "Good ✅"
    if us_aqi <= 100: return "Moderate ⚠️"
    if us_aqi <= 150: return "Unhealthy for Sensitive Groups 😷"
    if us_aqi <= 200: return "Unhealthy 🚫"
    return "Very Unhealthy 🚨"


def _aqi_advice(us_aqi) -> str:
    if us_aqi is None:
        return "Air quality data unavailable"
    if us_aqi <= 50: return "Great air — perfect for outdoor activities!"
    if us_aqi <= 100: return "Acceptable — sensitive individuals limit prolonged outdoor exertion"
    if us_aqi <= 150: return "Sensitive groups: wear N95 mask outdoors"
    return "Poor air quality — wear N95 mask, limit outdoor exposure"


def _wind_dir(degrees: float | None) -> str:
    if degrees is None:
        return "Unknown"
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return dirs[round(degrees / 45) % 8]


def _daily_tip(wcode: int, rain_prob: int | None) -> str:
    if rain_prob is None:
        return "Forecast details are unavailable."
    if wcode >= 95: return "🚨 Thunderstorms — stay indoors, avoid road travel"
    if wcode >= 61 or rain_prob > 70: return "🌧️ Heavy rain — indoor activities; carry waterproof gear"
    if rain_prob > 40: return "🌦️ Chance of rain — carry umbrella; morning outdoor, afternoon indoor"
    if wcode == 0: return "☀️ Perfect day — ideal for all outdoor sightseeing"
    return "🌤️ Mostly fine — good for sightseeing & travel"


def _get_coords(city_key: str):
    return CITY_COORDS.get(city_key)


def _at(values, key_or_index, default=None):
    if isinstance(key_or_index, str):
        return values.get(key_or_index, default) if isinstance(values, dict) else default
    return values[key_or_index] if isinstance(values, list) and key_or_index < len(values) else default
