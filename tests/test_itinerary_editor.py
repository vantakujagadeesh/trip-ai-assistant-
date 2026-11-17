import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from backend import main
from mcp_tools.itinerary import _build_weather_adaptive_day_plan, regenerate_itinerary_day


def sample_itinerary():
    return {
        "destination": "Jaipur",
        "days": 3,
        "dates": {"start": "2026-12-01", "end": "2026-12-03"},
        "top_places": [
            {"name": "City Museum", "description": "Indoor collection.", "source": "OpenTripMap"},
            {"name": "Amber Fort", "description": "Historic fort.", "source": "OpenTripMap"},
        ],
        "provider_status": {
            "places": {"status": "live_catalog", "checked_at": "2026-11-17T10:00:00Z"},
        },
        "day_plan": [
            {"day": 1, "activities": [{"id": "d1-a1", "type": "attraction", "title": "Hawa Mahal"}]},
            {
                "day": 2,
                "is_rainy": True,
                "activities": [
                    {"id": "d2-locked", "type": "attraction", "title": "Favorite stop", "locked": True},
                    {"id": "d2-food", "type": "food", "title": "Lunch break"},
                    {"id": "d2-old", "type": "attraction", "title": "Old suggestion"},
                ],
            },
            {"day": 3, "activities": [{"id": "d3-a1", "type": "attraction", "title": "City Palace"}]},
        ],
    }


class ItineraryEditorTests(unittest.TestCase):
    def test_pace_changes_activity_count_and_traveler_notes(self):
        places = [{"name": f"Place {index}", "description": "A listed place."} for index in range(6)]
        common = {
            "days": 3,
            "start_date": "2026-12-01",
            "places": places,
            "meals": {},
            "weather": [],
            "destination": "Jaipur",
            "cab_rental": {},
        }

        relaxed = _build_weather_adaptive_day_plan(
            **common,
            traveler_preferences={
                "pace": "relaxed",
                "traveling_with_kids": True,
            },
        )
        packed = _build_weather_adaptive_day_plan(
            **common,
            traveler_preferences={"pace": "packed"},
        )

        relaxed_stops = [
            activity for activity in relaxed[1]["activities"]
            if activity["type"] == "attraction"
        ]
        packed_stops = [
            activity for activity in packed[1]["activities"]
            if activity["type"] == "attraction"
        ]
        self.assertEqual(len(relaxed_stops), 1)
        self.assertEqual(len(packed_stops), 3)
        self.assertTrue(any("children" in note for note in relaxed[1]["traveler_notes"]))

    def test_relaxed_replan_changes_only_target_day_and_keeps_locked_items(self):
        itinerary = sample_itinerary()
        original_first = itinerary["day_plan"][0].copy()
        original_last = itinerary["day_plan"][2].copy()

        updated = regenerate_itinerary_day(
            itinerary,
            2,
            traveler_preferences={"pace": "balanced"},
            instruction="Make day 2 more relaxed",
        )

        self.assertEqual(updated["day_plan"][0], original_first)
        self.assertEqual(updated["day_plan"][2], original_last)
        self.assertEqual(updated["day_plan"][1]["pace"], "relaxed")
        activities = updated["day_plan"][1]["activities"]
        self.assertTrue(any(activity["id"] == "d2-locked" for activity in activities))
        self.assertTrue(any(activity["id"] == "d2-food" for activity in activities))
        self.assertFalse(any(activity.get("title") == "Old suggestion" for activity in activities))
        self.assertEqual(itinerary["day_plan"][1]["activities"][2]["title"], "Old suggestion")

    def test_rainy_replan_prefers_listed_indoor_places(self):
        itinerary = sample_itinerary()
        itinerary["day_plan"][1]["activities"] = [
            {"id": "d2-food", "type": "food", "title": "Lunch break"},
            {"id": "d2-old", "type": "attraction", "title": "Old suggestion"},
        ]
        updated = regenerate_itinerary_day(itinerary, 2, {"pace": "relaxed"})

        titles = [activity["title"] for activity in updated["day_plan"][1]["activities"]]
        self.assertIn("City Museum", titles)
        self.assertNotIn("Amber Fort", titles)

    def test_replan_rejects_day_not_in_itinerary(self):
        with self.assertRaises(ValueError):
            regenerate_itinerary_day(sample_itinerary(), 9)

    def test_replan_uses_transparent_flexible_time_when_no_places_remain(self):
        itinerary = sample_itinerary()
        itinerary["top_places"] = []
        itinerary["day_plan"][1]["activities"] = []

        updated = regenerate_itinerary_day(itinerary, 2)

        activity = updated["day_plan"][1]["activities"][0]
        self.assertEqual(activity["type"], "free_time")
        self.assertEqual(activity["source_label"], "Estimate")
        self.assertIsNone(activity["cost_inr"])

    def test_regeneration_api_returns_updated_itinerary(self):
        response = TestClient(main.app).post(
            "/itinerary/regenerate-day",
            json={
                "itinerary": sample_itinerary(),
                "day": 2,
                "instruction": "Make day 2 relaxed",
                "traveler_preferences": {"pace": "balanced"},
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["day"], 2)
        self.assertEqual(response.json()["itinerary"]["day_plan"][1]["pace"], "relaxed")

    def test_chat_forwards_validated_traveler_preferences(self):
        with patch(
            "backend.main.run_agent",
            new_callable=AsyncMock,
            return_value={"response": "Trip ready.", "tool_status": [], "itinerary": None},
        ) as run_agent:
            response = TestClient(main.app).post(
                "/chat",
                json={
                    "message": "Plan a trip to Jaipur",
                    "traveler_preferences": {
                        "pace": "relaxed",
                        "interests": ["culture"],
                        "food_preferences": ["vegetarian"],
                        "traveling_with_kids": True,
                        "traveling_with_seniors": False,
                    },
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn('"type": "response"', response.text)
        self.assertEqual(
            run_agent.await_args.kwargs["traveler_preferences"]["pace"],
            "relaxed",
        )


if __name__ == "__main__":
    unittest.main()
