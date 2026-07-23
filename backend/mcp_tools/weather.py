"""
MCP Tool: Weather Forecast
Uses Open-Meteo API — completely FREE, no API key required.
"""
import httpx
from typing import Optional


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
    coords = CITY_COORDS.get(loc_key)

    # Try fuzzy match
    if not coords:
        for key, val in CITY_COORDS.items():
            if loc_key in key or key in loc_key:
                coords = val
                break

    if not coords:
        return {"error": f"Location '{location}' not found", "weather": []}

    lat, lon = coords
    end = end_date or _add_days(start_date, 6)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weathercode",
                    "start_date": start_date,
                    "end_date": end,
                    "timezone": "auto",
                },
            )
            if resp.status_code != 200:
                return {"error": "Weather API unavailable", "weather": []}

            data = resp.json()
            daily = data.get("daily", {})
            dates = daily.get("time", [])
            forecast = []
            for i, date in enumerate(dates):
                wcode = daily.get("weathercode", [0])[i]
                forecast.append({
                    "date": date,
                    "max_temp_c": daily.get("temperature_2m_max", [25])[i],
                    "min_temp_c": daily.get("temperature_2m_min", [18])[i],
                    "rain_probability": daily.get("precipitation_probability_max", [20])[i],
                    "condition": WMO_CODES.get(wcode, "Variable"),
                    "icon": _weather_icon(wcode),
                    "travel_tip": _weather_tip(wcode, daily.get("precipitation_probability_max", [0])[i]),
                })
            return {
                "location": location,
                "forecast": forecast,
                "summary": _weather_summary(forecast),
            }
    except Exception as e:
        return {"error": str(e), "weather": []}


def _add_days(date_str: str, days: int) -> str:
    from datetime import datetime, timedelta
    d = datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=days)
    return d.strftime("%Y-%m-%d")


def _weather_icon(wcode: int) -> str:
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
    avg_temp = sum(d["max_temp_c"] for d in forecast) / len(forecast)
    rainy_days = sum(1 for d in forecast if d["rain_probability"] > 50)
    season = "warm" if avg_temp > 28 else "pleasant" if avg_temp > 20 else "cool"
    rain_txt = f", {rainy_days} rainy day{'s' if rainy_days != 1 else ''}" if rainy_days > 0 else ", mostly dry"
    return f"{season.capitalize()} weather (avg {avg_temp:.0f}°C){rain_txt}"
