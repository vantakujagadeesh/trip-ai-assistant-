"""
MCP Tool: Currency Conversion
Uses ExchangeRate-API (free tier: 1500 req/month, no credit card)
Falls back to cached approximate rates if API unavailable.
"""
import os
import httpx
from typing import Optional
from datetime import datetime, timedelta


# Cached rates (refreshed from API, used as fallback)
_rates_cache: dict = {}
_cache_time: Optional[datetime] = None
CACHE_TTL_HOURS = 6

# Static fallback rates (INR base, approximate mid-2026 rates)
FALLBACK_RATES_FROM_USD = {
    "INR": 83.5, "USD": 1.0, "EUR": 0.93, "GBP": 0.79,
    "JPY": 155.0, "SGD": 1.35, "AED": 3.67, "THB": 36.0,
    "IDR": 16200.0, "MYR": 4.7, "AUD": 1.55, "CAD": 1.37,
    "CHF": 0.90, "NZD": 1.65, "HKD": 7.8,
}


async def convert_currency(
    amount: float,
    from_currency: str,
    to_currency: str,
) -> dict:
    """
    Convert currency amounts for travel budget planning.

    Args:
        amount: amount to convert
        from_currency: source currency code (e.g., 'INR', 'USD', 'EUR')
        to_currency: target currency code

    Returns:
        dict with converted amount and exchange rate
    """
    from_cur = from_currency.upper().strip()
    to_cur = to_currency.upper().strip()

    if from_cur == to_cur:
        return {
            "amount": amount,
            "from": from_cur,
            "to": to_cur,
            "converted": amount,
            "rate": 1.0,
        }

    rate = await _get_rate(from_cur, to_cur)
    if not rate:
        return {"error": f"Rate for {from_cur}/{to_cur} unavailable", "converted": None}

    converted = round(amount * rate, 2)
    return {
        "amount": amount,
        "from": from_cur,
        "to": to_cur,
        "converted": converted,
        "rate": round(rate, 4),
        "formatted": f"{converted:,.2f} {to_cur}",
        "travel_note": _travel_note(from_cur, to_cur, converted),
    }


async def _get_rate(from_cur: str, to_cur: str) -> Optional[float]:
    """Get exchange rate, using cache or API."""
    global _rates_cache, _cache_time

    # Try refreshing cache from API
    api_key = os.getenv("EXCHANGE_RATE_API_KEY", "")
    if api_key and api_key != "your_exchange_rate_key_here":
        if not _cache_time or datetime.now() - _cache_time > timedelta(hours=CACHE_TTL_HOURS):
            try:
                async with httpx.AsyncClient(timeout=8) as client:
                    resp = await client.get(
                        f"https://v6.exchangerate-api.com/v6/{api_key}/latest/USD"
                    )
                    if resp.status_code == 200:
                        _rates_cache = resp.json().get("conversion_rates", {})
                        _cache_time = datetime.now()
            except Exception:
                pass

    # Use live rates if available
    if _rates_cache:
        from_usd = _rates_cache.get(from_cur)
        to_usd = _rates_cache.get(to_cur)
        if from_usd and to_usd:
            return to_usd / from_usd

    # Fallback to static rates
    from_usd = FALLBACK_RATES_FROM_USD.get(from_cur)
    to_usd_rate = FALLBACK_RATES_FROM_USD.get(to_cur)
    if from_usd and to_usd_rate:
        return to_usd_rate / from_usd

    return None


def _travel_note(from_cur: str, to_cur: str, converted: float) -> str:
    if from_cur == "INR" and to_cur == "EUR":
        return f"€{converted:.0f} — great for a European dinner (avg meal €15-25)"
    if from_cur == "INR" and to_cur == "JPY":
        return f"¥{converted:.0f} — covers ~{int(converted/1000)} convenience store meals in Tokyo"
    if from_cur == "USD" and to_cur == "INR":
        return f"₹{converted:.0f} — good value in India (avg meal ₹200-500)"
    return f"Converted at current market rates"


async def get_travel_budget_breakdown(
    total_budget_inr: float,
    destination: str,
    days: int,
) -> dict:
    """
    Break down a travel budget into recommended allocations.

    Args:
        total_budget_inr: total budget in INR
        destination: destination city/country
        days: number of travel days

    Returns:
        dict with suggested budget allocation by category
    """
    per_day = total_budget_inr / max(days, 1)
    return {
        "total_inr": total_budget_inr,
        "per_day_inr": round(per_day, 0),
        "recommended_allocation": {
            "flights": round(total_budget_inr * 0.30, 0),
            "accommodation": round(total_budget_inr * 0.35, 0),
            "food": round(total_budget_inr * 0.15, 0),
            "activities": round(total_budget_inr * 0.12, 0),
            "transport_local": round(total_budget_inr * 0.05, 0),
            "misc_shopping": round(total_budget_inr * 0.03, 0),
        },
        "tip": f"Budget of ₹{per_day:.0f}/day for {destination} — {'tight but doable' if per_day < 3000 else 'comfortable' if per_day < 8000 else 'generous — enjoy the luxury!'}",
    }
