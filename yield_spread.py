### yield_spread.py — 10Y Yield Spread (Base vs Quote)

import httpx
import asyncio
from config import FMP_API_KEY, FRED_API_KEY

# FRED tickers for G10 countries
FRED_SERIES_10Y = {
    "GBP": "IRLTLT01GBM156N",
    "EUR": "IRLTLT01EZM156N",
    "JPY": "IRLTLT01JPM156N",
    "AUD": "IRLTLT01AUM156N",
    "CAD": "IRLTLT01CAM156N",
}

async def fetch_us_yield():
    url = f"https://financialmodelingprep.com/api/v4/treasury?maturity=10Y&apikey={FMP_API_KEY}"
    async with httpx.AsyncClient(timeout=6) as c:
        r = await c.get(url)
        r.raise_for_status()
    return float(r.json()[0]["year10"])

async def fetch_fred_yield(series_id):
    url = (
        f"https://api.stlouisfed.org/fred/series/observations"
        f"?series_id={series_id}&api_key={FRED_API_KEY}&file_type=json&sort_order=desc&limit=1"
    )
    async with httpx.AsyncClient(timeout=6) as c:
        r = await c.get(url)
        r.raise_for_status()
    return float(r.json()["observations"][0]["value"])

def get_yield_spread(base: str, quote: str) -> dict:
    async def _spread():
        try:
            y_base = await (fetch_us_yield() if base == "USD" else fetch_fred_yield(FRED_SERIES_10Y[base]))
            y_quote = await (fetch_us_yield() if quote == "USD" else fetch_fred_yield(FRED_SERIES_10Y[quote]))
            diff = round(y_base - y_quote, 2)
            return {
                "cross_10": diff,  # + means base > quote
                "momentum": "widening" if diff > 0 else "narrowing"
            }
        except Exception as e:
            print(f"⚠️ Yield spread error ({base}/{quote}): {e}")
            return {"cross_10": 0.0, "momentum": "neutral"}

    return asyncio.run(_spread())