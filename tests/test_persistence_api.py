import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from backend import main


USER_ID = "2a2a12f3-4f4f-4f4f-8f4f-2a2a12f34f4f"
TRIP_ID = "a2a212f3-4f4f-4f4f-8f4f-2a2a12f34f4f"


class PersistenceApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        main.app.dependency_overrides[main.get_authenticated_user] = lambda: {
            "id": USER_ID,
            "email": "traveler@example.com",
            "app_metadata": {},
        }
        main.app.dependency_overrides[main.get_access_token] = lambda: "test-access-token"

    def tearDown(self):
        main.app.dependency_overrides.clear()

    def test_trip_creation_sets_owner_from_authenticated_user(self):
        saved = {
            "id": TRIP_ID,
            "user_id": USER_ID,
            "destination": "Jaipur",
        }
        with patch("backend.main.supabase_rest", new_callable=AsyncMock, return_value=[saved]) as rest:
            response = self.client.post(
                "/trips",
                json={
                    "title": "Jaipur trip",
                    "destination": "Jaipur",
                    "days": 3,
                    "dates": {},
                    "estimated_cost_inr": 25000,
                    "itinerary": {"destination": "Jaipur"},
                },
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["id"], TRIP_ID)
        self.assertEqual(rest.await_args.kwargs["payload"]["user_id"], USER_ID)

    def test_trip_update_is_scoped_to_authenticated_owner(self):
        updated = {"id": TRIP_ID, "days": 2, "itinerary": {"day_plan": []}}
        with patch(
            "backend.main.supabase_rest",
            new_callable=AsyncMock,
            return_value=[updated],
        ) as rest:
            response = self.client.patch(
                f"/trips/{TRIP_ID}",
                json={
                    "days": 2,
                    "dates": {"start": "2026-12-01", "end": "2026-12-02"},
                    "estimated_cost_inr": None,
                    "itinerary": {"day_plan": []},
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(rest.await_args.kwargs["params"]["user_id"], f"eq.{USER_ID}")
        self.assertEqual(rest.await_args.kwargs["payload"]["days"], 2)

    def test_booking_request_uses_owned_trip_and_verified_account_email(self):
        trip = {"id": TRIP_ID, "title": "Jaipur trip", "destination": "Jaipur"}
        booking = {"id": "booking-1", "status": "requested"}
        with patch(
            "backend.main.supabase_rest",
            new_callable=AsyncMock,
            side_effect=[[trip], [booking]],
        ) as rest:
            response = self.client.post(
                "/booking-requests",
                json={
                    "trip_id": TRIP_ID,
                    "service_type": "hotel",
                    "provider": "Example Hotel",
                    "contact_name": "Traveler",
                    "notes": "Two guests",
                },
            )

        self.assertEqual(response.status_code, 201)
        insert_payload = rest.await_args_list[1].kwargs["payload"]
        self.assertEqual(insert_payload["user_id"], USER_ID)
        self.assertNotIn("requester_email", insert_payload)
        self.assertNotIn("status", insert_payload)

    def test_clients_cannot_choose_trip_owner(self):
        response = self.client.post(
            "/trips",
            json={
                "title": "Jaipur trip",
                "destination": "Jaipur",
                "days": 3,
                "itinerary": {"destination": "Jaipur"},
                "user_id": "someone-else",
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_booking_status_changes_require_admin_role(self):
        response = self.client.get("/admin/booking-requests")
        self.assertEqual(response.status_code, 403)

    def test_admin_can_change_booking_status(self):
        main.app.dependency_overrides[main.get_authenticated_user] = lambda: {
            "id": USER_ID,
            "email": "admin@example.com",
            "app_metadata": {"role": "admin"},
        }
        with patch(
            "backend.main.supabase_rest",
            new_callable=AsyncMock,
            return_value=[{"id": "request-1", "status": "contacted"}],
        ):
            response = self.client.patch(
                f"/admin/booking-requests/{TRIP_ID}",
                json={"status": "contacted"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "contacted")

    def test_customer_cannot_set_booking_status(self):
        with patch("backend.main.supabase_rest", new_callable=AsyncMock) as rest:
            response = self.client.post(
                "/booking-requests",
                json={
                    "trip_id": TRIP_ID,
                    "service_type": "hotel",
                    "contact_name": "Traveler",
                    "status": "confirmed",
                },
            )

        self.assertEqual(response.status_code, 422)
        rest.assert_not_awaited()

    def test_booking_request_rejects_a_trip_the_user_cannot_read(self):
        with patch(
            "backend.main.supabase_rest",
            new_callable=AsyncMock,
            return_value=[],
        ) as rest:
            response = self.client.post(
                "/booking-requests",
                json={
                    "trip_id": TRIP_ID,
                    "service_type": "hotel",
                    "contact_name": "Traveler",
                },
            )

        self.assertEqual(response.status_code, 404)
        rest.assert_awaited_once()

    def test_trip_list_requires_a_bearer_token(self):
        main.app.dependency_overrides.clear()
        response = self.client.get("/trips")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
