"""
MCP Tool: Live Weather + Road Conditions
- Current weather (temp, feels-like, UV index, humidity, wind) via Open-Meteo (FREE, no API key)
- Hourly weather for next 12h (rain probability, visibility, wind)
- 7-day daily forecast with travel suitability rating
- Air Quality Index via Open-Meteo AQ endpoint
- Road condition analysis: highway alerts, blockage risk, fog/rain hazards, mountain warnings
- Smart travel advisories: best departure time, best travel window, packing list
"""
import httpx
import asyncio
from typing import Optional
from datetime import datetime


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
    coords = _get_coords(dest_key)

    if not coords:
        # Return minimal data with no-coord fallback
        return {
            "destination": destination, "origin": origin,
            "current_weather": {},
            "hourly_forecast": [],
            "daily_forecast": [],
            "air_quality": {},
            "road_conditions": {"risk_level": "UNKNOWN", "alerts": [], "conditions": []},
            "travel_advisories": [],
            "best_travel_window": {},
            "timestamp": datetime.now().isoformat(),
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
    road = _get_road_conditions(origin_key, dest_key, current_hourly)

    # Smart combined advisories
    advisories = _generate_advisories(current_hourly, daily, road)

    return {
        "destination": destination,
        "origin": origin,
        "current_weather": current_hourly.get("current", {}),
        "hourly_forecast": current_hourly.get("hourly", [])[:12],
        "daily_forecast": daily.get("forecast", []),
        "air_quality": aq,
        "road_conditions": road,
        "travel_advisories": advisories,
        "best_travel_window": _best_travel_window(current_hourly.get("hourly", [])),
        "timestamp": datetime.now().isoformat(),
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
            if resp.status_code != 200:
                return {}

            data = resp.json()
            cr = data.get("current", {})
            hr = data.get("hourly", {})

            wc = cr.get("weathercode", 0)
            wi = WMO_CODES.get(wc, ("Variable", "🌡️", "outdoor"))

            current = {
                "temp_c": cr.get("temperature_2m"),
                "feels_like_c": cr.get("apparent_temperature"),
                "humidity_pct": cr.get("relative_humidity_2m"),
                "wind_kmh": cr.get("wind_speed_10m"),
                "wind_direction": _wind_dir(cr.get("wind_direction_10m", 0)),
                "precipitation_mm": cr.get("precipitation", 0),
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
                hwc = hr.get("weathercode", [0] * 24)[i]
                hwi = WMO_CODES.get(hwc, ("Variable", "🌡️", "outdoor"))
                vis_raw = hr.get("visibility", [10000] * 24)[i]
                hourly.append({
                    "time": t,
                    "hour": t[11:16] if len(t) > 10 else t,
                    "temp_c": hr.get("temperature_2m", [25] * 24)[i],
                    "feels_like_c": hr.get("apparent_temperature", [25] * 24)[i],
                    "rain_prob": hr.get("precipitation_probability", [0] * 24)[i],
                    "wind_kmh": hr.get("wind_speed_10m", [10] * 24)[i],
                    "visibility_km": round((vis_raw or 10000) / 1000, 1),
                    "condition": hwi[0],
                    "icon": hwi[1],
                    "weathercode": hwc,
                })

            return {"current": current, "hourly": hourly}
    except Exception:
        return {}


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
            if resp.status_code != 200:
                return {}
            dr = resp.json().get("daily", {})
            forecast = []
            for i, d in enumerate(dr.get("time", [])):
                wc = dr.get("weathercode", [0])[i]
                wi = WMO_CODES.get(wc, ("Variable", "🌡️", "outdoor"))
                rain = dr.get("precipitation_probability_max", [20])[i] or 0
                forecast.append({
                    "date": d,
                    "max_temp_c": dr.get("temperature_2m_max", [30])[i],
                    "min_temp_c": dr.get("temperature_2m_min", [20])[i],
                    "rain_probability": rain,
                    "condition": wi[0],
                    "icon": wi[1],
                    "activity_suitability": wi[2],
                    "uv_max": dr.get("uv_index_max", [5])[i],
                    "max_wind_kmh": dr.get("wind_speed_10m_max", [15])[i],
                    "sunrise": (dr.get("sunrise", [""])[i] or "")[-5:],
                    "sunset": (dr.get("sunset", [""])[i] or "")[-5:],
                    "is_good_travel_day": rain < 40 and wc < 61,
                    "travel_tip": _daily_tip(wc, rain),
                })
            return {"forecast": forecast}
    except Exception:
        return {}


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
            if resp.status_code != 200:
                return {}
            c = resp.json().get("current", {})
            us = c.get("us_aqi")
            return {
                "pm2_5": c.get("pm2_5"),
                "pm10": c.get("pm10"),
                "us_aqi": us,
                "eu_aqi": c.get("european_aqi"),
                "level": _aqi_level(us),
                "health_advice": _aqi_advice(us),
            }
    except Exception:
        return {}


# ── Road Conditions Analyzer ──────────────────────────────────────────────────

def _get_road_conditions(origin_key, dest_key, weather_data: dict) -> dict:
    alerts = []
    conditions = []
    detour_advice = []
    risk_level = "LOW"

    # Find route
    route_key = None
    for (o, d) in HIGHWAY_ROUTES:
        if origin_key and o in (origin_key or "") and d in dest_key:
            route_key = (o, d)
            break
    if not route_key:
        for (o, d) in HIGHWAY_ROUTES:
            if d in dest_key:
                route_key = (o, d)
                break

    route_info = HIGHWAY_ROUTES.get(route_key, {})
    current = weather_data.get("current", {})
    hourly = weather_data.get("hourly", [])

    wcode = current.get("weathercode", 0)
    wind = current.get("wind_kmh") or 10
    rain_mm = current.get("precipitation_mm") or 0
    temp = current.get("temp_c") or 25
    visibility = hourly[0].get("visibility_km", 10) if hourly else 10

    # ── Weather-based road risk assessment ──
    if wcode >= 95:
        risk_level = "CRITICAL"
        alerts.append("🚨 ACTIVE THUNDERSTORM — Road travel strongly discouraged")
        alerts.append("⚠️ Risk of flash flooding on low-lying roads & underpasses")
        detour_advice.append("Stay indoors — delay departure by at least 2–3 hours after storm clears")

    elif wcode in [63, 65, 80, 81, 82]:
        risk_level = "HIGH"
        alerts.append("🌧️ Heavy rain — reduced road visibility & hydroplaning risk on highways")
        alerts.append("⚠️ Possible waterlogging in city underpasses & low-lying roads")
        if route_info.get("mountain"):
            alerts.append("🏔️ Mountain/ghat section CLOSED risk — check NHAI/highway authority before leaving")
            detour_advice.append("Avoid ghat roads during heavy rain; take valley/bypass route if available")

    elif wcode in [51, 53, 55, 61]:
        risk_level = "MODERATE"
        alerts.append("🌦️ Moderate rain — reduce highway speed by 20 km/h, use headlights")

    if wind > 60:
        risk_level = "HIGH" if risk_level not in ["HIGH", "CRITICAL"] else risk_level
        alerts.append(f"💨 Strong winds ({wind:.0f} km/h) — high-sided vehicles & two-wheelers at risk")

    if visibility < 0.5:
        risk_level = "HIGH" if risk_level not in ["HIGH", "CRITICAL"] else risk_level
        alerts.append(f"🌫️ Very low visibility ({visibility:.1f} km) — fog lights mandatory; drive <40 km/h")
        detour_advice.append("Delay departure until 9–10 AM when fog usually lifts")
    elif visibility < 1.5:
        risk_level = "MODERATE" if risk_level == "LOW" else risk_level
        alerts.append(f"🌫️ Reduced visibility ({visibility:.1f} km) — drive cautiously")

    if temp > 42:
        conditions.append("🌡️ Extreme heat (>42°C) — carry 2+ litres water; avoid driving 12–4 PM")
        conditions.append("🚗 Check tyre pressure before highway driving — heat causes blowouts")

    # ── Mountain road specific ──
    mountain_dest = any(x in dest_key for x in ["manali", "shimla", "leh", "darjeeling", "ooty", "munnar", "coorg", "kodaikanal", "gangtok"])
    if mountain_dest or route_info.get("mountain"):
        conditions.append("🏔️ Mountain road — sharp hairpin bends, single-lane sections; use low gear")
        conditions.append("⛽ Fill fuel at last major town before hills — petrol stations are sparse")
        conditions.append("📡 Mobile network may be limited — download offline maps (Google Maps/OsmAnd)")
        if wcode >= 61:
            alerts.append("🚨 Landslide / mudslide risk on mountain roads in rain — check BRO / NHAI updates")
            risk_level = "HIGH" if risk_level not in ["CRITICAL"] else risk_level

    # ── Route info block ──
    if route_info:
        conditions.append(f"🛣️ Route: {route_info['highways'][0]}")
        conditions.append(f"📏 {route_info['distance_km']} km — normal travel time: {route_info['normal_duration']}")
        conditions.append(f"📍 Via: {route_info['via']}")
        if wcode >= 63 or wind > 50:
            extra_time = "add 1–2h to your ETA"
        elif wcode >= 51:
            extra_time = "add 30–45 min to your ETA"
        else:
            extra_time = "normal ETA expected"
        conditions.append(f"⏱️ Weather impact: {extra_time}")

    # ── Night driving ──
    now_hour = datetime.now().hour
    if 21 <= now_hour or now_hour < 5:
        conditions.append("🌙 Night driving — beware of animals crossing highway; use high beams responsibly")
        conditions.append("😴 Plan rest stops every 2 hours on long overnight drives")

    # ── If all clear ──
    if not alerts:
        conditions.insert(0, "✅ Roads clear — normal driving conditions")

    # ── Always-on safety tips ──
    conditions.append("📱 Download Google Maps offline for this route before leaving")
    conditions.append("⛽ Keep fuel above 50% on inter-city highways")

    return {
        "risk_level": risk_level,
        "risk_color": {"LOW": "green", "MODERATE": "amber", "HIGH": "red", "CRITICAL": "red"}[risk_level],
        "risk_icon": {"LOW": "✅", "MODERATE": "⚠️", "HIGH": "🔴", "CRITICAL": "🚨"}[risk_level],
        "alerts": alerts,
        "conditions": conditions,
        "detour_advice": detour_advice,
        "route_info": route_info,
        "best_departure_time": _best_departure(wcode, now_hour),
    }


# ── Smart Advisories Builder ──────────────────────────────────────────────────

def _generate_advisories(current_hourly: dict, daily: dict, road: dict) -> list:
    advisories = []
    current = current_hourly.get("current", {})
    hourly = current_hourly.get("hourly", [])
    wcode = current.get("weathercode", 0)
    temp = current.get("temp_c") or 25
    uv = current.get("uv_index") or 0

    # Packing advice
    packing = []
    if wcode >= 51:
        packing += ["☂️ Compact rain jacket / umbrella", "💧 Waterproof bag cover"]
    if temp > 35 or uv > 7:
        packing += ["🧴 Sunscreen SPF 50+", "🕶️ UV-blocking sunglasses", "🎩 Wide-brim hat"]
    if temp < 15:
        packing += ["🧥 Warm jacket / thermal layers", "🧤 Gloves"]
    if uv > 9:
        packing.append(f"☀️ Extreme UV ({uv:.0f}) — reapply sunscreen every 90 min")
    if packing:
        advisories.append({"type": "packing", "icon": "🎒", "title": "What to Pack", "items": packing})

    # Best activity hours
    good = [h for h in hourly[:12] if (h.get("rain_prob") or 0) < 30 and h.get("weathercode", 99) < 61]
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

    # Best travel days this week
    good_days = [d for d in daily.get("forecast", [])[:7] if d.get("is_good_travel_day")]
    if good_days:
        advisories.append({
            "type": "best_days", "icon": "📅", "title": "Best Travel Days This Week",
            "items": [
                f"{d['date']}: {d['icon']} {d['condition']} (max {d['max_temp_c']}°C, {d['rain_probability']}% rain)"
                for d in good_days[:3]
            ]
        })

    return advisories


def _best_travel_window(hourly: list) -> dict:
    if not hourly:
        return {"start": "Morning", "reason": "Early morning generally clearest"}
    scored = []
    for h in hourly[:12]:
        rain = h.get("rain_prob") or 50
        wc = h.get("weathercode") or 3
        vis = h.get("visibility_km") or 10
        wind = h.get("wind_kmh") or 20
        score = (100 - rain) * 0.4 + min(vis, 10) * 3 - max(0, wind - 30) * 0.5 - (wc > 60) * 30
        scored.append((score, h["hour"], h["condition"], h["icon"], rain))
    best = max(scored, key=lambda x: x[0])
    return {
        "start": best[1], "condition": best[2], "icon": best[3],
        "rain_prob": best[4],
        "reason": f"Lowest rain & best visibility around {best[1]}"
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _best_departure(wcode: int, now_hour: int) -> str:
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


def _wind_dir(degrees: float) -> str:
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return dirs[round(degrees / 45) % 8]


def _daily_tip(wcode: int, rain_prob: int) -> str:
    if wcode >= 95: return "🚨 Thunderstorms — stay indoors, avoid road travel"
    if wcode >= 61 or rain_prob > 70: return "🌧️ Heavy rain — indoor activities; carry waterproof gear"
    if rain_prob > 40: return "🌦️ Chance of rain — carry umbrella; morning outdoor, afternoon indoor"
    if wcode == 0: return "☀️ Perfect day — ideal for all outdoor sightseeing"
    return "🌤️ Mostly fine — good for sightseeing & travel"


def _get_coords(city_key: str):
    coords = CITY_COORDS.get(city_key)
    if coords:
        return coords
    for key, val in CITY_COORDS.items():
        if city_key in key or key in city_key:
            return val
    return None
