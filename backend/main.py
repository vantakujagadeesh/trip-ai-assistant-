"""
Roam AI — FastAPI Backend
Endpoints: /chat, /itinerary/email, /alerts/subscribe, /health
"""
import os
import json
import logging
from pathlib import Path
from datetime import date
from typing import Any, Literal, Optional
from uuid import UUID
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from dotenv import load_dotenv

load_dotenv()

# ── Import agent & tools ──────────────────────────────────────────────────────
import sys
sys.path.insert(0, str(Path(__file__).parent))

from graph.agent import run_agent
from n8n.webhooks import trigger_email_itinerary, trigger_price_alert
from persistence import get_access_token, get_authenticated_user, public_supabase_config, supabase_rest


logger = logging.getLogger(__name__)


# ── App lifespan ──────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Roam AI backend starting up...")
    print(f"   Gemini API: {'✅ configured' if os.getenv('GEMINI_API_KEY') else '⚠️  not configured (add to .env)'}")
    print(f"   Amadeus API: {'✅ configured' if os.getenv('AMADEUS_API_KEY') else '⚠️  using demo data'}")
    print(f"   n8n Email: {'✅ configured' if os.getenv('N8N_EMAIL_WEBHOOK_URL') else '⚠️  not configured'}")
    yield
    print("🛑 Roam AI backend shutting down")


# ── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Roam AI Travel Assistant API",
    description="RAG + MCP + LangGraph powered travel planning API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


# ── Pydantic Models ───────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: Optional[str] = None
    ai_data_consent: bool = False


class TripCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    destination: str = Field(min_length=1, max_length=120)
    days: int = Field(ge=1, le=90)
    dates: dict[str, Any] = Field(default_factory=dict)
    estimated_cost_inr: float | None = Field(default=None, ge=0, le=1_000_000_000)
    itinerary: dict[str, Any]

    @field_validator("title", "destination")
    @classmethod
    def require_nonempty_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value

    @field_validator("itinerary")
    @classmethod
    def limit_itinerary_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > 100_000:
            raise ValueError("The itinerary is too large to save.")
        return value


class BookingRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trip_id: UUID
    service_type: Literal["flight", "hotel", "train", "bus", "cab", "other"]
    provider: str | None = Field(default=None, max_length=120)
    travel_date: date | None = None
    contact_name: str = Field(min_length=1, max_length=120)
    contact_phone: str | None = Field(default=None, max_length=30)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("contact_name")
    @classmethod
    def require_contact_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A contact name is required.")
        return value

    @field_validator("provider", "contact_phone", "notes")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class BookingRequestStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["requested", "contacted", "confirmed", "cancelled"]


class EmailItineraryRequest(BaseModel):
    email: str
    user_name: str = "Traveler"
    itinerary: dict


class PriceAlertRequest(BaseModel):
    email: str
    origin: str
    destination: str
    target_price_inr: float
    travel_date: str


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    supabase_config = public_supabase_config()
    return {
        "status": "ok",
        "service": "Roam AI Travel Assistant",
        "version": "1.0.0",
        "apis": {
            "gemini": bool(os.getenv("GEMINI_API_KEY")),
            "amadeus": bool(os.getenv("AMADEUS_API_KEY")),
            "n8n_email": bool(os.getenv("N8N_EMAIL_WEBHOOK_URL")),
            "supabase": supabase_config["supabase_configured"],
        },
    }


@app.get("/config")
async def public_config():
    return public_supabase_config()


@app.post("/trips", status_code=status.HTTP_201_CREATED)
async def save_trip(
    request: TripCreate,
    user: dict[str, Any] = Depends(get_authenticated_user),
    token: str = Depends(get_access_token),
):
    payload = request.model_dump()
    payload["user_id"] = user["id"]
    saved = await supabase_rest(
        "POST",
        "trips",
        token,
        payload=payload,
        prefer="return=representation",
    )
    if not saved:
        raise HTTPException(status_code=502, detail="Trip storage did not confirm the save.")
    return saved[0]


@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Main AI chat endpoint.
    Runs RAG retrieval → intent parsing → MCP tools → Gemini LLM synthesis.
    Returns streaming Server-Sent Events for real-time UI updates.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    async def generate():
        try:
            # Stream tool status updates first
            yield f"data: {json.dumps({'type': 'status', 'message': '🔍 Processing your request...'})}\n\n"

            result = await run_agent(
                request.message,
                ai_data_consent=request.ai_data_consent,
            )

            # Stream tool activity updates
            for status in result.get("tool_status", []):
                yield f"data: {json.dumps({'type': 'status', 'message': status})}\n\n"

            # Stream the final response
            yield f"data: {json.dumps({'type': 'response', 'message': result['response']})}\n\n"

            # Stream the structured itinerary if available
            if result.get("itinerary"):
                yield f"data: {json.dumps({'type': 'itinerary', 'data': result['itinerary']})}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception:
            logger.exception("Chat generation failed")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Trip generation failed. Please try again.'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/trips")
async def list_trips(
    user: dict[str, Any] = Depends(get_authenticated_user),
    token: str = Depends(get_access_token),
):
    return await supabase_rest(
        "GET",
        "trips",
        token,
        params={
            "select": "id,title,destination,days,dates,estimated_cost_inr,itinerary,created_at",
            "user_id": f"eq.{user['id']}",
            "order": "created_at.desc",
            "limit": "50",
        },
    )


@app.delete("/trips/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trip(
    trip_id: UUID,
    user: dict[str, Any] = Depends(get_authenticated_user),
    token: str = Depends(get_access_token),
):
    deleted = await supabase_rest(
        "DELETE",
        "trips",
        token,
        params={"id": f"eq.{trip_id}", "user_id": f"eq.{user['id']}", "select": "id"},
        prefer="return=representation",
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Trip not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/booking-requests", status_code=status.HTTP_201_CREATED)
async def create_booking_request(
    request: BookingRequestCreate,
    user: dict[str, Any] = Depends(get_authenticated_user),
    token: str = Depends(get_access_token),
):
    if not user.get("email"):
        raise HTTPException(status_code=422, detail="An email address is required for booking requests.")

    trip = await supabase_rest(
        "GET",
        "trips",
        token,
        params={
            "select": "id,title,destination",
            "id": f"eq.{request.trip_id}",
            "user_id": f"eq.{user['id']}",
            "limit": "1",
        },
    )
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found.")

    payload = request.model_dump(mode="json", exclude={"trip_id"})
    payload.update({
        "trip_id": str(request.trip_id),
        "user_id": user["id"],
    })
    created = await supabase_rest(
        "POST",
        "booking_requests",
        token,
        payload=payload,
        prefer="return=representation",
    )
    if not created:
        raise HTTPException(status_code=502, detail="Trip storage did not confirm the booking request.")
    return created[0]


@app.get("/booking-requests")
async def list_booking_requests(
    user: dict[str, Any] = Depends(get_authenticated_user),
    token: str = Depends(get_access_token),
):
    return await supabase_rest(
        "GET",
        "booking_requests",
        token,
        params={
            "select": "id,trip_id,trip_title,destination,service_type,provider,travel_date,contact_name,status,created_at,updated_at",
            "user_id": f"eq.{user['id']}",
            "order": "created_at.desc",
            "limit": "100",
        },
    )


def require_admin(user: dict[str, Any] = Depends(get_authenticated_user)) -> dict[str, Any]:
    if (user.get("app_metadata") or {}).get("role") != "admin":
        raise HTTPException(status_code=403, detail="Administrator access is required.")
    return user


@app.get("/admin/booking-requests")
async def list_all_booking_requests(
    _: dict[str, Any] = Depends(require_admin),
    token: str = Depends(get_access_token),
):
    return await supabase_rest(
        "GET",
        "booking_requests",
        token,
        params={
            "select": "id,trip_id,trip_title,destination,service_type,provider,travel_date,contact_name,contact_phone,requester_email,notes,status,created_at,updated_at",
            "order": "created_at.desc",
            "limit": "100",
        },
    )


@app.patch("/admin/booking-requests/{request_id}")
async def update_booking_request_status(
    request_id: UUID,
    request: BookingRequestStatusUpdate,
    _: dict[str, Any] = Depends(require_admin),
    token: str = Depends(get_access_token),
):
    updated = await supabase_rest(
        "PATCH",
        "booking_requests",
        token,
        params={"id": f"eq.{request_id}", "select": "id,status,updated_at"},
        payload={"status": request.status},
        prefer="return=representation",
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Booking request not found.")
    return updated[0]


@app.post("/itinerary/email")
async def send_itinerary_email(request: EmailItineraryRequest):
    """Trigger n8n workflow to email the itinerary as formatted HTML."""
    result = await trigger_email_itinerary(
        email=request.email,
        user_name=request.user_name,
        itinerary=request.itinerary,
    )
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])
    return result


@app.post("/alerts/subscribe")
async def subscribe_price_alert(request: PriceAlertRequest):
    """Trigger n8n workflow to set a flight price-drop alert."""
    result = await trigger_price_alert(
        email=request.email,
        origin=request.origin,
        destination=request.destination,
        target_price_inr=request.target_price_inr,
        travel_date=request.travel_date,
    )
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])
    return result


@app.get("/")
async def root():
    return {
        "message": "Roam AI Travel Assistant API is live 🌍",
        "docs": "/docs",
        "endpoints": {
            "chat": "POST /chat",
            "email_itinerary": "POST /itinerary/email",
            "price_alert": "POST /alerts/subscribe",
            "health": "GET /health",
        },
    }
