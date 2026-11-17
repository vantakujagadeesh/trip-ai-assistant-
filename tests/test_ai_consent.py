import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from graph.agent import (  # noqa: E402
    _free_tier_model,
    _redact_direct_contact_details,
    intent_parser_node,
    llm_synthesis_node,
)
from backend import main  # noqa: E402


class GeminiConsentTests(unittest.IsolatedAsyncioTestCase):
    def test_free_model_configuration_rejects_paid_model_ids(self):
        with patch.dict(os.environ, {"GEMINI_MODEL": "gemini-4-carbon"}):
            self.assertEqual(
                _free_tier_model("GEMINI_MODEL", "gemini-4-hydrogen"),
                "gemini-4-hydrogen",
            )

    def test_contact_redaction_preserves_trip_dates_and_budget(self):
        message = (
            "Plan Goa on 2026-12-10, budget INR 30,000. "
            "Email jane@example.com or call +91 9876543210."
        )

        redacted = _redact_direct_contact_details(message)

        self.assertIn("2026-12-10", redacted)
        self.assertIn("30,000", redacted)
        self.assertNotIn("jane@example.com", redacted)
        self.assertNotIn("9876543210", redacted)

    async def test_unconsented_request_never_calls_gemini(self):
        initial = {
            "user_message": "What is a Vande Bharat train?",
            "tool_status": [],
            "ai_data_consent": False,
        }
        with patch("graph.agent._call_gemini") as gemini:
            parsed = await intent_parser_node(initial)
            result = await llm_synthesis_node({
                **initial,
                **parsed,
                "tool_results": {},
                "rag_context": "",
                "ai_data_consent": False,
            })

        gemini.assert_not_called()
        self.assertIn("couldn't answer", result["llm_response"])

    async def test_selected_interests_apply_even_when_gemini_parses_intent(self):
        state = {
            "user_message": "Plan a trip to Goa",
            "tool_status": [],
            "ai_data_consent": True,
            "traveler_preferences": {"interests": ["culture", "nature"]},
        }
        with patch(
            "graph.agent._call_gemini",
            return_value='{"destination":"Goa","days":3,"preferences":["attractions"]}',
        ):
            parsed = await intent_parser_node(state)

        self.assertEqual(
            parsed["parsed_intent"]["preferences"],
            ["cultural", "natural", "restaurants"],
        )

    async def test_consented_synthesis_sends_redacted_user_message(self):
        state = {
            "user_message": "Plan Goa on 2026-12-10. jane@example.com +91 9876543210",
            "parsed_intent": {"destination": "Goa", "days": 3, "guests": 2},
            "tool_results": {},
            "rag_context": "",
            "tool_status": [],
            "ai_data_consent": True,
        }
        with patch("graph.agent._genai_client", object()), patch(
            "graph.agent._call_gemini",
            return_value="A sufficiently detailed Gemini response for this test.",
        ) as gemini:
            result = await llm_synthesis_node(state)

        prompt = gemini.call_args.args[0]
        self.assertIn("2026-12-10", prompt)
        self.assertNotIn("jane@example.com", prompt)
        self.assertNotIn("9876543210", prompt)
        self.assertIn("Generated response with Gemini", result["tool_status"][-1])


class ChatConsentApiTests(unittest.TestCase):
    def test_consent_defaults_to_false(self):
        self.assertFalse(main.ChatRequest(message="Plan a trip to Goa").ai_data_consent)

    def test_explicit_consent_is_forwarded_to_agent(self):
        with patch(
            "backend.main.run_agent",
            new_callable=AsyncMock,
            return_value={"response": "ok", "tool_status": [], "itinerary": None},
        ) as run_agent:
            response = TestClient(main.app).post(
                "/chat",
                json={"message": "Plan a trip to Goa", "ai_data_consent": True},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(run_agent.await_args.kwargs["ai_data_consent"])


if __name__ == "__main__":
    unittest.main()
