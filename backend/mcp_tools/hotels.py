"""
MCP Tool: Hotel Search
Uses Amadeus Hotel API (free sandbox tier)
"""
import os
import httpx
from datetime import datetime, timezone
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
    unavailable = {
        "city": city_code,
        "check_in": check_in,
        "check_out": check_out,
        "hotels": [],
        "cheapest_per_night_inr": None,
        "source": "Amadeus",
        "live_inventory": False,
        "availability_checked": False,
    }
    if not os.getenv("AMADEUS_API_KEY") or not os.getenv("AMADEUS_API_SECRET"):
        return {**unavailable, "status": "not_configured", "note": "Live hotel search is not configured."}

    try:
        nights = (datetime.strptime(check_out, "%Y-%m-%d") - datetime.strptime(check_in, "%Y-%m-%d")).days
    except ValueError:
        return {**unavailable, "status": "invalid_dates", "note": "Hotel dates must use YYYY-MM-DD."}
    if nights < 1:
        return {**unavailable, "status": "invalid_dates", "note": "Check-out must be after check-in."}
    if len(city_code) != 3 or not city_code.isalpha():
        return {**unavailable, "status": "unsupported_location", "note": "A valid hotel city code is required."}

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
                return {**unavailable, "status": "provider_error", "note": "Hotel search provider did not return results."}

            hotel_catalog = {
                hotel["hotelId"]: hotel
                for hotel in hotels_resp.json().get("data", [])[:10]
                if hotel.get("hotelId")
            }
            hotel_ids = list(hotel_catalog)
            if not hotel_ids:
                return {**unavailable, "status": "no_results", "note": "No hotels were returned for this location."}

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
                return {**unavailable, "status": "provider_error", "note": "Hotel availability could not be checked."}

            hotels = []
            for item in offers_resp.json().get("data", []):
                hotel = item.get("hotel", {})
                hotel_id = hotel.get("hotelId")
                catalog_entry = hotel_catalog.get(hotel_id, {})
                offers = item.get("offers") or []
                if not offers:
                    continue
                offer = offers[0]
                total_price = float(offer.get("price", {}).get("total", 0))
                price_per_night = total_price / nights
                if budget_per_night_inr and price_per_night > budget_per_night_inr:
                    continue
                geo_code = hotel.get("geoCode") or catalog_entry.get("geoCode") or {}
                latitude = hotel.get("latitude", geo_code.get("latitude"))
                longitude = hotel.get("longitude", geo_code.get("longitude"))
                try:
                    latitude = float(latitude)
                    longitude = float(longitude)
                except (TypeError, ValueError):
                    latitude = longitude = None
                if (
                    latitude is None
                    or longitude is None
                    or not (-90 <= latitude <= 90)
                    or not (-180 <= longitude <= 180)
                ):
                    latitude = longitude = None
                hotels.append({
                    "hotel_id": hotel_id,
                    "offer_id": offer.get("id"),
                    "name": hotel.get("name") or catalog_entry.get("name", "Unknown Hotel"),
                    "rating": hotel.get("rating"),
                    "address": hotel.get("address", {}).get("lines", [""])[0],
                    "latitude": latitude,
                    "longitude": longitude,
                    "price_per_night_inr": round(price_per_night, 2),
                    "total_inr": total_price,
                    "room_type": offer.get("room", {}).get("typeEstimated", {}).get("category", "STANDARD"),
                    "amenities": hotel.get("amenities", [])[:5],
                    "currency": offer.get("price", {}).get("currency", "INR"),
                    "availability_status": "offer_found",
                    "rooms_available": None,
                    "room_availability_note": "The provider returned an offer but does not provide an exact remaining-room count.",
                    "booking_status": "not_booked",
                })

            is_sandbox = "test.api.amadeus.com" in AMADEUS_BASE_URL
            return {
                "city": city_code,
                "check_in": check_in,
                "check_out": check_out,
                "hotels": sorted(hotels, key=lambda x: x["price_per_night_inr"]),
                "cheapest_per_night_inr": min([h["price_per_night_inr"] for h in hotels]) if hotels else None,
                "status": "sandbox" if is_sandbox else ("live" if hotels else "no_results"),
                "source": "Amadeus",
                "live_inventory": not is_sandbox and bool(hotels),
                "availability_checked": not is_sandbox,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "note": "Sandbox results are test data and are not bookable." if is_sandbox else None,
            }
    except (httpx.HTTPError, ValueError, KeyError):
        return {**unavailable, "status": "provider_error", "note": "Hotel availability could not be checked."}
