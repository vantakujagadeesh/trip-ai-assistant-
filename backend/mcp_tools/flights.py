"""
MCP Tool: Flight Search
Uses Amadeus API (free sandbox tier)
"""
import os
import httpx
from typing import Optional
from datetime import datetime

AMADEUS_BASE_URL = os.getenv("AMADEUS_BASE_URL", "https://test.api.amadeus.com")
_amadeus_token: Optional[str] = None
_token_expires: float = 0


async def _get_amadeus_token() -> str:
    """Fetch and cache Amadeus OAuth2 token."""
    global _amadeus_token, _token_expires
    import time
    if _amadeus_token and time.time() < _token_expires - 60:
        return _amadeus_token

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{AMADEUS_BASE_URL}/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": os.getenv("AMADEUS_API_KEY", ""),
                "client_secret": os.getenv("AMADEUS_API_SECRET", ""),
            },
        )
        if resp.status_code != 200:
            raise ValueError(f"Amadeus auth failed: {resp.text}")
        data = resp.json()
        _amadeus_token = data["access_token"]
        _token_expires = time.time() + int(data.get("expires_in", 1799))
        return _amadeus_token


async def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    adults: int = 1,
    budget_inr: Optional[float] = None,
    return_date: Optional[str] = None,
) -> dict:
    """
    Search flights using Amadeus Flight Offers API.

    Args:
        origin: IATA city code (e.g., 'DEL', 'BOM', 'BLR')
        destination: IATA city code (e.g., 'GOI' for Goa, 'MXP' for Milan)
        departure_date: YYYY-MM-DD format
        adults: number of passengers
        budget_inr: max budget in INR (optional filter)
        return_date: return date for round-trip (optional)

    Returns:
        dict with flight offers sorted by price
    """
    # Use mock data when API key is not configured (for demo purposes)
    if not os.getenv("AMADEUS_API_KEY") or os.getenv("AMADEUS_API_KEY") == "your_amadeus_api_key_here":
        return _mock_flight_data(origin, destination, departure_date, budget_inr)

    try:
        token = await _get_amadeus_token()
        params = {
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": departure_date,
            "adults": adults,
            "max": 5,
            "currencyCode": "INR",
        }
        if return_date:
            params["returnDate"] = return_date

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{AMADEUS_BASE_URL}/v2/shopping/flight-offers",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )
            if resp.status_code != 200:
                return {"error": f"Flight search failed: {resp.status_code}", "offers": []}

            data = resp.json()
            offers = []
            for offer in data.get("data", [])[:5]:
                price = float(offer["price"]["total"])
                if budget_inr and price > budget_inr:
                    continue
                itineraries = offer.get("itineraries", [{}])
                segments = itineraries[0].get("segments", [{}]) if itineraries else [{}]
                first_seg = segments[0] if segments else {}
                last_seg = segments[-1] if segments else {}
                offers.append({
                    "airline": first_seg.get("carrierCode", "Unknown"),
                    "departure": first_seg.get("departure", {}).get("at", ""),
                    "arrival": last_seg.get("arrival", {}).get("at", ""),
                    "duration": itineraries[0].get("duration", ""),
                    "stops": len(segments) - 1,
                    "price_inr": price,
                    "booking_class": offer.get("travelerPricings", [{}])[0].get("fareDetailsBySegment", [{}])[0].get("cabin", "ECONOMY"),
                })
            return {
                "route": f"{origin} → {destination}",
                "date": departure_date,
                "offers": sorted(offers, key=lambda x: x["price_inr"]),
                "cheapest_inr": min([o["price_inr"] for o in offers]) if offers else None,
            }
    except Exception as e:
        return _mock_flight_data(origin, destination, departure_date, budget_inr)


def _mock_flight_data(origin: str, destination: str, date: str, budget: Optional[float]) -> dict:
    """Return realistic mock flight data when API is unavailable."""
    dest_prices = {
        "GOI": 4500, "DEL": 3800, "BOM": 4200, "BLR": 3500,
        "MXP": 45000, "CDG": 48000, "NRT": 55000, "HND": 55000,
    }
    base_price = dest_prices.get(destination, 6000)
    return {
        "route": f"{origin} → {destination}",
        "date": date,
        "offers": [
            {
                "airline": "IndiGo",
                "departure": f"{date}T06:30:00",
                "arrival": f"{date}T08:45:00",
                "duration": "PT2H15M",
                "stops": 0,
                "price_inr": base_price,
                "booking_class": "ECONOMY",
            },
            {
                "airline": "Air India",
                "departure": f"{date}T11:00:00",
                "arrival": f"{date}T13:30:00",
                "duration": "PT2H30M",
                "stops": 0,
                "price_inr": base_price * 1.15,
                "booking_class": "ECONOMY",
            },
        ],
        "cheapest_inr": base_price,
        "note": "Demo data — add Amadeus API key for live prices",
    }
