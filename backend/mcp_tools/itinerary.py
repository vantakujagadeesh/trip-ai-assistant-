"""
MCP Tool: Multi-Modal Itinerary Builder (Orchestrator)
Generates 100% custom, destination-tailored, weather-adaptive itineraries with:
- 3 Meals of the day (Breakfast 🍳, Lunch 🥗, Dinner 🍽️)
- Best route & transit mode recommendations (Flight vs Vande Bharat Train vs Volvo Bus vs Cab)
- Dynamic weather adaptation (Indoor vs Outdoor swaps based on rain probability)
- Side-by-side transport comparison table & hotel/rental recommendations
- LIVE weather: current temp, UV, humidity, hourly 12h forecast, 7-day daily outlook
- Real-time road conditions: highway status, blockage risk, detour advice, departure timing
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from mcp_tools.flights import search_flights
from mcp_tools.hotels import search_hotels
from mcp_tools.weather import get_weather
from mcp_tools.places import get_places, get_3_meals
from mcp_tools.currency import get_travel_budget_breakdown
from mcp_tools.trains import search_trains
from mcp_tools.buses import search_buses
from mcp_tools.cabs import get_cab_and_rental_options
from mcp_tools.live_conditions import get_live_conditions

DESTINATION_IATA = {
    "goa": "GOI", "delhi": "DEL", "new delhi": "DEL", "mumbai": "BOM",
    "bangalore": "BLR", "bengaluru": "BLR", "kochi": "COK",
    "jaipur": "JAI", "varanasi": "VNS", "agra": "AGR", "udaipur": "UDR",
    "paris": "CDG", "france": "CDG", "rome": "FCO", "italy": "FCO",
    "tokyo": "NRT", "japan": "NRT", "kyoto": "ITM",
    "bangkok": "BKK", "thailand": "BKK", "singapore": "SIN",
    "bali": "DPS", "dubai": "DXB", "london": "LHR",
}

ORIGIN_IATA = {
    "delhi": "DEL", "new delhi": "DEL", "mumbai": "BOM",
    "bangalore": "BLR", "hyderabad": "HYD", "chennai": "MAA",
    "pune": "PNQ", "kolkata": "CCU", "ahmedabad": "AMD",
}


async def build_itinerary(
    destination: str,
    days: int,
    budget_inr: Optional[float] = None,
    origin: str = "Delhi",
    start_date: Optional[str] = None,
    preferences: Optional[list] = None,
    guests: int = 2,
) -> dict:
    """
    Master orchestrator: builds a weather-adaptive, 3-meals-a-day multi-modal trip plan.
    """
    if not start_date:
        start_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")

    end_date = (datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=days - 1)).strftime("%Y-%m-%d")
    prefs = preferences or ["attractions", "restaurants"]

    dest_key = destination.lower().strip()
    origin_key = origin.lower().strip()

    dest_iata = DESTINATION_IATA.get(dest_key, destination.upper()[:3])
    origin_iata = ORIGIN_IATA.get(origin_key, "DEL")

    # Run ALL MCP tool tasks in parallel for maximum speed (10 tools)
    tasks = [
        search_flights(origin_iata, dest_iata, start_date, adults=guests, budget_inr=budget_inr),
        search_hotels(dest_iata[:3], start_date, end_date, adults=guests,
                      budget_per_night_inr=(budget_inr / days / 2) if budget_inr else None),
        get_weather(destination, start_date, end_date),
        get_places(destination, prefs[0] if prefs else "attractions"),
        get_places(destination, prefs[1] if len(prefs) > 1 else "restaurants"),
        search_trains(origin, destination, start_date, budget_inr=budget_inr),
        search_buses(origin, destination, start_date, budget_inr=budget_inr),
        get_cab_and_rental_options(origin, destination, days=days, budget_inr=budget_inr),
        get_3_meals(destination),
        get_live_conditions(destination, origin=origin),  # 🆕 Live weather + road conditions
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    flight_data, hotel_data, weather_data, places_data, restaurants_data, train_data, bus_data, cab_data, meals_data, live_data = [
        r if not isinstance(r, Exception) else {} for r in results
    ]

    # Budget breakdown calculation
    budget_breakdown = None
    if budget_inr:
        budget_breakdown = await get_travel_budget_breakdown(budget_inr, destination, days)

    # Multi-modal transport comparison & route advice
    transport_comparison, route_recommendation = _build_transport_and_route_advice(
        origin=origin,
        destination=destination,
        flight_data=flight_data,
        train_data=train_data,
        bus_data=bus_data,
        cab_data=cab_data,
        guests=guests,
        budget_inr=budget_inr
    )

    # Extract top choices safely
    flights_list = flight_data.get("offers", []) if isinstance(flight_data, dict) else []
    best_flight = flights_list[0] if flights_list else None

    hotels_list = hotel_data.get("hotels", []) if isinstance(hotel_data, dict) else []
    best_hotel = hotels_list[0] if hotels_list else None

    trains_list = train_data.get("trains", []) if isinstance(train_data, dict) else []
    best_train = trains_list[0] if trains_list else None

    buses_list = bus_data.get("buses", []) if isinstance(bus_data, dict) else []
    best_bus = buses_list[0] if buses_list else None

    # Weather forecast list
    weather_forecast = weather_data.get("forecast", []) if isinstance(weather_data, dict) else []

    # Live conditions (current weather + road status)
    live_current = live_data.get("current_weather", {}) if isinstance(live_data, dict) else {}
    live_hourly = live_data.get("hourly_forecast", []) if isinstance(live_data, dict) else []
    live_daily = live_data.get("daily_forecast", []) if isinstance(live_data, dict) else []
    road_conditions = live_data.get("road_conditions", {}) if isinstance(live_data, dict) else {}
    air_quality = live_data.get("air_quality", {}) if isinstance(live_data, dict) else {}
    travel_advisories = live_data.get("travel_advisories", []) if isinstance(live_data, dict) else []
    best_travel_window = live_data.get("best_travel_window", {}) if isinstance(live_data, dict) else {}

    # Build 100% custom weather-adaptive day-by-day plan with 3 MEALS PER DAY!
    # Use live daily forecast if available, fall back to weather_data
    combined_forecast = live_daily[:days] if live_daily else weather_forecast
    day_plan = _build_weather_adaptive_day_plan(
        days=days,
        start_date=start_date,
        places=places_data.get("places", []) if isinstance(places_data, dict) else [],
        meals=meals_data if isinstance(meals_data, dict) else {},
        weather=combined_forecast,
        destination=destination,
        cab_rental=cab_data.get("self_drive_rentals", [{}])[2] if (isinstance(cab_data, dict) and cab_data.get("self_drive_rentals")) else {}
    )

    return {
        "destination": destination,
        "origin": origin,
        "days": days,
        "guests": guests,
        "dates": {"start": start_date, "end": end_date},
        "budget_inr": budget_inr,
        "budget_breakdown": budget_breakdown,

        # Transport & Route Advice
        "route_recommendation": route_recommendation,
        "transport_comparison": transport_comparison,
        "recommended_flight": best_flight,
        "all_flights": flights_list,
        "recommended_train": best_train,
        "all_trains": trains_list,
        "recommended_bus": best_bus,
        "all_buses": buses_list,
        "cabs_and_rentals": cab_data if isinstance(cab_data, dict) else {},

        # Accommodations & Weather
        "recommended_hotel": best_hotel,
        "all_hotels": hotels_list,
        "weather_summary": weather_data.get("summary", "") if isinstance(weather_data, dict) else "",
        "weather_forecast": weather_forecast[:days],

        # 🆕 LIVE Conditions (current + hourly + road + AQ)
        "live_current_weather": live_current,
        "live_hourly_forecast": live_hourly,
        "live_daily_forecast": live_daily,
        "road_conditions": road_conditions,
        "air_quality": air_quality,
        "travel_advisories": travel_advisories,
        "best_travel_window": best_travel_window,

        # 🆕 Informative Culture, Safety & Packing Guides
        "cultural_guide": _get_cultural_safety_guide(destination),
        "packing_checklist": _get_packing_checklist(destination, combined_forecast),

        "top_places": places_data.get("places", [])[:6] if isinstance(places_data, dict) else [],
        "top_restaurants": restaurants_data.get("places", [])[:4] if isinstance(restaurants_data, dict) else [],
        "day_plan": day_plan,
        "estimated_cost_inr": _estimate_cost(best_flight, best_hotel, days, guests, best_train),
    }


def _build_transport_and_route_advice(origin, destination, flight_data, train_data, bus_data, cab_data, guests, budget_inr):
    """Build side-by-side transport comparison and explicit best route advice."""
    options = []
    best_mode_title = "Flight / Train"
    best_mode_reason = f"Fastest & most convenient journey from {origin.title()} to {destination.title()}."

    # 1. Flight
    if isinstance(flight_data, dict) and flight_data.get("offers"):
        top_f = flight_data["offers"][0]
        options.append({
            "mode": "Flight ✈️",
            "provider": f"{top_f.get('airline', 'Flight')}",
            "duration": top_f.get("duration", "2h 15m").replace("PT", "").replace("H", "h ").replace("M", "m"),
            "price_per_person_inr": top_f.get("price_inr", 4500),
            "total_group_price_inr": top_f.get("price_inr", 4500) * guests,
            "badge": "Fastest",
            "badge_color": "bg-emerald-100 text-emerald-800"
        })

    # 2. Train
    if isinstance(train_data, dict) and train_data.get("trains"):
        top_t = train_data["trains"][0]
        options.append({
            "mode": "Train 🚆",
            "provider": f"{top_t.get('train_name', 'Express')}",
            "duration": top_t.get("duration", "7h 45m"),
            "price_per_person_inr": top_t.get("cheapest_fare_inr", 1815),
            "total_group_price_inr": top_t.get("cheapest_fare_inr", 1815) * guests,
            "badge": "Most Scenic & Eco",
            "badge_color": "bg-blue-100 text-blue-800"
        })

    # 3. Bus
    if isinstance(bus_data, dict) and bus_data.get("buses"):
        top_b = bus_data["buses"][0]
        options.append({
            "mode": "Intercity Bus 🚌",
            "provider": f"{top_b.get('operator', 'Volvo Sleeper')}",
            "duration": top_b.get("duration", "12h 30m"),
            "price_per_person_inr": top_b.get("fare_inr", 990),
            "total_group_price_inr": top_b.get("fare_inr", 990) * guests,
            "badge": "Overnight Saver",
            "badge_color": "bg-amber-100 text-amber-800"
        })

    # 4. Outstation Cab
    if isinstance(cab_data, dict) and cab_data.get("outstation_cabs"):
        top_c = cab_data["outstation_cabs"][0]
        options.append({
            "mode": "Outstation Taxi 🚗",
            "provider": f"{top_c.get('category', 'Sedan Cab')}",
            "duration": "Doorstep to Doorstep",
            "price_per_person_inr": round(top_c.get("estimated_one_way_inr", 3500) / max(guests, 1), 0),
            "total_group_price_inr": top_c.get("estimated_one_way_inr", 3500),
            "badge": "Door-to-Door",
            "badge_color": "bg-purple-100 text-purple-800"
        })

    # Route Advice Synthesis
    dest_l = destination.lower()
    if "jaipur" in dest_l or "agra" in dest_l:
        best_mode_title = "Vande Bharat Express Train 🚆"
        best_mode_reason = f"Takes under 4 hours from {origin.title()}, avoids airport hassle & highway traffic, includes food!"
    elif "goa" in dest_l and "mumbai" in origin.lower():
        best_mode_title = "Vande Bharat Train or Volvo AC Sleeper Bus 🚌"
        best_mode_reason = "7.5h Vande Bharat train or overnight Volvo AC Sleeper bus saves 1 night hotel expense."
    elif budget_inr and budget_inr < 15000:
        best_mode_title = "Express Train 3-Tier AC or Volvo Bus 🚌"
        best_mode_reason = f"Saves budget (fares under ₹1,500) while offering comfortable reclining sleepers."
    else:
        best_mode_title = "Direct Flight ✈️ or Vande Bharat Train 🚆"
        best_mode_reason = f"Best balance of speed (2h flight / 7h train) and high comfort for your {destination.title()} trip."

    recommendation = {
        "best_mode": best_mode_title,
        "reason": best_mode_reason,
        "local_transport": f"Rent a Scooter (₹450/day) or Self-Drive Car (₹1,500/day) upon arrival in {destination.title()} for maximum freedom."
    }

    return options, recommendation


def _build_weather_adaptive_day_plan(days, start_date, places, meals, weather, destination, cab_rental) -> list:
    """Build 100% custom weather-adaptive day-by-day plan with 3 MEALS PER DAY!"""
    plan = []
    place_idx = 0

    bf_list = meals.get("breakfast", [{"name": "Local Breakfast Café", "dish": "Fresh regional breakfast", "price_inr": 200}])
    lunch_list = meals.get("lunch", [{"name": "Regional Dining House", "dish": "Local lunch thali", "price_inr": 450}])
    dinner_list = meals.get("dinner", [{"name": "Clifftop / Beach Restaurant", "dish": "Specialty dinner", "price_inr": 800}])

    for day_num in range(1, days + 1):
        date = (datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=day_num - 1)).strftime("%Y-%m-%d")
        day_w = weather[day_num - 1] if day_num - 1 < len(weather) else {}
        rain_prob = day_w.get("rain_probability", 20)
        is_rainy = rain_prob > 45 or any(w in day_w.get("condition", "").lower() for w in ["rain", "shower", "thunderstorm", "drizzle"])

        bf = bf_list[(day_num - 1) % len(bf_list)]
        lh = lunch_list[(day_num - 1) % len(lunch_list)]
        dn = dinner_list[(day_num - 1) % len(dinner_list)]

        activities = []

        # Breakfast Meal
        activities.append({
            "time": "8:30 AM",
            "type": "food",
            "title": f"Breakfast 🍳 at {bf['name']}",
            "description": f"Must try: {bf['dish']} (~₹{bf.get('price_inr', 200)})"
        })

        if day_num == 1:
            activities.append({
                "time": "10:30 AM", "type": "travel",
                "title": f"Arrival & Hotel Check-In in {destination.title()}",
                "description": f"Arrive, check into hotel, pick up local rental vehicle ({cab_rental.get('car_model', 'scooter/car')}), and get oriented."
            })
            # Lunch
            activities.append({
                "time": "1:30 PM", "type": "food",
                "title": f"Lunch 🥗 at {lh['name']}",
                "description": f"Specialty: {lh['dish']} (~₹{lh.get('price_inr', 450)})"
            })
            # Afternoon
            p = places[place_idx % len(places)] if places else {"name": f"{destination.title()} Old Heritage Quarter", "description": "Explore local streets"}
            place_idx += 1
            activities.append({
                "time": "3:30 PM", "type": "attraction",
                "title": p["name"],
                "description": p.get("description", "Sightseeing & exploration")
            })

        elif day_num == days:
            # Morning Attraction
            p = places[place_idx % len(places)] if places else {"name": f"{destination.title()} Souvenir Market", "description": "Local shopping"}
            place_idx += 1
            activities.append({
                "time": "10:00 AM", "type": "attraction",
                "title": p["name"],
                "description": p.get("description", "Final sightseeing & souvenir shopping")
            })
            # Lunch
            activities.append({
                "time": "1:00 PM", "type": "food",
                "title": f"Farewell Lunch 🥗 at {lh['name']}",
                "description": f"Specialty: {lh['dish']} (~₹{lh.get('price_inr', 450)})"
            })
            activities.append({
                "time": "3:00 PM", "type": "travel",
                "title": "Check-Out & Onward Journey",
                "description": "Return rental vehicle and transfer to Airport / Station / Bus Terminal."
            })

        else:
            # Morning activity (Adapt based on weather!)
            if is_rainy:
                p1 = {"name": f"{destination.title()} Cultural Museum & Palace (Indoor)", "description": "Covered heritage museum & art gallery to stay dry during rain"}
            else:
                p1 = places[place_idx % len(places)] if places else {"name": f"Explore {destination.title()}", "description": "Outdoor sightseeing"}
                place_idx += 1

            activities.append({
                "time": "10:00 AM", "type": "attraction",
                "title": p1["name"],
                "description": p1.get("description", "")
            })

            # Lunch Meal
            activities.append({
                "time": "1:30 PM", "type": "food",
                "title": f"Lunch 🥗 at {lh['name']}",
                "description": f"Specialty: {lh['dish']} (~₹{lh.get('price_inr', 450)})"
            })

            # Afternoon activity
            if is_rainy:
                p2 = {"name": f"{destination.title()} Covered Handicraft Market & Tea House", "description": "Indoor market browsing & traditional tea/coffee tasting"}
            else:
                p2 = places[place_idx % len(places)] if places else {"name": f"{destination.title()} Sunset Viewpoint", "description": "Scenic sunset spot"}
                place_idx += 1

            activities.append({
                "time": "4:00 PM", "type": "attraction",
                "title": p2["name"],
                "description": p2.get("description", "")
            })

        # Evening Dinner Meal (Every day!)
        activities.append({
            "time": "8:00 PM", "type": "food",
            "title": f"Dinner 🍽️ at {dn['name']}",
            "description": f"Must try: {dn['dish']} (~₹{dn.get('price_inr', 800)})"
        })

        tip_txt = "🌧️ Rainy weather forecast — indoor activities & warm tea stops scheduled!" if is_rainy else day_w.get("travel_tip", "☀️ Great weather for outdoor exploring!")

        plan.append({
            "day": day_num,
            "date": date,
            "weather": day_w,
            "is_rainy": is_rainy,
            "activities": activities,
            "travel_tip": tip_txt,
        })

    return plan


def _estimate_cost(flight, hotel, days, guests, train=None) -> Optional[float]:
    """Calculate realistic cost estimate."""
    cost = 0
    if flight:
        cost += flight.get("price_inr", 0) * guests
    elif train:
        cost += train.get("cheapest_fare_inr", 1500) * guests
    else:
        cost += 3500

    if hotel:
        cost += hotel.get("price_per_night_inr", 0) * days

    # ~₹1800/day per guest for 3 meals + local transport + activity entries
    cost += 1800 * days * guests
    return round(cost, 0) if cost > 0 else None


def _get_cultural_safety_guide(destination: str) -> dict:
    """Generate local culture, etiquette, emergency helplines & scam advisories."""
    dest_l = destination.lower()
    is_foreign = any(c in dest_l for c in ["paris", "rome", "tokyo", "bali", "singapore", "london", "dubai", "barcelona"])

    emergency_numbers = {
        "police": "112 / 100",
        "ambulance": "108 / 102",
        "tourist_helpline": "1363 (National Tourist Helpline)",
    } if not is_foreign else {
        "police": "112 (European / Intl Standard)",
        "ambulance": "112 / Local Medical Emergency",
        "tourist_helpline": "Embassy Hotline",
    }

    scams = [
        "🚕 Rigged Taxi Meters: Always insist on using official prepaid taxi counters or Uber/Ola.",
        "🎟️ Fake Guides & Overpriced Tickets: Buy fort/museum tickets only at official ASI counters.",
        "🛍️ Shop Referral Commission Scam: Drivers may insist on taking you to specific 'handicraft shops' for high commissions.",
    ]

    etiquette = [
        "🛕 Temple / Mosque Etiquette: Remove footwear before entering; cover shoulders and knees.",
        "💵 Tipping Culture: 10% tip is standard & appreciated at restaurants; small change for porters.",
        "💧 Water Safety: Stick to sealed bottled water or RO purified water at verified eateries.",
    ]

    if "goa" in dest_l:
        scams.append("🛵 Scooter Rental Damage Claim: Take a 360° video of the rental scooter before riding away.")
    elif "rajasthan" in dest_l or "jaipur" in dest_l:
        scams.append("🐪 Elephant/Camels Overcharging: Agree on total ride fare before mounting.")
    elif "varanasi" in dest_l:
        scams.append("🔥 Cremation Ghat Donation Scam: Ignore anyone asking for 'wood donation' money near Manikarnika Ghat.")

    return {
        "emergency": emergency_numbers,
        "scams": scams,
        "etiquette": etiquette,
    }


def _get_packing_checklist(destination: str, weather: list) -> list:
    """Generate weather-adaptive interactive packing checklist."""
    dest_l = destination.lower()
    has_rain = any(w.get("rain_probability", 0) > 40 for w in weather) if weather else False
    is_hill_station = any(x in dest_l for x in ["manali", "shimla", "leh", "ladakh", "darjeeling", "munnar", "coorg", "ooty", "kodaikanal"])
    is_beach = any(x in dest_l for x in ["goa", "kerala", "andaman", "bali", "phuket", "pondicherry", "kovalam"])

    checklist = [
        "📱 Government ID Card (Aadhaar / Passport) & Hotel Vouchers",
        "🔌 Portable Power Bank & Multi-Plug Adapter",
        "💊 Personal Medication, ORS Powders & Pain Relief",
    ]

    if has_rain:
        checklist.append("☂️ Compact Windproof Umbrella & Waterproof Backpack Cover")
        checklist.append("🩴 Quick-dry footwear / sandals")

    if is_hill_station:
        checklist.append("🧥 Warm Fleece Jacket / Thermal Layers")
        checklist.append("🥾 Sturdy Trekking / Walking Shoes")
        checklist.append("🧴 Moisturizer & Lip Balm")
    elif is_beach:
        checklist.append("🩱 Sun-protective Swimwear & Beach Towel")
        checklist.append("🧴 High SPF 50+ Sunscreen & UV Sunglasses")
    else:
        checklist.append("👕 Breathable Cotton Clothing & Sun Hat")

    return checklist
