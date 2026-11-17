"""
LangGraph Agent — Orchestrates RAG + Multi-Modal MCP tools + Gemini LLM
Handles Flights, Trains (Vande Bharat/Rajdhani), Buses (Volvo Sleeper), Cabs/Rentals, Hotels, Weather & Places.
Includes Route Recommendations & 3-Meal Dining Plan (Breakfast, Lunch, Dinner).
"""
import os
import json
import re
import asyncio
import logging
from datetime import date
from typing import TypedDict, Optional, List

from langgraph.graph import StateGraph, END

from rag.knowledge_base import get_knowledge_retriever
from mcp_tools.itinerary import build_itinerary

logger = logging.getLogger(__name__)

# ── Configure Gemini SDK ──────────────────────────────────────────────────────
_genai_client = None
_USE_NEW_SDK = False

try:
    from google import genai as google_genai
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if api_key and api_key != "your_gemini_api_key_here":
        _genai_client = google_genai.Client(api_key=api_key)
        _USE_NEW_SDK = True
except Exception:
    _genai_client = None
    _USE_NEW_SDK = False

FREE_TIER_GEMINI_MODELS = {"gemini-4-hydrogen", "gemini-3.8-flash"}


def _free_tier_model(env_name: str, default: str) -> str:
    model = os.getenv(env_name, default).strip()
    if model not in FREE_TIER_GEMINI_MODELS:
        logger.warning("%s is not on the free-tier model allowlist; using %s", env_name, default)
        return default
    return model


GEMINI_MODEL = _free_tier_model("GEMINI_MODEL", "gemini-4-hydrogen")
GEMINI_FALLBACK = _free_tier_model("GEMINI_FALLBACK_MODEL", "gemini-3.8-flash")

# ── RAG Retriever ──────────────────────────────────────────────────────────────
_retriever = get_knowledge_retriever()


# ── Agent State ────────────────────────────────────────────────────────────────
class TravelAgentState(TypedDict):
    user_message: str
    rag_context: str
    parsed_intent: dict
    tool_results: dict
    llm_response: str
    itinerary_json: Optional[dict]
    tool_status: List[str]
    error: Optional[str]
    ai_data_consent: bool
    traveler_preferences: dict


def _fmt(val) -> str:
    """Safe formatting helper for numbers in INR."""
    if val is None:
        return "N/A"
    try:
        return f"₹{float(val):,.0f}"
    except Exception:
        return str(val)


def _redact_direct_contact_details(text: str) -> str:
    """Remove common email/phone patterns while preserving ISO travel dates."""
    dates = []

    def preserve_date(match):
        token = f"__TRAVEL_DATE_{len(dates)}__"
        dates.append((token, match.group(0)))
        return token

    text = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", preserve_date, text)
    text = re.sub(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        "[email redacted]",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(?<![\w])(?:\+\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{4}(?![\w])",
        "[phone number redacted]",
        text,
    )
    for token, value in dates:
        text = text.replace(token, value)
    return text


# ── Gemini Helper ──────────────────────────────────────────────────────────────
def _call_gemini(prompt: str) -> str:
    """Call only free-tier models, trying the fallback after a model/API failure."""
    if not _genai_client:
        return ""
    for model in dict.fromkeys((GEMINI_MODEL, GEMINI_FALLBACK)):
        try:
            response = _genai_client.models.generate_content(
                model=model,
                contents=prompt,
            )
            if response.text:
                return response.text
        except Exception as error:
            logger.warning("Gemini call failed for %s (%s)", model, type(error).__name__)
    return ""


# ── Node 1: RAG Retrieval ──────────────────────────────────────────────────────
async def rag_retrieval_node(state: TravelAgentState) -> dict:
    """Retrieve destination knowledge from ChromaDB or the keyword fallback."""
    try:
        context = _retriever(state["user_message"], n_results=3)
        return {
            "rag_context": context,
            "tool_status": state["tool_status"] + ["✅ Retrieved destination knowledge base"],
        }
    except Exception:
        return {
            "rag_context": "",
            "tool_status": state["tool_status"] + ["⚠️ Knowledge retrieval skipped"],
        }


# ── Node 2: Intent Parser ──────────────────────────────────────────────────────

# Comprehensive city/destination list for regex extraction
_ALL_CITIES = [
    # Indian Tier-1 & popular destinations
    "goa", "delhi", "new delhi", "mumbai", "bangalore", "bengaluru",
    "hyderabad", "chennai", "kolkata", "pune", "ahmedabad", "surat",
    # Rajasthan
    "jaipur", "jodhpur", "udaipur", "jaisalmer", "pushkar", "ajmer",
    "bikaner", "mount abu",
    # Himachal & North
    "manali", "shimla", "dharamshala", "mcleod ganj", "kasol", "kufri",
    "dalhousie", "khajjiar", "spiti", "lahaul", "kullu",
    # J&K / Ladakh
    "leh", "ladakh", "srinagar", "gulmarg", "pahalgam", "sonmarg",
    # Uttarakhand
    "rishikesh", "haridwar", "dehradun", "mussoorie", "nainital",
    "jim corbett", "corbett", "auli", "kedarnath", "badrinath",
    "chakrata", "lansdowne",
    # UP & Central
    "agra", "varanasi", "lucknow", "allahabad", "prayagraj", "mathura",
    "vrindavan", "orchha", "khajuraho", "bhopal", "indore", "ujjain",
    # North East
    "darjeeling", "gangtok", "sikkim", "shillong", "cherrapunji",
    "kaziranga", "tawang", "arunachal", "assam", "meghalaya", "manipur",
    # Kerala
    "kerala", "kochi", "munnar", "alleppey", "alappuzha", "thekkady",
    "kovalam", "varkala", "kozhikode", "calicut", "thrissur", "palakkad",
    # Karnataka
    "mysore", "mysuru", "coorg", "kodagu", "hampi", "badami",
    "mangalore", "udupi", "chikmagalur", "ooty",
    # Andhra & Telangana
    "tirupati", "vizag", "visakhapatnam", "vishakhapatnam", "vishakapatnam",
    "vijayawada", "warangal", "nellore",
    # Tamil Nadu
    "chennai", "madurai", "ooty", "kodaikanal", "pondicherry", "puducherry",
    "rameswaram", "kanyakumari", "mahabalipuram", "thanjavur",
    # Gujrat & West
    "rann of kutch", "kutch", "somnath", "diu", "dwarka", "amreli",
    "vadodara", "baroda", "rajkot",
    # Punjab & Haryana
    "amritsar", "chandigarh", "ludhiana", "golden temple",
    # Andaman
    "andaman", "port blair", "havelock", "neil island",
    # International
    "paris", "france", "rome", "italy", "london", "uk", "england",
    "barcelona", "spain", "amsterdam", "netherlands", "berlin", "germany",
    "prague", "vienna", "switzerland", "zurich", "geneva",
    "tokyo", "japan", "kyoto", "osaka",
    "bali", "indonesia", "jakarta",
    "bangkok", "thailand", "phuket", "chiang mai",
    "singapore", "malaysia", "kuala lumpur",
    "dubai", "abu dhabi", "uae",
    "maldives", "sri lanka", "colombo",
    "nepal", "kathmandu", "pokhara",
    "bhutan", "thimphu", "paro",
    "vietnam", "hanoi", "ho chi minh", "hoi an",
    "cambodia", "siem reap", "angkor",
    "new york", "usa", "los angeles", "las vegas", "miami",
    "canada", "toronto", "vancouver",
    "australia", "sydney", "melbourne",
    "new zealand", "auckland",
    "turkey", "istanbul", "cappadocia",
    "egypt", "cairo", "luxor",
    "morocco", "marrakech",
    "south africa", "cape town",
]

# Origin city list
_ORIGIN_CITIES = [
    "delhi", "new delhi", "mumbai", "bangalore", "bengaluru", "hyderabad",
    "chennai", "kolkata", "pune", "ahmedabad", "jaipur", "kochi",
    "lucknow", "chandigarh", "surat", "bhopal", "indore", "amritsar",
]


def _smart_parse_intent(msg: str) -> dict:
    """Comprehensive rule-based intent extractor — works for ANY destination worldwide."""
    msg_lower = msg.lower().strip()

    # ── Extract destination ──────────────────────────────────────────────────
    dest = None

    # Pattern: "to/in/at/visit <destination>"
    to_match = re.search(
        r'(?:trip to|travel to|going to|visit|visiting|explore|plan.*?to|holiday in|vacation in|tour of|weekend in|week in|days? in|days? at)\s+([\w\s]{2,30}?)'
        r'(?:\s+from|\s+under|\s+within|\s+for|\s+with|\s+by|$|,|\.|\?)',
        msg_lower
    )
    if to_match:
        candidate = to_match.group(1).strip()
        # Check against city list
        for city in sorted(_ALL_CITIES, key=len, reverse=True):
            if city in candidate or candidate in city:
                dest = city.title()
                break
        if not dest:
            # Use the extracted text directly (capitalize)
            dest = candidate.title()

    # Pattern: direct city mention anywhere in message
    if not dest:
        for city in sorted(_ALL_CITIES, key=len, reverse=True):  # longest first to avoid partial matches
            if re.search(r'\b' + re.escape(city) + r'\b', msg_lower):
                dest = city.title()
                break

    start_date = None
    date_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", msg_lower)
    if date_match:
        try:
            start_date = date.fromisoformat(date_match.group(1)).isoformat()
        except ValueError:
            pass

    # ── Extract origin ────────────────────────────────────────────────────────
    origin = None
    from_match = re.search(
        r'(?:from|departing|starting from|coming from)\s+([\w\s]{2,20}?)'
        r'(?:\s+to|\s+by|\s+via|\s+under|,|$)',
        msg_lower
    )
    if from_match:
        origin_candidate = from_match.group(1).strip()
        for city in _ORIGIN_CITIES:
            if city in origin_candidate:
                origin = city.title()
                break
        else:
            if len(origin_candidate) > 2:
                origin = origin_candidate.title()

    # ── Extract days ─────────────────────────────────────────────────────────
    days = 5
    days_match = re.search(r'(\d+)\s*(?:-|\s)?day', msg_lower)
    if days_match:
        days = max(1, min(int(days_match.group(1)), 30))
    elif re.search(r'weekend', msg_lower):
        days = 2
    elif re.search(r'week(?!end)', msg_lower):
        days = 7
    elif re.search(r'fortnight', msg_lower):
        days = 14

    # ── Extract budget ───────────────────────────────────────────────────────
    budget = None
    k_match = re.search(r'(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*k\b', msg_lower)
    lakh_match = re.search(r'(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:lakh|lac|l)\b', msg_lower)
    plain_match = re.search(r'(?:₹|rs\.?|inr)\s*(\d{4,})', msg_lower)
    if k_match:
        budget = int(float(k_match.group(1)) * 1000)
    elif lakh_match:
        budget = int(float(lakh_match.group(1)) * 100000)
    elif plain_match:
        budget = int(plain_match.group(1).replace(',', ''))

    # ── Extract guests ───────────────────────────────────────────────────────
    guests = 2
    guests_match = re.search(r'(\d+)\s*(?:person|people|guest|pax|adult|travell?er)', msg_lower)
    me_solo = any(x in msg_lower for x in ["solo", "just me", "myself", "alone", "1 person"])
    if guests_match:
        guests = max(1, int(guests_match.group(1)))
    elif me_solo:
        guests = 1

    # ── Preferences ─────────────────────────────────────────────────────────
    prefs = ["attractions", "restaurants"]
    if any(x in msg_lower for x in ["nature", "trekking", "hiking", "camping", "wildlife"]):
        prefs = ["natural", "restaurants"]
    elif any(x in msg_lower for x in ["heritage", "temple", "history", "culture", "fort"]):
        prefs = ["cultural", "restaurants"]
    elif any(x in msg_lower for x in ["beach", "sea", "coast", "water sport"]):
        prefs = ["beaches", "restaurants"]

    return {
        "destination": dest,
        "start_date": start_date,
        "days": days,
        "budget_inr": budget,
        "origin": origin,
        "preferences": prefs,
        "guests": guests,
        "needs_flights": True,
        "needs_trains": True,
        "needs_buses": True,
        "needs_hotels": True,
        "needs_weather": True,
        "is_general_question": any(x in msg_lower for x in ["what is", "tell me about", "explain", "how to get", "visa", "currency"]),
    }


async def intent_parser_node(state: TravelAgentState) -> dict:
    """Parse user message into structured travel intent using Gemini or Smart Regex."""
    prompt = f"""Parse this travel request into JSON. Respond with ONLY valid JSON, nothing else.

User message: "{_redact_direct_contact_details(state['user_message'])}"
Traveler preferences: {json.dumps(state.get("traveler_preferences", {}), ensure_ascii=False)}

Return this exact JSON structure:
{{
  "destination": "city or country name (string or null if not specified)",
  "start_date": "YYYY-MM-DD if the user specified a travel date, otherwise null",
  "days": 5,
  "budget_inr": null,
  "origin": "city the user is travelling FROM, or null if not specified",
  "preferences": ["attractions", "restaurants"],
  "guests": 2,
  "needs_flights": true,
  "needs_trains": true,
  "needs_buses": true,
  "needs_hotels": true,
  "needs_weather": true,
  "is_general_question": false
}}"""

    gemini_intent = None
    if state.get("ai_data_consent"):
        try:
            text = await asyncio.to_thread(_call_gemini, prompt)
            if text:
                text = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    text = match.group(0)
                parsed = json.loads(text)
                # Validate Gemini didn't return garbage
                dest = parsed.get('destination', '')
                if dest and str(dest).lower() not in ['null', 'unknown', '', 'your destination', 'none']:
                    gemini_intent = parsed
        except Exception as error:
            logger.warning("Gemini intent parsing failed (%s); using local parser", type(error).__name__)

    # Always run smart regex too — use it if Gemini failed or gave bad destination
    regex_intent = _smart_parse_intent(state["user_message"])
    traveler_preferences = state.get("traveler_preferences", {})
    selected_preferences = []
    if traveler_preferences.get("interests"):
        interest_preferences = {
            "culture": "cultural",
            "history": "historic",
            "nature": "natural",
            "beaches": "beaches",
            "adventure": "natural",
            "food": "restaurants",
        }
        selected_preferences = [
            interest_preferences[interest]
            for interest in traveler_preferences["interests"]
            if interest in interest_preferences
        ]

    # Choose: prefer Gemini if it gave a valid, specific destination
    if gemini_intent and gemini_intent.get('destination') and str(gemini_intent['destination']).lower() not in ['null', '']:
        intent = gemini_intent
        if not intent.get('origin') and regex_intent.get('origin'):
            intent['origin'] = regex_intent['origin']
        if not intent.get('start_date'):
            intent['start_date'] = regex_intent.get('start_date')
    else:
        intent = regex_intent
        if gemini_intent and gemini_intent.get('destination') and str(gemini_intent['destination']).lower() not in ['', 'null', 'none']:
            intent = gemini_intent
            if not intent.get("start_date"):
                intent["start_date"] = regex_intent.get("start_date")

    if selected_preferences:
        intent["preferences"] = list(dict.fromkeys([*selected_preferences, "restaurants"]))

    dest = intent.get('destination') or "unspecified destination"
    days = intent.get('days', 5)
    return {
        "parsed_intent": intent,
        "tool_status": state["tool_status"] + [
            f"🗺️ Planning {days}-day trip to {dest}"
        ],
    }


# ── Node 3: Tool Execution ────────────────────────────────────────────────────
async def tool_execution_node(state: TravelAgentState) -> dict:
    """Call ALL MCP tools — flights, trains, buses, cabs, hotels, weather, places, 3 meals — in parallel."""
    intent = state.get("parsed_intent", {})

    if intent.get("is_general_question"):
        return {
            "tool_results": {},
            "tool_status": state["tool_status"] + ["ℹ️ General question — answering from knowledge base"],
        }

    destination = intent.get("destination")
    if not destination or destination == "Local Destination":
        return {
            "tool_results": {},
            "itinerary_json": None,
            "tool_status": state["tool_status"] + ["ℹ️ Please specify a destination to build a trip plan."],
        }
    days = int(intent.get("days", 5))
    budget = intent.get("budget_inr")
    origin = intent.get("origin") or ""
    prefs = intent.get("preferences", ["attractions", "restaurants"])
    guests = int(intent.get("guests", 2))

    new_status = state["tool_status"] + [
        f"🔍 Checking available travel data for {destination}"
        + (f" from {origin}" if origin else "; origin not specified")
    ]

    try:
        itinerary_data = await build_itinerary(
            destination=destination,
            days=days,
            budget_inr=budget,
            origin=origin,
            start_date=intent.get("start_date"),
            preferences=prefs,
            guests=guests,
            traveler_preferences=state.get("traveler_preferences", {}),
        )

        result_status = list(new_status)
        flights = itinerary_data.get("all_flights", [])
        trains = itinerary_data.get("all_trains", [])
        buses = itinerary_data.get("all_buses", [])
        hotels = itinerary_data.get("all_hotels", [])
        places = itinerary_data.get("top_places", [])
        weather = itinerary_data.get("weather_summary", "")

        if flights:
            cheapest_f = flights[0].get("price_inr", 0)
            result_status.append(f"✈️ Flight offer: {_fmt(cheapest_f)} ({flights[0].get('airline','IndiGo')})")
        if trains:
            cheapest_t = trains[0].get("cheapest_fare_inr", 0)
            result_status.append(f"🚆 Train option: {_fmt(cheapest_t)} ({trains[0].get('train_name','Vande Bharat')})")
        if buses:
            cheapest_b = buses[0].get("fare_inr", 0)
            result_status.append(f"🚌 Bus sleeper: {_fmt(cheapest_b)} ({buses[0].get('operator','IntrCity')})")
        if hotels:
            result_status.append(f"🏨 Best hotel: {hotels[0].get('name','Hotel')} — {_fmt(hotels[0].get('price_per_night_inr',0))}/night")
        if places:
            result_status.append(f"📍 Found {len(places)} top attractions & 3-meal dining guide")
        if weather:
            result_status.append(f"🌤️ Weather: {weather}")

        # 🆕 Live conditions status
        live_current = itinerary_data.get("live_current_weather", {})
        road = itinerary_data.get("road_conditions", {})
        aq = itinerary_data.get("air_quality", {})
        if live_current.get("temp_c") is not None:
            result_status.append(
                f"🌡️ Live Now: {live_current['icon']} {live_current['temp_c']}°C "
                f"(feels {live_current.get('feels_like_c','?')}°C) · UV {live_current.get('uv_index','?')}"
            )
        if road.get("risk_level"):
            result_status.append(
                f"{road.get('risk_icon','🛣️')} Road conditions: {road['risk_level']} risk · {road.get('best_departure_time','Good to go')}"
            )
        if aq.get("level"):
            result_status.append(f"💨 Air Quality: {aq['level']} (AQI {aq.get('us_aqi','?')})")

        return {
            "tool_results": itinerary_data,
            "itinerary_json": itinerary_data,
            "tool_status": result_status,
        }

    except Exception as e:
        return {
            "tool_results": {},
            "itinerary_json": None,
            "tool_status": new_status + [f"⚠️ Tool error: {str(e)[:80]}"],
        }


# ── Node 4: LLM / Smart Synthesis ─────────────────────────────────────────────
async def llm_synthesis_node(state: TravelAgentState) -> dict:
    """Synthesize multi-modal results with 3 Meals & Weather Adaptation using Gemini API or Smart Concierge."""
    intent = state.get("parsed_intent", {})
    tool_data = state.get("tool_results", {})
    rag_context = state.get("rag_context", "")
    destination = intent.get("destination", "your destination")
    days = intent.get("days", 5)

    is_general_question = bool(intent.get("is_general_question"))
    if not intent.get("destination") and not is_general_question:
        return {
            "llm_response": "Tell me which destination you want to visit, and I can prepare a trip outline with the live data currently available.",
            "tool_status": state["tool_status"],
        }

    transport_comparison = tool_data.get("transport_comparison", [])
    route_rec = tool_data.get("route_recommendation", {})
    flights = tool_data.get("all_flights", [])
    trains = tool_data.get("all_trains", [])
    buses = tool_data.get("all_buses", [])
    hotels = tool_data.get("all_hotels", [])
    places = [p.get("name") for p in tool_data.get("top_places", [])[:5]]
    restaurants = [r.get("name") for r in tool_data.get("top_restaurants", [])[:3]]
    weather = tool_data.get("weather_summary", "")
    budget_bd = tool_data.get("budget_breakdown", {})
    est_cost = tool_data.get("estimated_cost_inr")

    safe_user_message = _redact_direct_contact_details(state["user_message"])
    if is_general_question:
        prompt = f"""You are Roam AI, a travel information assistant.

User question: "{safe_user_message}"

CURATED DESTINATION KNOWLEDGE (may be outdated):
{rag_context[:1200]}

Use only this context for destination-specific claims. Do not present curated information as live or verified. Do not invent current prices, schedules, availability, weather, or opening hours. If the context does not answer the question, say what information is missing.

Answer concisely."""
    else:
        prompt = f"""You are Roam AI, an advanced multi-modal travel concierge.

User request: "{safe_user_message}"

DESTINATION KNOWLEDGE:
{rag_context[:1200]}

LIVE MULTI-MODAL TRAVEL DATA:
- Origin: {tool_data.get('origin') or 'not specified'}
- Provider status: {tool_data.get('provider_status', {})}
- Route Recommendation: {route_rec.get('best_mode')} ({route_rec.get('reason')})
- Flights: {flights[0] if flights else 'N/A'}
- Trains: {trains[0] if trains else 'N/A'}
- Buses: {buses[0] if buses else 'N/A'}
- Hotels: {hotels[0] if hotels else 'N/A'}
- Weather: {weather}
- Places: {', '.join(places)}
- Dining suggestions: {tool_data.get('meal_suggestions', {})}
- Total Estimated Cost: {_fmt(est_cost)} for {tool_data.get('guests',2)} guests

LIVE CURRENT CONDITIONS:
- Current Temp: {tool_data.get('live_current_weather', {}).get('temp_c','?')}°C, feels like {tool_data.get('live_current_weather', {}).get('feels_like_c','?')}°C
- Condition: {tool_data.get('live_current_weather', {}).get('icon','')} {tool_data.get('live_current_weather', {}).get('condition','')}
- UV Index: {tool_data.get('live_current_weather', {}).get('uv_index','?')} | Wind: {tool_data.get('live_current_weather', {}).get('wind_kmh','?')} km/h
- Air Quality: {tool_data.get('air_quality', {}).get('level','N/A')} (AQI {tool_data.get('air_quality', {}).get('us_aqi','?')})
- Road Risk: {tool_data.get('road_conditions', {}).get('risk_level','Unknown')}
- Best Departure Time: {tool_data.get('road_conditions', {}).get('best_departure_time','Unavailable')}

Only describe details supported by the provider data above. Distinguish live quotes from estimates and curated suggestions. Never invent fares, schedules, room availability, restaurant hours, road traffic, or weather. Clearly state when a provider is not configured or a forecast is outside its supported date range.

Write a concise response covering available route, accommodation, place, weather, and safety information. Use emojis naturally."""

    if state.get("ai_data_consent") and _genai_client:
        try:
            text = await asyncio.to_thread(_call_gemini, prompt)
            if text and len(text.strip()) > 50:
                return {
                    "llm_response": text,
                    "tool_status": state["tool_status"] + ["✨ Generated response with Gemini"],
                }
        except Exception as error:
            logger.warning("Gemini response synthesis failed (%s); using local planner", type(error).__name__)

    # ── Advanced Smart Concierge Synthesizer ──────────────────────────────────
    fallback_status = list(state["tool_status"])
    if state.get("ai_data_consent") and _genai_client:
        fallback_status.append("⚠️ Gemini did not return a usable response; the local planner was used.")
    elif state.get("ai_data_consent"):
        fallback_status.append("⚠️ Gemini API key is not configured; the local planner was used.")

    if is_general_question:
        return {
            "llm_response": (
                "I couldn't answer this general question with the local trip planner. "
                "You can opt in to Gemini for a response, or ask me to build a trip outline."
            ),
            "tool_status": fallback_status,
        }

    response_parts = [
        f"### {days}-Day Trip Outline: {destination}\n",
        "Provider coverage is shown below; this outline does not book travel or guarantee availability.\n",
    ]
    if not tool_data.get("origin"):
        response_parts.append("Add your departure city to get route-specific travel options.\n")
    if tool_data.get("dates", {}).get("assumed"):
        response_parts.append(
            f"No travel date was provided; {tool_data['dates']['start']} is only a placeholder.\n"
        )

    # Best Route Recommendation
    if route_rec:
        response_parts.append("**🛣️ Route data:**")
        response_parts.append(f"• **Available option:** **{route_rec.get('best_mode', 'No live quote')}**")
        response_parts.append(f"• **Why:** {route_rec.get('reason')}")
        if route_rec.get('local_transport'):
            response_parts.append(f"• **Local Transit:** {route_rec.get('local_transport')}")
        response_parts.append("")

    # Transport options comparison block
    if transport_comparison:
        response_parts.append("**🚄 Transport Mode Options:**")
        for item in transport_comparison:
            response_parts.append(
                f"• **{item['mode']}** ({item['provider']}): **{_fmt(item['price_per_person_inr'])}**/person • Duration: {item['duration']} `[{item['badge']}]`"
            )
        response_parts.append("")

    # Hotel & Accommodation
    if hotels:
        h = hotels[0]
        response_parts.append("**🏨 Live hotel offer:**")
        rating = f" ({h['rating']}★)" if h.get("rating") else ""
        response_parts.append(f"• **{h.get('name')}**{rating} — **{_fmt(h.get('price_per_night_inr'))}**/night")
        response_parts.append("")

    # Live Current Weather
    live_c = tool_data.get("live_current_weather", {})
    if live_c.get("temp_c") is not None:
        response_parts.append(f"**🌡️ Live Weather Right Now in {destination}:**")
        response_parts.append(
            f"• {live_c.get('icon','')} **{live_c.get('condition','')}** — "
            f"**{live_c.get('temp_c')}°C** (feels like {live_c.get('feels_like_c')}°C)"
        )
        response_parts.append(
            f"• 💧 Humidity: {live_c.get('humidity_pct')}% · 💨 Wind: {live_c.get('wind_kmh')} km/h ({live_c.get('wind_direction','')}) · "
            f"☀️ UV Index: {live_c.get('uv_index','?')}"
        )
        aq = tool_data.get("air_quality", {})
        if aq.get("level"):
            response_parts.append(f"• 💨 Air Quality: **{aq['level']}** (AQI {aq.get('us_aqi','?')}) — {aq.get('health_advice','')}")
        response_parts.append("")

    # Weather forecast & Places
    if weather:
        response_parts.append(f"**📅 Weather forecast:** {weather}")
    if places:
        place_source = tool_data.get("provider_status", {}).get("places", {}).get("status")
        label = "Place listings" if place_source == "live_catalog" else "Curated place suggestions (not live-verified)"
        response_parts.append(f"**📍 {label}:** {', '.join(places)}")
    response_parts.append("")

    # Road Conditions
    road = tool_data.get("road_conditions", {})
    if road:
        risk = road.get("risk_level", "Unknown")
        risk_icon = road.get("risk_icon", "ℹ️")
        response_parts.append(f"**🛣️ Weather-based travel advisory (not live traffic): {risk_icon} {risk}**")
        if road.get("best_departure_time"):
            response_parts.append(f"• 🕐 **Best time to depart:** {road['best_departure_time']}")
        for alert in road.get("alerts", [])[:3]:
            response_parts.append(f"• {alert}")
        for cond in road.get("conditions", [])[:3]:
            response_parts.append(f"• {cond}")
        if road.get("detour_advice"):
            response_parts.append(f"• ↩️ **Detour tip:** {road['detour_advice'][0]}")
        response_parts.append("")

    # Best travel window
    btw = tool_data.get("best_travel_window", {})
    if btw.get("start"):
        response_parts.append(f"**⏰ Best Travel Window:** {btw.get('icon','')} Around {btw['start']} — {btw.get('reason','')}")
        response_parts.append("")

    meals = tool_data.get("meal_suggestions", {})
    if meals.get("status") == "curated":
        response_parts.append("**🍽️ Dining:** Curated suggestions are available; venue hours, availability, and prices are not verified.")
    elif meals.get("status") == "not_configured":
        response_parts.append("**🍽️ Dining:** Live restaurant search is not connected.")

    provider_status = tool_data.get("provider_status", {})
    unavailable = [
        name.replace("_", " ")
        for name, info in provider_status.items()
        if info.get("status") in {"not_configured", "not_integrated", "unsupported_location", "out_of_range", "provider_error", "sandbox", "no_results"}
    ]
    if unavailable:
        response_parts.append(f"\n**Not currently available:** {', '.join(unavailable)}.")

    return {
        "llm_response": "\n".join(response_parts),
        "tool_status": fallback_status + ["✅ Multi-modal travel plan ready"],
    }


# ── Build LangGraph ───────────────────────────────────────────────────────────
def create_travel_agent():
    graph = StateGraph(TravelAgentState)

    graph.add_node("rag_retrieval", rag_retrieval_node)
    graph.add_node("intent_parser", intent_parser_node)
    graph.add_node("tool_execution", tool_execution_node)
    graph.add_node("llm_synthesis", llm_synthesis_node)

    graph.set_entry_point("rag_retrieval")
    graph.add_edge("rag_retrieval", "intent_parser")
    graph.add_edge("intent_parser", "tool_execution")
    graph.add_edge("tool_execution", "llm_synthesis")
    graph.add_edge("llm_synthesis", END)

    return graph.compile()


_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = create_travel_agent()
    return _agent


async def run_agent(
    user_message: str,
    ai_data_consent: bool = False,
    traveler_preferences: Optional[dict] = None,
) -> dict:
    """Run the full multi-modal travel agent pipeline."""
    agent = get_agent()
    if ai_data_consent:
        initial_status = (
            ["🔐 Google Gemini free-tier use approved for this request; email and phone patterns are redacted."]
        )
        if not _genai_client:
            initial_status.append("⚠️ Gemini API key is not configured; local planning will be used.")
    else:
        initial_status = ["ℹ️ Gemini was not used because data-sharing consent was not provided."]
    initial_state: TravelAgentState = {
        "user_message": user_message,
        "rag_context": "",
        "parsed_intent": {},
        "tool_results": {},
        "llm_response": "",
        "itinerary_json": None,
        "tool_status": initial_status,
        "error": None,
        "ai_data_consent": ai_data_consent,
        "traveler_preferences": traveler_preferences or {},
    }
    final_state = await agent.ainvoke(initial_state)
    return {
        "response": final_state.get("llm_response", ""),
        "itinerary": final_state.get("itinerary_json"),
        "tool_status": final_state.get("tool_status", []),
    }
