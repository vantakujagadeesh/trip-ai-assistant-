"""
LangGraph Agent — Orchestrates RAG + Multi-Modal MCP tools + Gemini LLM
Handles Flights, Trains (Vande Bharat/Rajdhani), Buses (Volvo Sleeper), Cabs/Rentals, Hotels, Weather & Places.
Includes Route Recommendations & 3-Meal Dining Plan (Breakfast, Lunch, Dinner).
"""
import os
import json
import re
import asyncio
from typing import TypedDict, Optional, List

from langgraph.graph import StateGraph, END

from rag.knowledge_base import get_knowledge_retriever
from mcp_tools.itinerary import build_itinerary

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

GEMINI_MODEL = "gemini-1.5-flash"  # Better free-tier quota than 2.0-flash
GEMINI_FALLBACK = "gemini-1.5-flash-8b"  # Cheapest model as last resort

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


def _fmt(val) -> str:
    """Safe formatting helper for numbers in INR."""
    if val is None:
        return "N/A"
    try:
        return f"₹{float(val):,.0f}"
    except Exception:
        return str(val)


# ── Gemini Helper ──────────────────────────────────────────────────────────────
def _call_gemini(prompt: str) -> str:
    """Call Gemini API with automatic fallback to cheaper models on quota errors."""
    if not _genai_client:
        return ""
    for model in [GEMINI_MODEL, GEMINI_FALLBACK]:
        try:
            response = _genai_client.models.generate_content(
                model=model,
                contents=prompt,
            )
            return response.text or ""
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err or "quota" in err.lower():
                continue  # Try next model
            raise RuntimeError(f"Gemini API ({model}): {e}")
    return ""  # All models exhausted


# ── Node 1: RAG Retrieval ──────────────────────────────────────────────────────
async def rag_retrieval_node(state: TravelAgentState) -> dict:
    """Retrieve relevant destination knowledge from ChromaDB / keyword fallback."""
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

    # Check for "local trip" or "nearby"
    if not dest and any(x in msg_lower for x in ["local trip", "nearby", "local travel", "near me", "around here"]):
        dest = "Local Destination"

    if not dest:
        dest = "Goa"  # absolute last resort only

    # ── Extract origin ────────────────────────────────────────────────────────
    origin = "Delhi"  # default
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

User message: "{state['user_message']}"

Return this exact JSON structure:
{{
  "destination": "city or country name (string, NEVER null)",
  "days": 5,
  "budget_inr": null,
  "origin": "city the user is travelling FROM (default Delhi)",
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
            if dest and dest not in ['null', 'unknown', '', 'your destination', 'None']:
                gemini_intent = parsed
    except Exception:
        pass

    # Always run smart regex too — use it if Gemini failed or gave bad destination
    regex_intent = _smart_parse_intent(state["user_message"])

    # Choose: prefer Gemini if it gave a valid, specific destination
    if gemini_intent and gemini_intent.get('destination') and gemini_intent['destination'].lower() not in ['goa', 'null', '']:
        intent = gemini_intent
        # Merge regex-extracted origin if Gemini left it as default
        if intent.get('origin', 'Delhi') == 'Delhi' and regex_intent.get('origin') != 'Delhi':
            intent['origin'] = regex_intent['origin']
    else:
        # Regex is more reliable when Gemini quota is exhausted or returned wrong city
        intent = regex_intent
        # But if Gemini gave a non-Goa destination, trust it
        if gemini_intent and gemini_intent.get('destination', '').lower() not in ['', 'null', 'none']:
            intent = gemini_intent

    dest = intent.get('destination', 'your destination')
    days = intent.get('days', 5)
    return {
        "parsed_intent": intent,
        "tool_status": state["tool_status"] + [
            f"🗺️ Planning {days}-day trip to {dest} from {intent.get('origin', 'Delhi')}"
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

    destination = intent.get("destination", "Goa")
    days = int(intent.get("days", 5))
    budget = intent.get("budget_inr")
    origin = intent.get("origin", "Delhi")
    prefs = intent.get("preferences", ["attractions", "restaurants"])
    guests = int(intent.get("guests", 2))

    new_status = state["tool_status"] + [f"🔍 Searching Flights, Trains, Buses & Cabs from {origin} to {destination}..."]

    try:
        itinerary_data = await build_itinerary(
            destination=destination,
            days=days,
            budget_inr=budget,
            origin=origin,
            preferences=prefs,
            guests=guests,
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

    prompt = f"""You are Roam AI, an advanced multi-modal travel concierge.

User request: "{state['user_message']}"

DESTINATION KNOWLEDGE:
{rag_context[:1200]}

LIVE MULTI-MODAL TRAVEL DATA:
- Route Recommendation: {route_rec.get('best_mode')} ({route_rec.get('reason')})
- Flights: {flights[0] if flights else 'N/A'}
- Trains: {trains[0] if trains else 'N/A'}
- Buses: {buses[0] if buses else 'N/A'}
- Hotels: {hotels[0] if hotels else 'N/A'}
- Weather: {weather}
- Places: {', '.join(places)}
- Total Estimated Cost: {_fmt(est_cost)} for {tool_data.get('guests',2)} guests

LIVE CURRENT CONDITIONS:
- Current Temp: {tool_data.get('live_current_weather', {}).get('temp_c','?')}°C, feels like {tool_data.get('live_current_weather', {}).get('feels_like_c','?')}°C
- Condition: {tool_data.get('live_current_weather', {}).get('icon','')} {tool_data.get('live_current_weather', {}).get('condition','')}
- UV Index: {tool_data.get('live_current_weather', {}).get('uv_index','?')} | Wind: {tool_data.get('live_current_weather', {}).get('wind_kmh','?')} km/h
- Air Quality: {tool_data.get('air_quality', {}).get('level','N/A')} (AQI {tool_data.get('air_quality', {}).get('us_aqi','?')})
- Road Risk: {tool_data.get('road_conditions', {}).get('risk_level','LOW')}
- Best Departure Time: {tool_data.get('road_conditions', {}).get('best_departure_time','Good to go')}

Write a hyper-useful response covering:
1. Best Recommended Route & Transport (Flight vs Train vs Bus)
2. Hotel recommendation & prices
3. 3-Meal Dining Plan (Breakfast 🍳, Lunch 🥗, Dinner 🍽️)
4. Live Weather & current conditions
5. Road conditions & smart departure advice
Use emojis naturally."""

    try:
        text = await asyncio.to_thread(_call_gemini, prompt)
        if text and len(text.strip()) > 50:
            return {
                "llm_response": text,
                "tool_status": state["tool_status"] + ["✨ Generated AI itinerary"],
            }
    except Exception:
        pass

    # ── Advanced Smart Concierge Synthesizer ──────────────────────────────────
    response_parts = [
        f"### 🌟 {days}-Day Weather-Adaptive Trip to {destination}\n",
        f"I've computed your route options, live weather, hotels, and a 3-Meal Dining Plan (Breakfast 🍳, Lunch 🥗, Dinner 🍽️)!\n",
    ]

    # Best Route Recommendation
    if route_rec:
        response_parts.append(f"**🛣️ Best Route Recommendation:**")
        response_parts.append(f"• **Recommended Mode:** **{route_rec.get('best_mode', 'Flight / Train')}**")
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
        response_parts.append(f"**🏨 Recommended Hotel:**")
        response_parts.append(f"• **{h.get('name')}** ({h.get('rating','4')}★) — **{_fmt(h.get('price_per_night_inr',0))}**/night")
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
        response_parts.append(f"**📅 7-Day Outlook:** {weather}")
    if places:
        response_parts.append(f"**📍 Top Sights & Attractions:** {', '.join(places)}")
    response_parts.append("")

    # Road Conditions
    road = tool_data.get("road_conditions", {})
    if road:
        risk = road.get("risk_level", "LOW")
        risk_icon = road.get("risk_icon", "✅")
        response_parts.append(f"**🛣️ Road Conditions: {risk_icon} {risk} Risk**")
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

    # 3 Meals Highlights
    response_parts.append(f"**🍽️ 3 Meals of the Day Included in Plan:**")
    response_parts.append(f"• **Breakfast 🍳:** Regional specialties & local café brews (~8:30 AM)")
    response_parts.append(f"• **Lunch 🥗:** Authentic regional thalis & coastal/heritage dining (~1:30 PM)")
    response_parts.append(f"• **Dinner 🍽️:** Clifftop, rooftop or beach shack dining experience (~8:00 PM)")
    response_parts.append("")

    response_parts.append("👉 Explore the day-by-day 3-meal timeline, live weather & road map on the right panel →")

    return {
        "llm_response": "\n".join(response_parts),
        "tool_status": state["tool_status"] + ["✅ Multi-modal travel plan ready"],
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


async def run_agent(user_message: str) -> dict:
    """Run the full multi-modal travel agent pipeline."""
    agent = get_agent()
    initial_state: TravelAgentState = {
        "user_message": user_message,
        "rag_context": "",
        "parsed_intent": {},
        "tool_results": {},
        "llm_response": "",
        "itinerary_json": None,
        "tool_status": [],
        "error": None,
    }
    final_state = await agent.ainvoke(initial_state)
    return {
        "response": final_state.get("llm_response", ""),
        "itinerary": final_state.get("itinerary_json"),
        "tool_status": final_state.get("tool_status", []),
    }
