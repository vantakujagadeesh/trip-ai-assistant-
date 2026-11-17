"""Ground transport search availability."""
from typing import Any, Dict, Optional


async def get_cab_and_rental_options(
    origin: str,
    destination: str,
    days: int = 3,
    budget_inr: Optional[float] = None,
) -> Dict[str, Any]:
    """Return an explicit unavailable state until a live quote provider is added."""
    return {
        "pickup": origin.strip().title(),
        "destination": destination.strip().title(),
        "duration_days": days,
        "outstation_cabs": [],
        "self_drive_rentals": [],
        "status": "not_integrated",
        "source": None,
        "availability_checked": False,
        "note": "Live cab and rental quotes, prices, and vehicle availability are not connected.",
    }
