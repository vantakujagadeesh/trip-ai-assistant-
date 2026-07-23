"""
n8n Webhook Triggers
Fires n8n cloud workflows for post-itinerary automation:
  - Email itinerary delivery
  - Price drop alerts
"""
import os
import httpx
from typing import Optional


N8N_EMAIL_URL = os.getenv("N8N_EMAIL_WEBHOOK_URL", "")
N8N_PRICE_ALERT_URL = os.getenv("N8N_PRICE_ALERT_WEBHOOK_URL", "")


async def trigger_email_itinerary(
    email: str,
    user_name: str,
    itinerary: dict,
) -> dict:
    """
    Trigger n8n workflow to send itinerary email.
    n8n workflow should: receive JSON → format HTML email → send via Gmail.
    """
    if not N8N_EMAIL_URL:
        return {"success": False, "message": "n8n webhook not configured — add N8N_EMAIL_WEBHOOK_URL to .env"}

    payload = {
        "email": email,
        "name": user_name,
        "destination": itinerary.get("destination", ""),
        "days": itinerary.get("days", 0),
        "dates": itinerary.get("dates", {}),
        "estimated_cost_inr": itinerary.get("estimated_cost_inr"),
        "recommended_flight": itinerary.get("recommended_flight"),
        "recommended_hotel": itinerary.get("recommended_hotel"),
        "day_plan": itinerary.get("day_plan", []),
        "top_places": itinerary.get("top_places", [])[:5],
        "weather_summary": itinerary.get("weather_summary", ""),
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(N8N_EMAIL_URL, json=payload)
            if resp.status_code in (200, 201):
                return {"success": True, "message": f"Itinerary sent to {email} successfully!"}
            return {"success": False, "message": f"n8n returned status {resp.status_code}"}
    except Exception as e:
        return {"success": False, "message": f"Failed to trigger n8n: {str(e)[:100]}"}


async def trigger_price_alert(
    email: str,
    origin: str,
    destination: str,
    target_price_inr: float,
    travel_date: str,
) -> dict:
    """
    Trigger n8n workflow to set a price-drop alert.
    n8n workflow should: poll Amadeus API on schedule → compare price → email user when price drops.
    """
    if not N8N_PRICE_ALERT_URL:
        return {"success": False, "message": "n8n webhook not configured — add N8N_PRICE_ALERT_WEBHOOK_URL to .env"}

    payload = {
        "email": email,
        "origin": origin,
        "destination": destination,
        "target_price_inr": target_price_inr,
        "travel_date": travel_date,
        "check_interval_hours": 6,
        "alert_active": True,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(N8N_PRICE_ALERT_URL, json=payload)
            if resp.status_code in (200, 201):
                return {
                    "success": True,
                    "message": f"Price alert set! We'll email {email} when {origin}→{destination} drops below ₹{target_price_inr:,.0f}",
                }
            return {"success": False, "message": f"n8n returned {resp.status_code}"}
    except Exception as e:
        return {"success": False, "message": f"Failed to set price alert: {str(e)[:100]}"}
