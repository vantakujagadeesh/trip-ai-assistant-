"""
Roam AI — FastAPI Backend
Endpoints: /chat, /itinerary/email, /alerts/subscribe, /health
"""
import os
import json
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ── Import agent & tools ──────────────────────────────────────────────────────
import sys
sys.path.insert(0, str(Path(__file__).parent))

from graph.agent import run_agent
from n8n.webhooks import trigger_email_itinerary, trigger_price_alert


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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic Models ───────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


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
    return {
        "status": "ok",
        "service": "Roam AI Travel Assistant",
        "version": "1.0.0",
        "apis": {
            "gemini": bool(os.getenv("GEMINI_API_KEY")),
            "amadeus": bool(os.getenv("AMADEUS_API_KEY")),
            "n8n_email": bool(os.getenv("N8N_EMAIL_WEBHOOK_URL")),
        },
    }


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

            result = await run_agent(request.message)

            # Stream tool activity updates
            for status in result.get("tool_status", []):
                yield f"data: {json.dumps({'type': 'status', 'message': status})}\n\n"

            # Stream the final response
            yield f"data: {json.dumps({'type': 'response', 'message': result['response']})}\n\n"

            # Stream the structured itinerary if available
            if result.get("itinerary"):
                yield f"data: {json.dumps({'type': 'itinerary', 'data': result['itinerary']})}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


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
