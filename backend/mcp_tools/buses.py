"""
MCP Tool: Intercity Bus Search
Provides realistic intercity bus options (Volvo AC Multi-Axle Sleeper, Scania, BharatBenz, Electric Buses)
with operators, boarding/dropping points, amenities (WiFi, charging, blankets), and fares in INR.
"""
from typing import Optional, List, Dict, Any

BUS_OPERATORS = [
    {"name": "IntrCity SmartBus", "rating": 4.8, "type": "Volvo Multi-Axle AC Sleeper (2+1)"},
    {"name": "Zingbus", "rating": 4.6, "type": "AC Sleeper / Seater (2+1)"},
    {"name": "KSRTC Swift / Kadamba", "rating": 4.5, "type": "Gajraj Volvo AC Multi-Axle"},
    {"name": "Paulo Travels", "rating": 4.3, "type": "AC Sleeper (2+1)"},
    {"name": "VRL Travels", "rating": 4.7, "type": "I-Shift Volvo Multi-Axle Sleeper"},
    {"name": "NueGo Electric Bus", "rating": 4.9, "type": "AC Electric Seater / Sleeper"},
]


async def search_buses(
    origin: str,
    destination: str,
    travel_date: str,
    budget_inr: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Search intercity bus routes between origin and destination.

    Args:
        origin: Departure city (e.g. 'Delhi', 'Mumbai', 'Bangalore')
        destination: Arrival city (e.g. 'Goa', 'Jaipur', 'Kochi')
        travel_date: YYYY-MM-DD
        budget_inr: Maximum budget filter in INR

    Returns:
        dict with list of bus operators, bus types, departure/arrival times, amenities, and fares
    """
    orig_title = origin.title()
    dest_title = destination.title()

    buses = [
        {
            "operator": "IntrCity SmartBus",
            "bus_type": "Volvo Multi-Axle A/C Sleeper (2+1)",
            "departure": "19:30",
            "arrival": "08:15 (+1 day)",
            "duration": "12h 45m",
            "fare_inr": 1250,
            "rating": 4.8,
            "seats_left": 14,
            "boarding_point": f"{orig_title} Main Bus Terminal / City Center",
            "dropping_point": f"{dest_title} Central Bus Stand",
            "amenities": ["A/C", "Personal TV", "Charging Point", "Blanket", "Water Bottle", "Free WiFi", "GPS Live Tracking"]
        },
        {
            "operator": "Zingbus Premium",
            "bus_type": "BharatBenz A/C Sleeper (2+1)",
            "departure": "20:45",
            "arrival": "09:00 (+1 day)",
            "duration": "12h 15m",
            "fare_inr": 990,
            "rating": 4.6,
            "seats_left": 8,
            "boarding_point": f"{orig_title} Bypass Flyover Hub",
            "dropping_point": f"{dest_title} Beach Road / City Station",
            "amenities": ["A/C", "Charging Point", "Blanket", "Reading Light", "Live Tracking"]
        },
        {
            "operator": "VRL Travels",
            "bus_type": "Volvo I-Shift Multi-Axle AC Sleeper",
            "departure": "18:15",
            "arrival": "06:45 (+1 day)",
            "duration": "12h 30m",
            "fare_inr": 1490,
            "rating": 4.7,
            "seats_left": 22,
            "boarding_point": f"{orig_title} VRL Terminal",
            "dropping_point": f"{dest_title} VRL Office Circle",
            "amenities": ["A/C", "Reclining Sleeper", "Emergency Button", "Charging Point", "Blanket"]
        },
        {
            "operator": "NueGo Zero Emission Bus",
            "bus_type": "Premium AC Electric Seater",
            "departure": "07:00",
            "arrival": "17:30",
            "duration": "10h 30m",
            "fare_inr": 750,
            "rating": 4.9,
            "seats_left": 31,
            "boarding_point": f"{orig_title} Eco Transit Hub",
            "dropping_point": f"{dest_title} Green Terminal",
            "amenities": ["Quiet Electric Ride", "A/C", "Type-C Fast Charging", "Reclining Seats", "WiFi"]
        }
    ]

    # Filter by budget if provided
    filtered_buses = []
    for bus in buses:
        if not budget_inr or bus["fare_inr"] <= budget_inr:
            filtered_buses.append(bus)

    if not filtered_buses:
        filtered_buses = buses[:2]  # Fallback to display top choices

    cheapest_fare = min(b["fare_inr"] for b in filtered_buses)

    return {
        "route": f"{orig_title} → {dest_title}",
        "date": travel_date,
        "total_buses": len(filtered_buses),
        "cheapest_fare_inr": cheapest_fare,
        "buses": sorted(filtered_buses, key=lambda x: x["fare_inr"]),
        "booking_portal": "RedBus / AbhiBus / IntrCity",
        "tip": "Overnight Volvo Sleeper buses save you 1 night of hotel cost!"
    }
