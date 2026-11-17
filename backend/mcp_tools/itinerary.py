"""Build an itinerary outline from configured travel-data providers."""
import asyncio
from datetime import datetime, timedelta
from math import asin, cos, isfinite, radians, sin, sqrt
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
    origin: str = "",
    start_date: Optional[str] = None,
    preferences: Optional[list] = None,
    guests: int = 2,
) -> dict:
    """
    Orchestrate live weather/catalog lookups and clearly marked provider availability.
    """
    date_was_assumed = start_date is None
    if not start_date:
        start_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")

    if days < 1:
        raise ValueError("Trip duration must be at least one day.")
    end_date = (datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=days - 1)).strftime("%Y-%m-%d")
    prefs = preferences or ["attractions", "restaurants"]

    dest_key = destination.lower().strip()
    origin = origin.strip() if origin else ""
    origin_key = origin.lower()

    dest_iata = DESTINATION_IATA.get(dest_key)
    origin_iata = ORIGIN_IATA.get(origin_key)

    # Independent provider lookups run concurrently.
    tasks = [
        search_flights(origin_iata or "", dest_iata or "", start_date, adults=guests, budget_inr=budget_inr),
        search_hotels(dest_iata or "", start_date, end_date, adults=guests,
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
    flights_list = (
        flight_data.get("offers", [])
        if isinstance(flight_data, dict) and flight_data.get("live_quotes")
        else []
    )
    best_flight = flights_list[0] if flights_list else None

    hotels_list = (
        hotel_data.get("hotels", [])
        if isinstance(hotel_data, dict) and hotel_data.get("live_inventory")
        else []
    )
    place_list = places_data.get("places", []) if isinstance(places_data, dict) else []
    hotels_list = _attach_nearby_places(hotels_list, place_list)
    best_hotel = hotels_list[0] if hotels_list else None

    trains_list = (
        train_data.get("trains", [])
        if isinstance(train_data, dict) and train_data.get("availability_checked")
        else []
    )
    best_train = trains_list[0] if trains_list else None

    buses_list = (
        bus_data.get("buses", [])
        if isinstance(bus_data, dict) and bus_data.get("availability_checked")
        else []
    )
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

    # Use forecast data only for dates that the weather provider returned.
    combined_forecast = weather_forecast
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
        "dates": {"start": start_date, "end": end_date, "assumed": date_was_assumed},
        "budget_inr": budget_inr,
        "budget_breakdown": budget_breakdown,
        "provider_status": {
            "flights": _provider_status(flight_data),
            "hotels": _provider_status(hotel_data),
            "weather": _provider_status(weather_data),
            "places": _provider_status(places_data),
            "restaurants": _provider_status(restaurants_data),
            "trains": _provider_status(train_data),
            "buses": _provider_status(bus_data),
            "ground_transport": _provider_status(cab_data),
            "live_conditions": _provider_status(live_data),
        },

        # Transport & Route Advice
        "route_recommendation": route_recommendation,
        "transport_comparison": transport_comparison,
        "recommended_flight": best_flight,
        "all_flights": flights_list,
        "flight_search": flight_data,
        "recommended_train": best_train,
        "all_trains": trains_list,
        "train_search": train_data,
        "recommended_bus": best_bus,
        "all_buses": buses_list,
        "bus_search": bus_data,
        "cabs_and_rentals": cab_data if isinstance(cab_data, dict) else {},

        # Accommodations & Weather
        "recommended_hotel": best_hotel,
        "all_hotels": hotels_list,
        "hotel_search": hotel_data,
        "weather_summary": weather_data.get("summary", "") if isinstance(weather_data, dict) else "",
        "weather_forecast": weather_forecast[:days],
        "weather_status": _provider_status(weather_data),

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

        "top_places": place_list[:6],
        "top_restaurants": restaurants_data.get("places", [])[:4] if isinstance(restaurants_data, dict) else [],
        "meal_suggestions": meals_data if isinstance(meals_data, dict) else {},
        "day_plan": day_plan,
        "estimated_cost_inr": None,
        "cost_note": "A complete trip total is unavailable because live transport, accommodation, and on-ground prices are not all connected.",
    }


def _provider_status(result) -> dict:
    if not isinstance(result, dict):
        return {"status": "unavailable", "source": None, "note": "No provider response was received."}
    return {
        "status": result.get("status", "unavailable"),
        "source": result.get("source"),
        "note": result.get("note"),
        "checked_at": result.get("checked_at") or result.get("observed_at") or result.get("timestamp"),
    }


def _coordinates(item: dict) -> tuple[float, float] | None:
    if not isinstance(item, dict):
        return None
    try:
        latitude = float(item.get("latitude"))
        longitude = float(item.get("longitude"))
    except (TypeError, ValueError):
        return None
    if not isfinite(latitude) or not isfinite(longitude):
        return None
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return None
    return latitude, longitude


def _distance_km(first: tuple[float, float], second: tuple[float, float]) -> float:
    latitude1, longitude1 = map(radians, first)
    latitude2, longitude2 = map(radians, second)
    latitude_delta = latitude2 - latitude1
    longitude_delta = longitude2 - longitude1
    haversine = (
        sin(latitude_delta / 2) ** 2
        + cos(latitude1) * cos(latitude2) * sin(longitude_delta / 2) ** 2
    )
    return 6371.0088 * 2 * asin(sqrt(haversine))


def _attach_nearby_places(hotels: list, places: list) -> list:
    place_points = []
    for place in places:
        coordinates = _coordinates(place)
        if coordinates:
            place_points.append((place, coordinates))

    enriched_hotels = []
    for hotel in hotels:
        hotel = dict(hotel)
        hotel_coordinates = _coordinates(hotel)
        nearby = []
        if hotel_coordinates:
            distances = [
                (
                    _distance_km(hotel_coordinates, coordinates),
                    place,
                )
                for place, coordinates in place_points
            ]
            distances.sort(key=lambda result: result[0])
            nearby = [
                {"name": place.get("name", "Place listing"), "distance_km": round(distance, 1)}
                for distance, place in distances
                if distance <= 10
            ][:3]
            hotel["nearest_place_distance_km"] = (
                round(distances[0][0], 1) if distances else None
            )
        else:
            hotel["nearest_place_distance_km"] = None
        hotel["nearby_places"] = nearby
        enriched_hotels.append(hotel)
    return enriched_hotels


def _numeric_price(value) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    return price if isfinite(price) and price > 0 else None


def _build_transport_and_route_advice(origin, destination, flight_data, train_data, bus_data, cab_data, guests, budget_inr):
    """Build route advice only from provider-backed options."""
    options = []
    best_mode_title = "No live route quote available"
    best_mode_reason = "Live transport prices and availability are not connected for this route."

    # 1. Flight
    if isinstance(flight_data, dict) and flight_data.get("live_quotes") and flight_data.get("offers"):
        top_f = flight_data["offers"][0]
        price = _numeric_price(top_f.get("price_inr"))
        if price is not None:
            options.append({
                "mode": "Flight ✈️",
                "provider": f"{top_f.get('airline', 'Flight')}",
                "duration": top_f.get("duration", "Duration not provided").replace("PT", "").replace("H", "h ").replace("M", "m"),
                "price_per_person_inr": price,
                "total_group_price_inr": price * guests,
                "bookable_seats": top_f.get("bookable_seats"),
                "booking_status": "not_booked",
                "badge": "Live quote",
                "badge_color": "bg-emerald-100 text-emerald-800"
            })

    # 2. Train
    if isinstance(train_data, dict) and train_data.get("availability_checked") and train_data.get("trains"):
        top_t = train_data["trains"][0]
        price = _numeric_price(top_t.get("cheapest_fare_inr") or top_t.get("fare_inr"))
        if price is not None:
            options.append({
                "mode": "Train 🚆",
                "provider": f"{top_t.get('train_name', 'Train')}",
                "duration": top_t.get("duration", "Duration not provided"),
                "price_per_person_inr": price,
                "total_group_price_inr": price * guests,
                "bookable_seats": top_t.get("seats_available"),
                "booking_status": "not_booked",
                "badge": "Live quote",
                "badge_color": "bg-blue-100 text-blue-800"
            })

    # 3. Bus
    if isinstance(bus_data, dict) and bus_data.get("availability_checked") and bus_data.get("buses"):
        top_b = bus_data["buses"][0]
        price = _numeric_price(top_b.get("fare_inr"))
        if price is not None:
            options.append({
                "mode": "Intercity Bus 🚌",
                "provider": f"{top_b.get('operator', 'Bus provider')}",
                "duration": top_b.get("duration", "Duration not provided"),
                "price_per_person_inr": price,
                "total_group_price_inr": price * guests,
                "bookable_seats": top_b.get("seats_available"),
                "booking_status": "not_booked",
                "badge": "Live quote",
                "badge_color": "bg-amber-100 text-amber-800"
            })

    # 4. Outstation Cab
    if isinstance(cab_data, dict) and cab_data.get("availability_checked") and cab_data.get("outstation_cabs"):
        top_c = cab_data["outstation_cabs"][0]
        total_price = _numeric_price(top_c.get("estimated_one_way_inr"))
        if total_price is not None:
            options.append({
                "mode": "Outstation Taxi 🚗",
                "provider": f"{top_c.get('category', 'Cab provider')}",
                "duration": "Doorstep to doorstep",
                "price_per_person_inr": round(total_price / max(guests, 1), 2),
                "total_group_price_inr": total_price,
                "booking_status": "not_booked",
                "badge": "Live quote",
                "badge_color": "bg-purple-100 text-purple-800"
            })

    if options:
        options.sort(key=lambda item: item["price_per_person_inr"])
        best_mode_title = f"Lowest quoted price: {options[0]['mode']}"
        best_mode_reason = "Sorted by provider-returned price only; confirm schedules, availability, and booking terms with the provider."

    recommendation = {
        "best_mode": best_mode_title,
        "reason": best_mode_reason,
        "local_transport": None,
    }

    return options, recommendation


def _build_weather_adaptive_day_plan(days, start_date, places, meals, weather, destination, cab_rental) -> list:
    """Build a day outline using only available place, meal, and forecast data."""
    plan = []
    place_idx = 0

    bf_list = meals.get("breakfast", [])
    lunch_list = meals.get("lunch", [])
    dinner_list = meals.get("dinner", [])

    for day_num in range(1, days + 1):
        day_date = (datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=day_num - 1)).strftime("%Y-%m-%d")
        day_w = weather[day_num - 1] if day_num - 1 < len(weather) else {}
        rain_prob = day_w.get("rain_probability")
        condition = day_w.get("condition", "").lower()
        has_forecast = rain_prob is not None or bool(condition)
        is_rainy = (
            rain_prob > 45 if rain_prob is not None
            else any(w in condition for w in ["rain", "shower", "thunderstorm", "drizzle"])
            if has_forecast else None
        )

        bf = bf_list[(day_num - 1) % len(bf_list)] if bf_list else None
        lh = lunch_list[(day_num - 1) % len(lunch_list)] if lunch_list else None
        dn = dinner_list[(day_num - 1) % len(dinner_list)] if dinner_list else None

        activities = []

        _append_meal_or_break(activities, "breakfast", "8:30 AM", bf)

        if day_num == 1:
            activities.append({
                "time": "10:30 AM", "type": "travel",
                "title": f"Arrival in {destination.title()}",
                "description": "Allow time to arrive and get oriented. Accommodation and local transport are not booked by this plan."
            })
            _append_meal_or_break(activities, "lunch", "1:30 PM", lh)
            _append_place_or_free_time(activities, places, place_idx, "3:30 PM")
            place_idx += bool(places)

        elif day_num == days:
            _append_place_or_free_time(activities, places, place_idx, "10:00 AM")
            place_idx += bool(places)
            _append_meal_or_break(activities, "lunch", "1:00 PM", lh)
            activities.append({
                "time": "3:00 PM", "type": "travel",
                "title": "Check-Out & Onward Journey",
                "description": "Confirm checkout time and arrange your own transfer."
            })

        else:
            _append_place_or_free_time(activities, places, place_idx, "10:00 AM")
            place_idx += bool(places)
            _append_meal_or_break(activities, "lunch", "1:30 PM", lh)
            _append_place_or_free_time(activities, places, place_idx, "4:00 PM")
            place_idx += bool(places)

        _append_meal_or_break(activities, "dinner", "8:00 PM", dn)

        tip_txt = (
            day_w.get("travel_tip", "")
            if has_forecast
            else "Weather forecast is unavailable for this date; check conditions before outdoor plans."
        )

        plan.append({
            "day": day_num,
            "date": day_date,
            "weather": day_w,
            "weather_status": "available" if has_forecast else "unavailable",
            "is_rainy": is_rainy,
            "activities": activities,
            "travel_tip": tip_txt,
        })

    return plan


def _append_place_or_free_time(activities, places, place_idx, time):
    if places:
        place = places[place_idx % len(places)]
        activities.append({
            "time": time,
            "type": "attraction",
            "title": place.get("name", "Suggested place"),
            "description": place.get("description", "Place listing; confirm details before visiting."),
            "source": place.get("source", "unknown"),
        })
    else:
        activities.append({
            "time": time,
            "type": "free_time",
            "title": "Flexible time",
            "description": "No verified place listings are available for this destination.",
        })


def _append_meal_or_break(activities, meal_type, time, meal):
    if meal:
        title = f"{meal_type.title()} suggestion: {meal.get('name', 'Local option')}"
        description = (
            f"{meal.get('dish', 'Meal suggestion')}. "
            "Confirm current hours, availability, and prices before visiting."
        )
        source = meal.get("source", "curated")
    else:
        title = f"{meal_type.title()} break"
        description = "Restaurant search and current venue availability are not connected."
        source = "unavailable"
    activities.append({
        "time": time,
        "type": "food",
        "title": title,
        "description": description,
        "source": source,
    })


def _get_cultural_safety_guide(destination: str) -> dict:
    return {
        "status": "not_configured",
        "note": "Official destination-specific emergency contacts, safety alerts, and local rules are not connected. Verify them with government sources before travel.",
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
