"""
MCP Tool: Train Search
Comprehensive Indian Railways + International rail data.
Uses curated route database (IRCTC API requires special approval).
"""
from typing import Optional
from datetime import datetime, timedelta


# ── Indian Railways Route Database ────────────────────────────────────────────
TRAIN_ROUTES = {
    # Delhi routes
    ("DEL", "GOI"): [
        {"train": "Goa Express (12779)", "departure": "15:00", "arrival": "05:40+1",
         "duration": "14h 40m", "price_sl": 545, "price_3ac": 1420, "price_2ac": 2050,
         "frequency": "Daily", "type": "Express"},
        {"train": "Nizamuddin-Madgaon Rajdhani (12431)", "departure": "11:05", "arrival": "04:30+1",
         "duration": "17h 25m", "price_3ac": 2785, "price_2ac": 3985, "price_1ac": 6720,
         "frequency": "Bi-weekly", "type": "Rajdhani"},
    ],
    ("DEL", "JAI"): [
        {"train": "Shatabdi Express (12015)", "departure": "06:05", "arrival": "10:30",
         "duration": "4h 25m", "price_cc": 780, "price_ec": 1555,
         "frequency": "Daily except Sun", "type": "Shatabdi"},
        {"train": "Ajmer Shatabdi (12016)", "departure": "17:40", "arrival": "22:15",
         "duration": "4h 35m", "price_cc": 780, "price_ec": 1555,
         "frequency": "Daily except Sun", "type": "Shatabdi"},
        {"train": "Double Decker (12985)", "departure": "06:10", "arrival": "10:50",
         "duration": "4h 40m", "price_cc": 540,
         "frequency": "Daily", "type": "Double Decker"},
    ],
    ("DEL", "AGR"): [
        {"train": "Gatimaan Express (12050)", "departure": "08:10", "arrival": "09:50",
         "duration": "1h 40m", "price_cc": 690, "price_ec": 1365,
         "frequency": "Daily except Fri", "type": "Semi-HSR"},
        {"train": "Shatabdi Express (12001)", "departure": "06:00", "arrival": "07:57",
         "duration": "1h 57m", "price_cc": 630, "price_ec": 1210,
         "frequency": "Daily except Sun", "type": "Shatabdi"},
    ],
    ("DEL", "VNS"): [
        {"train": "Vande Bharat Express (22436)", "departure": "06:00", "arrival": "14:00",
         "duration": "8h 00m", "price_cc": 1570, "price_ec": 2820,
         "frequency": "Daily except Tue", "type": "Vande Bharat"},
        {"train": "Mahakal Express (12165)", "departure": "14:30", "arrival": "04:35+1",
         "duration": "14h 05m", "price_sl": 415, "price_3ac": 1080,
         "frequency": "Daily", "type": "Superfast"},
    ],
    # Mumbai routes
    ("BOM", "GOI"): [
        {"train": "Konkan Kanya Express (10111)", "departure": "23:00", "arrival": "11:15+1",
         "duration": "12h 15m", "price_sl": 395, "price_3ac": 1055, "price_2ac": 1530,
         "frequency": "Daily", "type": "Express"},
        {"train": "Tejas Express (22119)", "departure": "06:00", "arrival": "14:20",
         "duration": "8h 20m", "price_cc": 1240, "price_ec": 2320,
         "frequency": "Except Mon,Wed", "type": "Tejas"},
    ],
    ("BOM", "DEL"): [
        {"train": "Rajdhani Express (12951)", "departure": "17:00", "arrival": "08:35+1",
         "duration": "15h 35m", "price_3ac": 2430, "price_2ac": 3560, "price_1ac": 5950,
         "frequency": "Daily", "type": "Rajdhani"},
        {"train": "Duronto Express (12223)", "departure": "23:15", "arrival": "15:55+1",
         "duration": "16h 40m", "price_3ac": 2120, "price_2ac": 3080,
         "frequency": "4 days/week", "type": "Duronto"},
    ],
    ("BOM", "JAI"): [
        {"train": "Mumbai-Jaipur SF (12955)", "departure": "18:10", "arrival": "07:00+1",
         "duration": "12h 50m", "price_sl": 480, "price_3ac": 1280, "price_2ac": 1870,
         "frequency": "Daily", "type": "Superfast"},
    ],
    # Bangalore routes
    ("BLR", "GOI"): [
        {"train": "Vasco Da Gama Express (17311)", "departure": "20:45", "arrival": "11:30+1",
         "duration": "14h 45m", "price_sl": 380, "price_3ac": 995,
         "frequency": "Daily", "type": "Express"},
    ],
    ("BLR", "COK"): [
        {"train": "Kochuveli Express (16315)", "departure": "20:00", "arrival": "08:30+1",
         "duration": "12h 30m", "price_sl": 345, "price_3ac": 920,
         "frequency": "Daily", "type": "Express"},
    ],
    # International routes (Shinkansen, Eurostar, etc.)
    ("NRT", "KYO"): [
        {"train": "Shinkansen Nozomi", "departure": "Every 10min", "arrival": "~2h 15m later",
         "duration": "2h 15m", "price_cc": 11000, "price_ec": 14500,
         "frequency": "Every 10 min", "type": "Bullet Train",
         "note": "Covered by JR Pass (7-day ¥50,000 / ₹26,500)"},
    ],
    ("CDG", "FCO"): [
        {"train": "TGV + Frecciarossa", "departure": "06:30", "arrival": "17:30",
         "duration": "11h 00m", "price_cc": 8500, "price_ec": 14500,
         "frequency": "Daily", "type": "High-Speed",
         "note": "Change at Lyon/Turin. Fly is faster (2h) for ~same price."},
    ],
}

# Reverse routes (same data, swap origin/destination)
_reverse_routes = {}
for (o, d), trains in list(TRAIN_ROUTES.items()):
    _reverse_routes[(d, o)] = trains
TRAIN_ROUTES.update(_reverse_routes)


async def search_trains(
    origin: str,
    destination: str,
    date: str,
    passengers: int = 1,
    preferred_class: Optional[str] = None,
) -> dict:
    """
    Search train routes between two cities.

    Args:
        origin: IATA code or city name
        destination: IATA code or city name
        date: YYYY-MM-DD travel date
        passengers: number of travelers
        preferred_class: 'SL' (Sleeper), '3AC', '2AC', '1AC', 'CC' (Chair Car), 'EC' (Executive)

    Returns:
        dict with available trains, prices, timings
    """
    origin_code = _resolve_code(origin)
    dest_code = _resolve_code(destination)

    key = (origin_code, dest_code)
    trains = TRAIN_ROUTES.get(key, [])

    if not trains:
        # Try partial match
        for (o, d), t in TRAIN_ROUTES.items():
            if origin_code[:2] in o and dest_code[:2] in d:
                trains = t
                break

    if not trains:
        return {
            "route": f"{origin} → {destination}",
            "trains": [],
            "note": f"No direct train data for this route. Consider bus or flight.",
            "tip": "Book at irctc.co.in — Tatkal opens 10am (AC) / 11am (SL), 1 day before travel."
        }

    result_trains = []
    for t in trains:
        prices = {}
        for cls in ["price_sl", "price_3ac", "price_2ac", "price_1ac", "price_cc", "price_ec"]:
            if cls in t:
                label = cls.replace("price_", "").upper()
                prices[label] = t[cls] * passengers
        
        result_trains.append({
            "name": t["train"],
            "type": t["type"],
            "departure": t["departure"],
            "arrival": t["arrival"],
            "duration": t["duration"],
            "frequency": t["frequency"],
            "prices": prices,
            "cheapest_inr": min(prices.values()) if prices else 0,
            "note": t.get("note", ""),
        })

    cheapest = min(result_trains, key=lambda x: x["cheapest_inr"])

    return {
        "route": f"{origin} → {destination}",
        "date": date,
        "passengers": passengers,
        "trains": result_trains,
        "cheapest_option": cheapest["name"],
        "cheapest_inr": cheapest["cheapest_inr"],
        "booking_tip": "Book at irctc.co.in. Tatkal: 10am (AC), 11am (SL), 1 day prior. 120-day advance booking.",
    }


def _resolve_code(name: str) -> str:
    codes = {
        "delhi": "DEL", "new delhi": "DEL", "mumbai": "BOM", "bombay": "BOM",
        "goa": "GOI", "bangalore": "BLR", "bengaluru": "BLR",
        "jaipur": "JAI", "agra": "AGR", "varanasi": "VNS",
        "chennai": "MAA", "hyderabad": "HYD", "kolkata": "CCU",
        "kochi": "COK", "pune": "PNQ",
        "tokyo": "NRT", "kyoto": "KYO", "paris": "CDG", "rome": "FCO",
    }
    return codes.get(name.lower().strip(), name.upper()[:3])
