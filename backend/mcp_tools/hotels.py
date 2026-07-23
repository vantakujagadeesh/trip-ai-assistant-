"""
MCP Tool: Hotel Search
Uses Amadeus Hotel API (free sandbox tier)
"""
import os
import httpx
from typing import Optional
from mcp_tools.flights import _get_amadeus_token

AMADEUS_BASE_URL = os.getenv("AMADEUS_BASE_URL", "https://test.api.amadeus.com")


async def search_hotels(
    city_code: str,
    check_in: str,
    check_out: str,
    adults: int = 2,
    budget_per_night_inr: Optional[float] = None,
) -> dict:
    """
    Search hotels using Amadeus Hotel Offers API.

    Args:
        city_code: IATA city code (e.g., 'GOI', 'DEL', 'PAR')
        check_in: YYYY-MM-DD
        check_out: YYYY-MM-DD
        adults: number of guests
        budget_per_night_inr: max price per night in INR

    Returns:
        dict with hotel offers sorted by price
    """
    if not os.getenv("AMADEUS_API_KEY") or os.getenv("AMADEUS_API_KEY") == "your_amadeus_api_key_here":
        return _mock_hotel_data(city_code, check_in, check_out, budget_per_night_inr)

    try:
        token = await _get_amadeus_token()
        async with httpx.AsyncClient(timeout=15) as client:
            # Step 1: Get hotel IDs for city
            hotels_resp = await client.get(
                f"{AMADEUS_BASE_URL}/v1/reference-data/locations/hotels/by-city",
                headers={"Authorization": f"Bearer {token}"},
                params={"cityCode": city_code, "radius": 5, "radiusUnit": "KM"},
            )
            if hotels_resp.status_code != 200:
                return _mock_hotel_data(city_code, check_in, check_out, budget_per_night_inr)

            hotel_ids = [h["hotelId"] for h in hotels_resp.json().get("data", [])[:10]]
            if not hotel_ids:
                return _mock_hotel_data(city_code, check_in, check_out, budget_per_night_inr)

            # Step 2: Get offers for those hotels
            offers_resp = await client.get(
                f"{AMADEUS_BASE_URL}/v3/shopping/hotel-offers",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "hotelIds": ",".join(hotel_ids[:5]),
                    "checkInDate": check_in,
                    "checkOutDate": check_out,
                    "adults": adults,
                    "currencyCode": "INR",
                    "bestRateOnly": "true",
                },
            )
            if offers_resp.status_code != 200:
                return _mock_hotel_data(city_code, check_in, check_out, budget_per_night_inr)

            hotels = []
            for item in offers_resp.json().get("data", []):
                hotel = item.get("hotel", {})
                offer = item.get("offers", [{}])[0]
                price_per_night = float(offer.get("price", {}).get("base", 0)) / max(
                    (
                        datetime.strptime(check_out, "%Y-%m-%d")
                        - datetime.strptime(check_in, "%Y-%m-%d")
                    ).days,
                    1,
                )
                if budget_per_night_inr and price_per_night > budget_per_night_inr:
                    continue
                hotels.append({
                    "name": hotel.get("name", "Unknown Hotel"),
                    "rating": hotel.get("rating", "N/A"),
                    "address": hotel.get("address", {}).get("lines", [""])[0],
                    "price_per_night_inr": round(price_per_night, 2),
                    "total_inr": float(offer.get("price", {}).get("total", 0)),
                    "room_type": offer.get("room", {}).get("typeEstimated", {}).get("category", "STANDARD"),
                    "amenities": hotel.get("amenities", [])[:5],
                })

            from datetime import datetime
            return {
                "city": city_code,
                "check_in": check_in,
                "check_out": check_out,
                "hotels": sorted(hotels, key=lambda x: x["price_per_night_inr"]),
                "cheapest_per_night_inr": min([h["price_per_night_inr"] for h in hotels]) if hotels else None,
            }
    except Exception:
        return _mock_hotel_data(city_code, check_in, check_out, budget_per_night_inr)


def _mock_hotel_data(city: str, check_in: str, check_out: str, budget: Optional[float]) -> dict:
    city_hotels = {
        "GOI": [
            {"name": "Taj Exotica Resort & Spa", "rating": "5", "price_per_night_inr": 12500},
            {"name": "Alila Diwa Goa", "rating": "5", "price_per_night_inr": 8900},
            {"name": "Country Inn Goa", "rating": "3", "price_per_night_inr": 3200},
        ],
        "DEL": [
            {"name": "The Imperial New Delhi", "rating": "5", "price_per_night_inr": 18000},
            {"name": "Connaught Hotel", "rating": "3", "price_per_night_inr": 4500},
        ],
        "PAR": [
            {"name": "Hotel Le Marais", "rating": "4", "price_per_night_inr": 11000},
            {"name": "Hôtel de Crillon", "rating": "5", "price_per_night_inr": 42000},
        ],
    }
    hotels_raw = city_hotels.get(city, [
        {"name": f"{city} Grand Hotel", "rating": "4", "price_per_night_inr": 5000},
        {"name": f"{city} Budget Inn", "rating": "3", "price_per_night_inr": 2500},
    ])
    hotels = [
        {**h, "room_type": "STANDARD", "amenities": ["WiFi", "Pool", "Breakfast"],
         "total_inr": h["price_per_night_inr"] * 5}
        for h in hotels_raw if not budget or h["price_per_night_inr"] <= budget
    ]
    return {
        "city": city,
        "check_in": check_in,
        "check_out": check_out,
        "hotels": hotels,
        "cheapest_per_night_inr": min([h["price_per_night_inr"] for h in hotels]) if hotels else None,
        "note": "Demo data — add Amadeus API key for live prices",
    }
