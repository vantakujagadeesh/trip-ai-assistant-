import os
import sys
import unittest
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from mcp_tools.buses import search_buses
from mcp_tools.flights import search_flights
from mcp_tools.hotels import search_hotels
from mcp_tools.itinerary import (
    _attach_nearby_places,
    _build_transport_and_route_advice,
    _build_weather_adaptive_day_plan,
    build_itinerary,
)
from mcp_tools.places import get_places
from mcp_tools.trains import search_trains
from graph.agent import _smart_parse_intent


class LiveProviderTruthfulnessTests(unittest.IsolatedAsyncioTestCase):
    def test_intent_parser_does_not_assume_goa_or_departure_city(self):
        unspecified = _smart_parse_intent("Plan a 5-day trip")
        goa_trip = _smart_parse_intent("Plan a 5-day trip to Goa from Mumbai")

        self.assertIsNone(unspecified["destination"])
        self.assertIsNone(unspecified["origin"])
        self.assertEqual(goa_trip["destination"], "Goa")
        self.assertEqual(goa_trip["origin"], "Mumbai")

    def test_intent_parser_captures_explicit_iso_trip_date(self):
        intent = _smart_parse_intent("Plan a trip to Paris on 2026-12-01")

        self.assertEqual(intent["start_date"], "2026-12-01")

    def test_structured_trip_prompt_preserves_all_requested_details(self):
        intent = _smart_parse_intent(
            "Plan a 4-day trip to Jaipur from Delhi, starting 2026-12-10 "
            "for 3 people under ₹45000 Interests or requirements: heritage and food"
        )

        self.assertEqual(intent["destination"], "Jaipur")
        self.assertEqual(intent["origin"], "Delhi")
        self.assertEqual(intent["start_date"], "2026-12-10")
        self.assertEqual(intent["days"], 4)
        self.assertEqual(intent["guests"], 3)
        self.assertEqual(intent["budget_inr"], 45000)
        self.assertEqual(intent["preferences"][0], "cultural")

    async def test_live_place_catalog_keeps_provider_coordinates_for_map(self):
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json=[{
                    "name": "Example Place",
                    "kinds": "historic,architecture",
                    "point": {"lat": 26.9124, "lon": 75.7873},
                }],
            )
        )
        client = httpx.AsyncClient(transport=transport)
        with patch.dict(os.environ, {"OPENTRIPMAP_API_KEY": "test-key"}):
            with patch(
                "mcp_tools.places.resolve_location",
                new_callable=AsyncMock,
                return_value={"latitude": 26.9124, "longitude": 75.7873},
            ), patch("mcp_tools.places.httpx.AsyncClient", return_value=client):
                result = await get_places("Jaipur", "attractions")

        self.assertEqual(result["status"], "live_catalog")
        self.assertEqual(result["places"][0]["latitude"], 26.9124)
        self.assertEqual(result["places"][0]["longitude"], 75.7873)

    async def test_live_flight_offer_exposes_provider_seats_without_booking(self):
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "data": [{
                        "id": "offer-1",
                        "numberOfBookableSeats": 3,
                        "price": {"total": "5400"},
                        "itineraries": [{
                            "duration": "PT2H",
                            "segments": [{
                                "carrierCode": "AI",
                                "departure": {"at": "2026-12-01T10:00:00"},
                                "arrival": {"at": "2026-12-01T12:00:00"},
                            }],
                        }],
                    }],
                },
            )
        )
        client = httpx.AsyncClient(transport=transport)
        with patch.dict(os.environ, {"AMADEUS_API_KEY": "test-key", "AMADEUS_API_SECRET": "test-secret"}):
            with patch("mcp_tools.flights.AMADEUS_BASE_URL", "https://api.amadeus.com"), patch(
                "mcp_tools.flights._get_amadeus_token",
                new_callable=AsyncMock,
                return_value="token",
            ), patch("mcp_tools.flights.httpx.AsyncClient", return_value=client):
                result = await search_flights("DEL", "JAI", "2026-12-01")

        self.assertEqual(result["status"], "live")
        self.assertEqual(result["offers"][0]["bookable_seats"], 3)
        self.assertEqual(result["offers"][0]["booking_status"], "not_booked")

    async def test_live_hotel_offer_keeps_coordinates_and_never_invents_room_count(self):
        def respond(request):
            if request.url.path.endswith("/by-city"):
                return httpx.Response(
                    200,
                    json={"data": [{
                        "hotelId": "hotel-1",
                        "name": "Provider Hotel",
                        "geoCode": {"latitude": 26.9124, "longitude": 75.7873},
                    }]},
                )
            return httpx.Response(
                200,
                json={"data": [{
                    "hotel": {
                        "hotelId": "hotel-1",
                        "name": "Provider Hotel",
                        "rating": "4",
                        "address": {"lines": ["Pink City"]},
                    },
                    "offers": [{
                        "id": "hotel-offer-1",
                        "price": {"total": "6000", "currency": "INR"},
                        "room": {"typeEstimated": {"category": "STANDARD"}},
                    }],
                }]},
            )

        client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        with patch.dict(os.environ, {"AMADEUS_API_KEY": "test-key", "AMADEUS_API_SECRET": "test-secret"}):
            with patch("mcp_tools.hotels.AMADEUS_BASE_URL", "https://api.amadeus.com"), patch(
                "mcp_tools.hotels._get_amadeus_token",
                new_callable=AsyncMock,
                return_value="token",
            ), patch("mcp_tools.hotels.httpx.AsyncClient", return_value=client):
                result = await search_hotels("JAI", "2026-12-01", "2026-12-03")

        hotel = result["hotels"][0]
        self.assertEqual(result["status"], "live")
        self.assertEqual((hotel["latitude"], hotel["longitude"]), (26.9124, 75.7873))
        self.assertEqual(hotel["offer_id"], "hotel-offer-1")
        self.assertIsNone(hotel["rooms_available"])
        self.assertEqual(hotel["booking_status"], "not_booked")

    def test_hotels_report_nearby_places_only_when_both_have_coordinates(self):
        hotels = [{"name": "Hotel", "latitude": 26.9124, "longitude": 75.7873}]
        places = [
            {"name": "Nearby landmark", "latitude": 26.9224, "longitude": 75.7873},
            {"name": "Unlocated suggestion"},
        ]

        enriched = _attach_nearby_places(hotels, places)

        self.assertEqual(enriched[0]["nearby_places"][0]["name"], "Nearby landmark")
        self.assertAlmostEqual(enriched[0]["nearby_places"][0]["distance_km"], 1.1, places=1)

    def test_transport_comparison_does_not_invent_missing_live_prices(self):
        options, recommendation = _build_transport_and_route_advice(
            origin="Delhi",
            destination="Jaipur",
            flight_data={},
            train_data={"availability_checked": True, "trains": [{"train_name": "Provider train"}]},
            bus_data={"availability_checked": True, "buses": [{"operator": "Provider bus"}]},
            cab_data={"availability_checked": True, "outstation_cabs": [{"category": "Sedan"}]},
            guests=2,
            budget_inr=None,
        )

        self.assertEqual(options, [])
        self.assertEqual(recommendation["best_mode"], "No live route quote available")

    async def test_train_search_does_not_invent_schedules_or_availability(self):
        result = await search_trains("Delhi", "Jaipur", "2026-12-01")

        self.assertEqual(result["status"], "not_integrated")
        self.assertFalse(result["availability_checked"])
        self.assertEqual(result["trains"], [])
        self.assertIsNone(result["cheapest_fare_inr"])
        self.assertIn("irctc.co.in", result["booking_portal"])

    async def test_bus_search_does_not_invent_fares_or_seat_counts(self):
        result = await search_buses("Delhi", "Jaipur", "2026-12-01")

        self.assertEqual(result["status"], "not_integrated")
        self.assertFalse(result["availability_checked"])
        self.assertEqual(result["buses"], [])
        self.assertIsNone(result["cheapest_fare_inr"])
        self.assertIn("redbus.in", result["booking_portal"])

    async def test_invalid_travel_dates_are_reported(self):
        train_result = await search_trains("Delhi", "Jaipur", "not-a-date")
        bus_result = await search_buses("Delhi", "Jaipur", "not-a-date")

        self.assertEqual(train_result["status"], "invalid_date")
        self.assertEqual(bus_result["status"], "invalid_date")

    def test_day_plan_does_not_invent_places_meals_or_weather(self):
        plan = _build_weather_adaptive_day_plan(
            days=1,
            start_date="2026-12-01",
            places=[],
            meals={"breakfast": [], "lunch": [], "dinner": []},
            weather=[],
            destination="Unknown City",
            cab_rental={},
        )

        day = plan[0]
        self.assertEqual(day["weather_status"], "unavailable")
        self.assertIsNone(day["is_rainy"])
        self.assertTrue(any(activity["title"] == "Flexible time" for activity in day["activities"]))
        self.assertTrue(all("suggestion:" not in activity["title"] for activity in day["activities"]))
        self.assertFalse(any("Museum" in activity["title"] for activity in day["activities"]))

    async def test_itinerary_hides_sandbox_quotes_and_reports_provider_status(self):
        flight_result = {
            "offers": [{"airline": "Test Airline", "price_inr": 1000}],
            "status": "sandbox",
            "source": "Amadeus",
            "live_quotes": False,
        }
        hotel_result = {
            "hotels": [{"name": "Test Hotel", "price_per_night_inr": 1000}],
            "status": "sandbox",
            "source": "Amadeus",
            "live_inventory": False,
        }
        with ExitStack() as stack:
            stack.enter_context(patch("mcp_tools.itinerary.search_flights", new_callable=AsyncMock, return_value=flight_result))
            stack.enter_context(patch("mcp_tools.itinerary.search_hotels", new_callable=AsyncMock, return_value=hotel_result))
            stack.enter_context(patch("mcp_tools.itinerary.get_weather", new_callable=AsyncMock, return_value={"status": "out_of_range", "source": "Open-Meteo", "forecast": [], "summary": ""}))
            stack.enter_context(patch("mcp_tools.itinerary.get_places", new_callable=AsyncMock, return_value={"status": "curated", "source": "curated", "places": []}))
            stack.enter_context(patch("mcp_tools.itinerary.search_trains", new_callable=AsyncMock, return_value={"status": "not_integrated", "trains": []}))
            stack.enter_context(patch("mcp_tools.itinerary.search_buses", new_callable=AsyncMock, return_value={"status": "not_integrated", "buses": []}))
            stack.enter_context(patch("mcp_tools.itinerary.get_cab_and_rental_options", new_callable=AsyncMock, return_value={"status": "not_integrated", "outstation_cabs": [], "self_drive_rentals": []}))
            stack.enter_context(patch("mcp_tools.itinerary.get_3_meals", new_callable=AsyncMock, return_value={"status": "not_configured", "breakfast": [], "lunch": [], "dinner": []}))
            stack.enter_context(patch("mcp_tools.itinerary.get_live_conditions", new_callable=AsyncMock, return_value={"status": "provider_error", "source": "Open-Meteo", "current_weather": {}, "road_conditions": {"risk_level": "UNKNOWN"}}))
            result = await build_itinerary(
                destination="Jaipur",
                origin="Delhi",
                days=2,
                start_date="2026-12-01",
            )

        self.assertEqual(result["provider_status"]["flights"]["status"], "sandbox")
        self.assertEqual(result["provider_status"]["hotels"]["status"], "sandbox")
        self.assertEqual(result["all_flights"], [])
        self.assertEqual(result["all_hotels"], [])
        self.assertEqual(result["transport_comparison"], [])
        self.assertIsNone(result["estimated_cost_inr"])
        self.assertEqual(result["day_plan"][0]["weather_status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
