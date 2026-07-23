"""
MCP Tool: Bus Search
Comprehensive intercity bus data for India + international coach services.
Covers KSRTC, RSRTC, RedBus, private operators.
"""
from typing import Optional


# ── Bus Route Database ──────────────────────────────────────────────────────
BUS_ROUTES = {
    # Goa routes
    ("DEL", "GOI"): [
        {"operator": "RSRTC Volvo", "type": "AC Sleeper", "departure": "17:00",
         "arrival": "19:00+1", "duration": "26h", "price": 2200,
         "amenities": ["AC", "Blanket", "Water", "Charging Point"]},
        {"operator": "VRL Travels", "type": "Non-AC Sleeper", "departure": "16:30",
         "arrival": "18:30+1", "duration": "26h", "price": 1400,
         "amenities": ["Blanket", "Water"]},
    ],
    ("BOM", "GOI"): [
        {"operator": "Paulo Travels", "type": "AC Sleeper (Volvo B11R)", "departure": "19:30",
         "arrival": "07:00+1", "duration": "11h 30m", "price": 1200,
         "amenities": ["AC", "Blanket", "Charging", "WiFi", "Water"]},
        {"operator": "Neeta Travels", "type": "AC Semi-Sleeper", "departure": "20:00",
         "arrival": "06:30+1", "duration": "10h 30m", "price": 850,
         "amenities": ["AC", "Water", "Charging"]},
        {"operator": "MSRTC Shivneri", "type": "AC Seater (Govt)", "departure": "06:00",
         "arrival": "18:00", "duration": "12h", "price": 650,
         "amenities": ["AC", "Water"]},
        {"operator": "VRL Travels", "type": "Non-AC Sleeper", "departure": "21:00",
         "arrival": "08:00+1", "duration": "11h", "price": 600,
         "amenities": ["Blanket", "Water"]},
    ],
    ("BLR", "GOI"): [
        {"operator": "SRS Travels", "type": "AC Sleeper (Volvo)", "departure": "20:30",
         "arrival": "08:30+1", "duration": "12h", "price": 1100,
         "amenities": ["AC", "Blanket", "Charging", "Water"]},
        {"operator": "KSRTC Airavat", "type": "AC Semi-Sleeper (Govt)", "departure": "19:00",
         "arrival": "07:00+1", "duration": "12h", "price": 750,
         "amenities": ["AC", "Water", "Charging"]},
    ],
    # Rajasthan routes
    ("DEL", "JAI"): [
        {"operator": "RSRTC Volvo", "type": "AC Seater (Govt)", "departure": "Every 30min",
         "arrival": "~5h later", "duration": "5h", "price": 550,
         "amenities": ["AC", "Water"]},
        {"operator": "IntrCity SmartBus", "type": "AC Sleeper (Luxury)", "departure": "22:30",
         "arrival": "04:00+1", "duration": "5h 30m", "price": 900,
         "amenities": ["AC", "WiFi", "Snacks", "Personal Screen", "Charging", "Blanket"]},
        {"operator": "Ordinary RSRTC", "type": "Non-AC Seater (Govt)", "departure": "Every 20min",
         "arrival": "~6h later", "duration": "6h", "price": 280,
         "amenities": ["Budget-friendly"]},
    ],
    ("JAI", "JDH"): [
        {"operator": "RSRTC Volvo", "type": "AC Seater", "departure": "05:30",
         "arrival": "11:00", "duration": "5h 30m", "price": 600,
         "amenities": ["AC", "Water"]},
        {"operator": "RSRTC Ordinary", "type": "Non-AC Seater", "departure": "Every 1hr",
         "arrival": "~6h later", "duration": "6h", "price": 320,
         "amenities": []},
    ],
    ("JDH", "JSM"): [
        {"operator": "RSRTC Express", "type": "AC Seater", "departure": "06:00",
         "arrival": "11:30", "duration": "5h 30m", "price": 480,
         "amenities": ["AC"]},
        {"operator": "Private Tempo", "type": "Shared Cab", "departure": "On demand",
         "arrival": "~5h later", "duration": "5h", "price": 350,
         "amenities": ["Door-to-door"]},
    ],
    # Kerala routes
    ("COK", "ALP"): [
        {"operator": "KSRTC Superfast", "type": "AC Seater", "departure": "Every 1hr",
         "arrival": "~5h later", "duration": "5h", "price": 380,
         "amenities": ["AC"]},
        {"operator": "KSRTC Ordinary", "type": "Non-AC Seater", "departure": "Every 30min",
         "arrival": "~6h later", "duration": "6h", "price": 160,
         "amenities": []},
    ],
    ("COK", "MUN"): [
        {"operator": "KSRTC Fast Passenger", "type": "Non-AC Seater", "departure": "Every 2hr",
         "arrival": "~4h30m later", "duration": "4h 30m", "price": 220,
         "amenities": []},
        {"operator": "Private Volvo", "type": "AC Seater", "departure": "08:00",
         "arrival": "12:30", "duration": "4h 30m", "price": 480,
         "amenities": ["AC", "Water"]},
    ],
    # Metropolitan
    ("DEL", "AGR"): [
        {"operator": "UPSRTC AC", "type": "AC Seater (Yamuna Expressway)", "departure": "Every 30min",
         "arrival": "~3h later", "duration": "3h", "price": 350,
         "amenities": ["AC", "Expressway"]},
        {"operator": "Private Volvo", "type": "AC Seater", "departure": "06:00",
         "arrival": "09:30", "duration": "3h 30m", "price": 500,
         "amenities": ["AC", "Snacks", "WiFi"]},
    ],
    ("BOM", "PNQ"): [
        {"operator": "MSRTC Shivneri", "type": "AC Seater (Govt Premium)", "departure": "Every 30min",
         "arrival": "~3h30m later", "duration": "3h 30m", "price": 650,
         "amenities": ["AC", "Water", "Charging"]},
        {"operator": "Neeta Travels", "type": "AC Semi-Sleeper", "departure": "22:00",
         "arrival": "01:30+1", "duration": "3h 30m", "price": 550,
         "amenities": ["AC", "Blanket"]},
    ],
}

# Generate reverse routes
_rev = {}
for (o, d), buses in list(BUS_ROUTES.items()):
    _rev[(d, o)] = buses
BUS_ROUTES.update(_rev)

# City code resolution
CITY_CODES = {
    "delhi": "DEL", "new delhi": "DEL", "mumbai": "BOM", "bombay": "BOM",
    "goa": "GOI", "panaji": "GOI", "bangalore": "BLR", "bengaluru": "BLR",
    "jaipur": "JAI", "jodhpur": "JDH", "jaisalmer": "JSM", "udaipur": "UDR",
    "agra": "AGR", "varanasi": "VNS", "kochi": "COK", "cochin": "COK",
    "alleppey": "ALP", "alappuzha": "ALP", "munnar": "MUN",
    "chennai": "MAA", "hyderabad": "HYD", "pune": "PNQ", "kolkata": "CCU",
}


async def search_buses(
    origin: str,
    destination: str,
    date: str,
    passengers: int = 1,
    bus_type: Optional[str] = None,  # "ac", "sleeper", "govt", "luxury"
) -> dict:
    """
    Search intercity bus routes.

    Args:
        origin: city name or code
        destination: city name or code
        date: YYYY-MM-DD
        passengers: number of travelers
        bus_type: filter by type ('ac', 'sleeper', 'govt', 'luxury')

    Returns:
        dict with bus options, prices, amenities
    """
    o_code = CITY_CODES.get(origin.lower().strip(), origin.upper()[:3])
    d_code = CITY_CODES.get(destination.lower().strip(), destination.upper()[:3])

    buses = BUS_ROUTES.get((o_code, d_code), [])

    if not buses:
        return {
            "route": f"{origin} → {destination}",
            "buses": [],
            "note": f"No direct bus data for this route. Check redbus.in for availability.",
            "booking_tip": "Book on RedBus app, AbhiBus, or respective state RTC website.",
        }

    result = []
    for b in buses:
        # Apply type filter
        if bus_type:
            bt = bus_type.lower()
            bus_desc = (b["type"] + " " + b["operator"]).lower()
            if bt == "ac" and "ac" not in bus_desc: continue
            if bt == "sleeper" and "sleeper" not in bus_desc: continue
            if bt == "govt" and "govt" not in bus_desc: continue
            if bt == "luxury" and not any(x in bus_desc for x in ["volvo", "luxury", "smart", "tejas"]): continue

        result.append({
            "operator": b["operator"],
            "type": b["type"],
            "departure": b["departure"],
            "arrival": b["arrival"],
            "duration": b["duration"],
            "price_per_person": b["price"],
            "total_price": b["price"] * passengers,
            "amenities": b["amenities"],
        })

    cheapest = min(result, key=lambda x: x["price_per_person"]) if result else None

    return {
        "route": f"{origin} → {destination}",
        "date": date,
        "passengers": passengers,
        "buses": result,
        "cheapest_option": cheapest["operator"] if cheapest else None,
        "cheapest_inr": cheapest["price_per_person"] if cheapest else None,
        "booking_tip": "Book on RedBus, AbhiBus, or state RTC website. Book 2-7 days ahead for best prices.",
    }
