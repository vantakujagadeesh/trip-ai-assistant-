"""Train search availability.

The app does not currently have a live rail inventory integration. This module
returns an explicit unavailable state rather than invented schedules or fares.
"""
from datetime import date
from typing import Any, Dict, Optional


async def search_trains(
    origin: str,
    destination: str,
    travel_date: str,
    budget_inr: Optional[float] = None,
) -> Dict[str, Any]:
    """Return train-search capability and the official booking portal."""
    route = f"{origin.strip().title()} → {destination.strip().title()}"
    result = {
        "route": route,
        "date": travel_date,
        "trains_count": 0,
        "cheapest_fare_inr": None,
        "trains": [],
        "status": "not_integrated",
        "source": None,
        "availability_checked": False,
        "booking_portal": "https://www.irctc.co.in/nget/train-search",
        "note": "Live train schedules, fares, and seat availability are not connected.",
    }
    try:
        date.fromisoformat(travel_date)
    except ValueError:
        return {**result, "status": "invalid_date", "note": "Travel date must use YYYY-MM-DD."}
    return result
