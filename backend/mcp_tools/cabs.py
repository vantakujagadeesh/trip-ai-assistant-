"""
MCP Tool: Cabs & Self-Drive Rentals
Provides outstation taxi estimates (Hatchback, Sedan, SUV, Innova Crysta)
and self-drive rental options (Zoomcar style per day rates).
"""
from typing import Optional, Dict, Any


async def get_cab_and_rental_options(
    origin: str,
    destination: str,
    days: int = 3,
    budget_inr: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Get outstation cab packages and self-drive car rental options.

    Args:
        origin: Pickup city (e.g. 'Delhi', 'Goa Airport')
        destination: Travel area / destination
        days: Trip duration in days
        budget_inr: Max budget filter in INR

    Returns:
        dict with outstation cab rates and self-drive car rentals
    """
    orig_title = origin.title()
    dest_title = destination.title()

    outstation_cabs = [
        {
            "category": "Sedan (Dzire / Etios)",
            "capacity": "4 Passengers + 2 Bags",
            "rate_per_km_inr": 12,
            "estimated_one_way_inr": 3500,
            "round_trip_daily_pkg_inr": 2800, # per day
            "total_estimated_inr": 2800 * days,
            "amenities": ["A/C", "Clean Sanitized Cab", "Doorstep Pickup", "Luggage Carrier"]
        },
        {
            "category": "SUV (Ertiga / Carens)",
            "capacity": "6 Passengers + 3 Bags",
            "rate_per_km_inr": 16,
            "estimated_one_way_inr": 4800,
            "round_trip_daily_pkg_inr": 3800, # per day
            "total_estimated_inr": 3800 * days,
            "amenities": ["A/C", "Extra Legroom", "Roof Carrier", "Top-rated Chauffeur"]
        },
        {
            "category": "Premium SUV (Innova Crysta)",
            "capacity": "7 Passengers + 4 Bags",
            "rate_per_km_inr": 22,
            "estimated_one_way_inr": 6800,
            "round_trip_daily_pkg_inr": 5200, # per day
            "total_estimated_inr": 5200 * days,
            "amenities": ["Leather Captain Seats", "Rear A/C", "Reclining Seats", "Premium Experience"]
        }
    ]

    self_drive_rentals = [
        {
            "car_model": "Maruti Swift / Hyundai i20",
            "transmission": "Manual / Petrol",
            "seats": 5,
            "price_per_day_inr": 1500,
            "total_rent_inr": 1500 * days,
            "fuel_included": False,
            "security_deposit_inr": 3000,
            "free_km_per_day": 250,
            "vendor": "Zoomcar / Drivezy"
        },
        {
            "car_model": "Mahindra Thar 4x4 / Creta",
            "transmission": "Automatic / Diesel",
            "seats": 5,
            "price_per_day_inr": 2800,
            "total_rent_inr": 2800 * days,
            "fuel_included": False,
            "security_deposit_inr": 5000,
            "free_km_per_day": 300,
            "vendor": "Zoomcar / Revv"
        },
        {
            "car_model": "Royal Enfield Classic 350 / Scooter",
            "transmission": "Motorcycle / Scooter",
            "seats": 2,
            "price_per_day_inr": 450,
            "total_rent_inr": 450 * days,
            "fuel_included": False,
            "security_deposit_inr": 1000,
            "free_km_per_day": "Unlimited",
            "vendor": "Goa Bike Rentals / Local Bike Hub"
        }
    ]

    return {
        "pickup": orig_title,
        "destination": dest_title,
        "duration_days": days,
        "outstation_cabs": outstation_cabs,
        "self_drive_rentals": self_drive_rentals,
        "cheapest_outstation_cab_day": min(c["round_trip_daily_pkg_inr"] for c in outstation_cabs),
        "cheapest_bike_scooter_day": 450,
        "recommendation": f"Renting a scooter (₹450/day) or self-drive car in {dest_title} gives you maximum freedom to explore at your own pace!"
    }
