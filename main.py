print("⚙️ main.py has started execution", flush=True)

import requests
import pandas as pd
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bs4 import BeautifulSoup
import time
import os
import sys
import numpy as np  # Already in your code, but make sure it's there
import io
import cot_reports as cot



from dotenv import load_dotenv
load_dotenv()          # <- pulls variables from .env

print(f"🛠 Running Python version: {sys.version}", flush=True)

# ---- scoring weights -----------------------------------------
WEIGHTS = {
    "CB tone divergence hawk→dove": 1.0,
    "CB tone divergence dove→hawk": 1.0,      # treat both directions equal
    "Yield spread":                 1.0,      # string assembled later
    "COT extreme":                  1.5,
    "Retail crowd on wrong side":   1.0,
    "Inter-market correlation confirmed": 1.0,
    "Major S/R break or clean pattern": 0.5,
    "Catalyst aligns":              0.5,
}
SCORE_THRESHOLD = 4            # ~equivalent to 4 “strong” ticks

# --- CONFIG (pulled from .env) ---------------------------------
from dotenv import load_dotenv
load_dotenv()                       # ← keep this near the imports

EMAIL_SENDER   = os.getenv("EMAIL_SENDER", "benjihornetrades@gmail.com")
EMAIL_PASS     = os.getenv("EMAIL_PASS")           # Gmail app-password
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "benhorne6@gmail.com")

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT   = 587

LOG_FILE = "trade_log.csv"

TE_KEY         = os.getenv("TE_KEY")               # TradingEconomics
FMP_API_KEY    = os.getenv("FMP_API_KEY")
FRED_API_KEY   = os.getenv("FRED_API_KEY")
QUANDL_API_KEY = os.getenv("QUANDL_API_KEY")       # safe to keep even if unused


TRADE_PAIRS = [
    ("GBP/USD", "GBP", "USD"),
    ("USD/JPY", "USD", "JPY"),
    ("USD/CAD", "USD", "CAD"),
    ("AUD/USD", "AUD", "USD"),
    ("GBP/JPY", "GBP", "JPY"),
    ("EUR/USD", "EUR", "USD"),  # Optional: Keep if you want one slower, bigger liquidity pair
]



RUN_INTERVAL_SECONDS = 21600  # Scan every 6 hours (6 * 60 * 60 seconds) to stay well within free API limits


# --- API Health Check -----------------------------------------

def api_health_check():
    try:
        test_url = f"https://financialmodelingprep.com/api/v3/quote/AAPL?apikey={FMP_API_KEY}"
        res = requests.get(test_url)
        if res.status_code == 200:
            print("✅ API health check passed.")
            return True
        else:
            print(f"⚠️ API health check failed: {res.status_code}")
            return False
    except Exception as e:
        print(f"⚠️ API health check exception: {e}")
        return False


# --- DATA FUNCTIONS ---

# ── COT CONTRACT MAPPINGS ─────────────────────────────────────
import cot_reports as cot
import numpy as np

def get_cot_positioning(currency):
    try:
        # Load legacy futures data instead of disaggregated
        df = cot.cot_all('legacy_fut', verbose=False)

        # Check available contract names (optional for debugging)
        # print(df['Market and Exchange Names'].dropna().unique())

        # Correct contract mapping for legacy_fut dataset
        contract_map = {
            "EUR": "EURO FX - CHICAGO MERCANTILE EXCHANGE",
            "GBP": "BRITISH POUND STERLING - CHICAGO MERCANTILE EXCHANGE",
            "JPY": "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE",
            "AUD": "AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE",
            "CAD": "CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE"
        }

        contract_name = contract_map.get(currency.upper())
        if not contract_name:
            print(f"❌ No contract mapping found for {currency}")
            return {"net_spec_position": 0, "extreme_zscore": 0.0, "sentiment_reversal": False}

        cot_filtered = df[df['Market and Exchange Names'].str.contains(contract_name, case=False)]

        if cot_filtered.empty:
            print(f"⚠️ No COT data found for {currency} (contract: {contract_name})")
            return {"net_spec_position": 0, "extreme_zscore": 0.0, "sentiment_reversal": False}

        cot_filtered = cot_filtered.sort_values("As of Date in Form YYYY-MM-DD")

        net_spec = cot_filtered['Noncommercial Positions-Long (All)'] - cot_filtered['Noncommercial Positions-Short (All)']
        latest_net = net_spec.iloc[-1]
        zscore = ((latest_net - net_spec.mean()) / net_spec.std()).round(2)

        return {
            "net_spec_position": int(latest_net),
            "extreme_zscore": float(zscore),
            "sentiment_reversal": bool(abs(zscore) > 1.5)
        }

    except Exception as e:
        print(f"⚠️ COT fetch error for {currency.upper()}: {e}")
        return {"net_spec_position": 0, "extreme_zscore": 0.0, "sentiment_reversal": False}






# ----- LIVE 10-year cross-country spread (TradingEconomics) -----
import httpx, asyncio, os

TE_KEY = os.getenv("TE_KEY", "guest:guest")

BONDS = {  # G-10 10-year symbols
    "USD": "us10y",
    "GBP": "gb10y",
    "EUR": "germany10y",
    "JPY": "jp10y",
    "AUD": "au10y",
    "CAD": "ca10y",
}

async def _bond(code):
    url = f"https://api.tradingeconomics.com/bonds/{code}?c={TE_KEY}&f=json"
    async with httpx.AsyncClient(timeout=6) as c:
        r = await c.get(url)
        r.raise_for_status()
    return float(r.json()[0]["value"])

# ---- robust 10-year cross-country spread ----------------------
import httpx, asyncio, os, datetime, json, time

TE_KEY      = os.getenv("TE_KEY", "guest:guest")
FMP_API_KEY = os.getenv("FMP_API_KEY")

# TradingEconomics tickers for 10-year gov bonds
TE_TICKER = {
    "GBP": "unitedkingdomgovernmentbond10y",
    "EUR": "germanygovernmentbondbund10y",
    "JPY": "japangovernmentbond10y",
    "AUD": "australiagovernmentbond10y",
    "CAD": "canadagovernmentbond10y",
}

async def te_yield(ccy):
    code = TE_TICKER[ccy]
    url  = f"https://api.tradingeconomics.com/bonds/{code}?c={TE_KEY}&f=json"
    async with httpx.AsyncClient(timeout=6) as c:
        r = await c.get(url)
        r.raise_for_status()
    return float(r.json()[0]["value"])

async def us_yield():
    url = f"https://financialmodelingprep.com/api/v4/treasury?maturity=10Y&apikey={FMP_API_KEY}"
    async with httpx.AsyncClient(timeout=6) as c:
        r = await c.get(url)
        r.raise_for_status()
    return float(r.json()[0]["year10"])

# -------- robust cross-country 10-year spread (USD live, others EoD) -----
import httpx, asyncio, os, datetime, json

FMP_API_KEY  = os.getenv("FMP_API_KEY")
FRED_API_KEY = os.getenv("FRED_API_KEY")

FRED_SERIES_10Y = {
    "GBP": "IRLTLT01GBM156N",   # UK 10-yr constant-maturity
    "EUR": "IRLTLT01EZM156N",   # Euro area
    "JPY": "IRLTLT01JPM156N",   # Japan
    "AUD": "IRLTLT01AUM156N",   # Australia
    "CAD": "IRLTLT01CAM156N",   # Canada
}

async def us_10y():
    url = f"https://financialmodelingprep.com/api/v4/treasury?maturity=10Y&apikey={FMP_API_KEY}"
    async with httpx.AsyncClient(timeout=6) as c:
        r = await c.get(url); r.raise_for_status()
    return float(r.json()[0]["year10"])

async def fred_10y(series):
    url = (
        "https://api.stlouisfed.org/fred/series/observations"
        f"?series_id={series}&api_key={FRED_API_KEY}&file_type=json&sort_order=desc&limit=1"
    )
    async with httpx.AsyncClient(timeout=6) as c:
        r = await c.get(url); r.raise_for_status()
    return float(r.json()["observations"][0]["value"])

def get_yield_spread(base, quote):
    async def _spread():
        y_base  = await (us_10y() if base  == "USD" else fred_10y(FRED_SERIES_10Y[base]))
        y_quote = await (us_10y() if quote == "USD" else fred_10y(FRED_SERIES_10Y[quote]))
        diff = round(y_base - y_quote, 2)
        return {
            "cross_10": diff,                    # + => base yield higher
            "momentum": "widening" if diff > 0 else "narrowing"
        }
    return asyncio.run(_spread())

# ---- live CB tone via RSS headlines ---------------------------
import feedparser, datetime

RSS_FEEDS = {
    "USD": ["https://www.federalreserve.gov/feeds/press_all.xml"],
    "GBP": ["https://www.bankofengland.co.uk/boeapps/RSSFeeds/Pages/News.xml"],
    "EUR": ["https://www.ecb.europa.eu/rss/press.html"],
    "JPY": ["https://www.boj.or.jp/en/announcements/release_2024.xml"],
    "AUD": ["https://www.rba.gov.au/rss/media-releases.xml"],
    "CAD": ["https://www.bankofcanada.ca/feeds/speeches"],
}

HAWKISH = ("hike", "tighten", "restrictive", "inflation too high")
DOVISH  = ("cut", "ease", "accommodative", "downside risk")

def get_central_bank_tone(ccy):
    texts = []
    today = datetime.datetime.utcnow().date()
    for url in RSS_FEEDS.get(ccy, []):
        for entry in feedparser.parse(url).entries[:5]:
            ts = datetime.datetime(*entry.published_parsed[:6]).date()
            if ts == today:
                title = entry.title if hasattr(entry, "title") else ""
                summary = getattr(entry, "summary", "")
                texts.append((title + " " + summary).lower())

    blob = " ".join(texts)
    if any(k in blob for k in HAWKISH):
        return {"tone": "hawkish"}
    if any(k in blob for k in DOVISH):
        return {"tone": "dovish"}
    return {"tone": "neutral"}
# ----------------------------------------------------------------

# ------------------------------------------------------------------------

def get_retail_sentiment(pair):
    url = "https://www.ig.com/au/trading-strategies/client-sentiment"
    try:
        page = requests.get(url)
        soup = BeautifulSoup(page.content, "html.parser")
        tables = soup.find_all("table")
        for table in tables:
            if pair.replace("/", "") in table.text.replace(" ", ""):
                rows = table.find_all("tr")
                for row in rows:
                    if "Long" in row.text:
                        long_percent = int(row.find_all("td")[1].text.replace("%", "").strip())
                    if "Short" in row.text:
                        short_percent = int(row.find_all("td")[1].text.replace("%", "").strip())
                retail_against = long_percent > 75 or short_percent > 75
                return {"long_percent": long_percent, "retail_against": retail_against}
        return {"long_percent": 50, "retail_against": False}
    except:
        return {"long_percent": 50, "retail_against": False}



cached_assets = {}

def fetch_change(symbol, label):
    try:
        if symbol in cached_assets:
            return cached_assets[symbol]
        url = f"https://financialmodelingprep.com/api/v3/quote/{symbol}?apikey={FMP_API_KEY}"
        res = requests.get(url).json()
        if not res or not isinstance(res, list) or "changesPercentage" not in res[0]:
            print(f"⚠️ Intermarket data not available for {symbol}", flush=True)
            return None
        change = float(res[0]["changesPercentage"])
        cached_assets[symbol] = change
        print(f"🔢 {label} change: {change:.2f}%", flush=True)
        return change
    except Exception as e:
        print(f"⚠️ Intermarket fetch error for {symbol}: {e}", flush=True)
        return None


def get_intermarket_agreement(pair):
    try:
        base, quote = pair.split("/")
        confluences = []

        fallback_map = {
            "^FTSE": "UKX.L",
            "^GDAXI": "DAX",
            "^VIX": "VIXY",
            "000001.SS": "SSEC",
            "GC=F": "GOLD",
            "CL=F": "WTI_OIL",
            "HG=F": "COPPER"
        }

        asset_map = {
            "CAD": ("CL=F", "Crude Oil"),
            "AUD": ("HG=F", "Copper"),
            "CHF": ("GC=F", "Gold"),
            "JPY": ("GC=F", "Gold"),
            "JPY_VIX": ("^VIX", "VIX"),
            "CHF_VIX": ("^VIX", "VIX"),
            "AUD_CHINA": ("000001.SS", "Shanghai Index"),
            "USD": ("DX-Y.NYB", "US Dollar Index (DXY)"),
            "EUR": ("^GDAXI", "German DAX Index"),
            "GBP": ("^FTSE", "FTSE 100 Index")
        }

        for side in [base, quote]:
            if side in asset_map:
                symbol, label = asset_map[side]
                change = fetch_change(symbol, label)
                if change is None and symbol in fallback_map:
                    symbol_fallback = fallback_map[symbol]
                    change = fetch_change(symbol_fallback, label + " (fallback)")
                if change is not None:
                    if side == base and change > 0.5:
                        confluences.append(f"{side} supported by {label}")
                    elif side == quote and change < -0.5:
                        confluences.append(f"{side} weakness from {label}")
            else:
                print(f"❌ No intermarket logic for {side}", flush=True)

        if base in ["JPY", "CHF"] or quote in ["JPY", "CHF"]:
            vix = fetch_change("^VIX", "VIX Proxy")
            if vix is None:
                vix = fetch_change("VIXY", "VIXY ETF")
            if vix is not None and vix > 2:
                if base in ["JPY", "CHF"]:
                    confluences.append(f"{base} supported by risk-off (VIX ↑)")
                if quote in ["JPY", "CHF"]:
                    confluences.append(f"{quote} weakness from risk-off (VIX ↑)")

        if base == "AUD":
            china = fetch_change("000001.SS", "Shanghai Index")
            if china is None:
                china = fetch_change("SSEC", "Shanghai Comp (alt)")
            if china is not None and china > 0.5:
                confluences.append("AUD strength from China optimism")

        if confluences:
            print(f"✅ Intermarket agreement confirmed: {' & '.join(confluences)}", flush=True)
            return True
        else:
            print("❌ No intermarket alignment confirmed", flush=True)
            return False
    except Exception as e:
        print(f"⚠️ Intermarket agreement error: {e}", flush=True)
        return False




import numpy as np  # Make sure this is at the top of your file

# --- LIVE TECHNICAL PATTERN DETECTION ---
def get_technical_pattern(pair):
    try:
        base, quote = pair.split("/")
        symbol = f"{base}{quote}=X"
        url = f"https://financialmodelingprep.com/api/v3/historical-chart/4hour/{symbol}?apikey={FMP_API_KEY}"
        res = requests.get(url).json()
        df = pd.DataFrame(res)

        if df.empty or "close" not in df.columns:
            return {"key_level_broken": False, "clean_pattern": "data unavailable"}

        df["datetime"] = pd.to_datetime(df["date"])
        df.set_index("datetime", inplace=True)
        closes = df["close"].sort_index()

        if len(closes) < 30:
            return {"key_level_broken": False, "clean_pattern": "not enough data"}

        recent = closes[-20:]
        ma = recent.rolling(window=10).mean()

        if recent.iloc[-1] > ma.iloc[-1] and recent.iloc[-2] < ma.iloc[-2]:
             return {"key_level_broken": True, "clean_pattern": "bullish breakout"}
        elif recent.iloc[-1] < ma.iloc[-1] and recent.iloc[-2] > ma.iloc[-2]:
             return {"key_level_broken": True, "clean_pattern": "bearish breakdown"}


        return {"key_level_broken": False, "clean_pattern": "range-bound"}

    except Exception as e:
        print(f"⚠️ Technical pattern detection error: {e}", flush=True)
        return {"key_level_broken": False, "clean_pattern": "error"}




def get_upcoming_catalyst(pair):
    try:
        base, quote = pair.split("/")
        currencies = [base, quote]

        url = f"https://financialmodelingprep.com/api/v3/economic_calendar?apikey={FMP_API_KEY}"
        res = requests.get(url)
        if res.status_code != 200:
            print(f"⚠️ Catalyst fetch error: {res.status_code}")
            return {"event": None, "bias_alignment": False}

        data = res.json()
        now = datetime.datetime.utcnow()
        upcoming = []

        for event in data:
            try:
                event_time = datetime.datetime.strptime(event["date"], "%Y-%m-%d %H:%M:%S")
                if now <= event_time <= now + datetime.timedelta(hours=48):
                    if event.get("country") in currencies or event.get("currency") in currencies:
                        upcoming.append(event.get("event", "Unknown Event"))
            except Exception:
                continue

        if upcoming:
            return {"event": ", ".join(upcoming), "bias_alignment": True}
        else:
            return {"event": None, "bias_alignment": False}

    except Exception as e:
        print(f"⚠️ Catalyst fetch error: {e}")
        return {"event": None, "bias_alignment": False}


# ───────────────── EMAIL & JOURNAL WITH WEIGHTED SCORE ─────────────
def send_email_alert(pair, checklist, direction, score):
    """Send bias alert only when weighted score >= SCORE_THRESHOLD."""
    if score < SCORE_THRESHOLD:
        print(f"❌ Email BLOCKED — score {score:.1f} / {SCORE_THRESHOLD}")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[{direction.upper()}] {pair} — {score:.1f}-pt bias"
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    # Format checklist items
    passed = [item for item in checklist if item.startswith("✅")]
    failed = [item for item in checklist if item.startswith("❌")]

    html = f"""
    <html><body style='font-family:Arial'>
        <h2>📈 {pair} bias triggered</h2>
        <p><b>Direction:</b> {'LONG' if direction == 'long' else 'SHORT'}</p>
        <p><b>Weighted score:</b> {score:.1f} / {SCORE_THRESHOLD}</p>

        <h3 style='color:green'>✅ Passed Checklist</h3>
        <ul>{''.join(f'<li>{item[2:]}</li>' for item in passed)}</ul>

        <h3 style='color:red'>❌ Failed Checklist</h3>
        <ul>{''.join(f'<li>{item[2:]}</li>' for item in failed)}</ul>

        <p style='font-size:13px;margin-top:10px'>🎯 Manually check LTF structure & SL/TP</p>
        <p style='font-size:12px;color:#888'>UTC: {datetime.datetime.utcnow():%Y-%m-%d %H:%M:%S}</p>
    </body></html>
    """

    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASS)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())

def log_trade(pair, checklist, score):
    df = pd.DataFrame([{
        "timestamp": datetime.datetime.utcnow(),
        "pair": pair,
        "checklist": " | ".join(checklist),
        "score": score
    }])
    try:
        existing = pd.read_csv(LOG_FILE)
        df = pd.concat([existing, df], ignore_index=True)
    except FileNotFoundError:
        pass
    df.to_csv(LOG_FILE, index=False)
# ───────────────────────────────────────────────────────────────────

def precision_filters(pair, base_ccy, quote_ccy, direction):
    now_utc = datetime.datetime.utcnow()

    # 1. Time of Day Filter
    if not (8 <= now_utc.hour <= 16):
        print(f"❌ Skipping {pair} — Outside optimal trading hours ({now_utc.hour}:00 UTC)")
        return False

    # 2. Volatility Filter (ATR)
    try:
        url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{base_ccy}{quote_ccy}=X?serietype=line&timeseries=20&apikey={FMP_API_KEY}"
        res = requests.get(url).json()
        closes = [float(day['close']) for day in res['historical']]
        atr = np.mean([abs(closes[i] - closes[i-1]) for i in range(1, len(closes))])
        minimum_atr_threshold = 0.0025
        if atr < minimum_atr_threshold:
            print(f"❌ Skipping {pair} — Volatility too low (ATR={atr:.5f})")
            return False
    except Exception as e:
        print(f"⚠️ ATR fetch error for {pair}: {e}")
        return False

    # 3. Higher Timeframe Trend Filter (Daily 50 MA)
    try:
        url = f"https://financialmodelingprep.com/api/v3/historical-chart/1hour/{base_ccy}{quote_ccy}=X?apikey={FMP_API_KEY}"
        res = requests.get(url).json()
        df = pd.DataFrame(res)
        df['datetime'] = pd.to_datetime(df['date'])
        df.set_index('datetime', inplace=True)
        closes = df['close'].sort_index()
        closes_daily = closes.resample('D').last().dropna()

        if len(closes_daily) < 60:
            print(f"⚠️ Not enough daily data for {pair} to check trend")
            return False

        ma50 = closes_daily.rolling(window=50).mean()
        last_close = closes_daily.iloc[-1]
        last_ma50 = ma50.iloc[-1]

        daily_trend = "long" if last_close > last_ma50 else "short"
        if daily_trend != direction:
            print(f"❌ Skipping {pair} — Daily trend mismatch ({daily_trend.upper()} vs {direction.upper()})")
            return False
    except Exception as e:
        print(f"⚠️ Trend fetch error for {pair}: {e}")
        return False

    # 4. Structural Level Breakout Filter (10-day High/Low)
    try:
        recent_high = closes_daily[-10:].max()
        recent_low = closes_daily[-10:].min()
        last_close = closes_daily.iloc[-1]

        if direction == "long" and last_close < recent_high:
            print(f"❌ Skipping {pair} — No breakout above recent high ({last_close:.5f} vs {recent_high:.5f})")
            return False
        if direction == "short" and last_close > recent_low:
            print(f"❌ Skipping {pair} — No breakdown below recent low ({last_close:.5f} vs {recent_low:.5f})")
            return False
    except Exception as e:
        print(f"⚠️ Structure level check error for {pair}: {e}")
        return False

    # 5. DXY Context Filter (for USD pairs)
    if "USD" in [base_ccy, quote_ccy]:
        try:
            dxy_url = f"https://financialmodelingprep.com/api/v3/historical-price-full/DXY?serietype=line&timeseries=10&apikey={FMP_API_KEY}"
            dxy_res = requests.get(dxy_url).json()
            dxy_closes = [float(day['close']) for day in dxy_res['historical']]
            dxy_trend = "up" if dxy_closes[-1] > dxy_closes[-5] else "down"

            if base_ccy == "USD" and direction == "short" and dxy_trend == "up":
                print(f"❌ Skipping {pair} — USD strength contradicts SHORT idea")
                return False

            if quote_ccy == "USD" and direction == "long" and dxy_trend == "up":
                print(f"❌ Skipping {pair} — USD strength contradicts LONG idea")
                return False
        except Exception as e:
            print(f"⚠️ DXY fetch error for {pair}: {e}")
            return False

    # ✅ If ALL filters pass
    return True


def is_volatility_sufficient(pair):
    try:
        base, quote = pair.split("/")
        symbol = f"{base}{quote}=X"

        url = f"https://financialmodelingprep.com/api/v3/historical-chart/4hour/{symbol}?apikey={FMP_API_KEY}"
        res = requests.get(url)
        if res.status_code != 200:
            print(f"⚠️ ATR fetch error for {pair}")
            return True  # Fail safe: assume volatility is fine

        df = pd.DataFrame(res.json())
        if df.empty or "close" not in df.columns:
            return True  # Fail safe: assume volatility fine

        df["datetime"] = pd.to_datetime(df["date"])
        df.set_index("datetime", inplace=True)
        closes = df["close"].sort_index()

        # Calculate ATR(14) manually on 4H data
        df["H-L"] = df["high"] - df["low"]
        df["H-PC"] = abs(df["high"] - df["close"].shift(1))
        df["L-PC"] = abs(df["low"] - df["close"].shift(1))
        df["TR"] = df[["H-L", "H-PC", "L-PC"]].max(axis=1)
        df["ATR"] = df["TR"].rolling(window=14).mean()

        latest_atr = df["ATR"].iloc[-1]
        latest_close = closes.iloc[-1]

        atr_percent = (latest_atr / latest_close) * 100

        # Minimum acceptable volatility (adjust if needed)
        if atr_percent >= 0.3:
            return True
        else:
            print(f"⚠️ Skipping {pair} — 4H volatility too low ({atr_percent:.2f}%)")
            return False

    except Exception as e:
        print(f"⚠️ Error in 4H volatility check for {pair}: {e}")
        return True  # Fail safe: assume volatility is fine if error

def is_in_killzone():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=10)))  # AEST timezone
    current_hour = now.hour
    return 17 <= current_hour <= 22  # 17 = 5PM, 22 = 10PM

def scan_trade_opportunity(pair, base_ccy, quote_ccy):
    if not api_health_check():
        print(f"⚠️ Skipping scan for {pair} — API unhealthy.")
        return

    if not is_in_killzone():
        print(f"⚠️ Skipping {pair} — outside kill zone hours (5 PM–10 PM AEST)")
        return

    if not is_volatility_sufficient(pair):
        return

    checklist = []
    base_strength = 0
    quote_strength = 0

    # Central Bank Tone
    tone_base = get_central_bank_tone(base_ccy)["tone"]
    tone_quote = get_central_bank_tone(quote_ccy)["tone"]

    if tone_base == "hawkish" and tone_quote == "dovish":
        key = "CB tone divergence hawk→dove"
        checklist.append(key)
        base_strength += 1
    elif tone_base == "dovish" and tone_quote == "hawkish":
        key = "CB tone divergence dove→hawk"
        checklist.append(key)
        quote_strength += 1

    # Yield Spread
    spread = get_yield_spread(base_ccy, quote_ccy)
    if abs(spread["cross_10"]) >= 30 and spread["momentum"] == "widening":
        key = "Yield spread"
        line = f"{key} +{spread['cross_10']} bp widening"
        checklist.append(line)
        if spread["cross_10"] > 0:
            base_strength += 1
        else:
            quote_strength += 1

    # Retail Sentiment
    sentiment = get_retail_sentiment(pair)
    if sentiment["retail_against"]:
        key = "Retail crowd on wrong side"
        checklist.append(key)

    # Intermarket
    if get_intermarket_agreement(pair):
        key = "Inter-market correlation confirmed"
        checklist.append(key)

    # Technical Pattern
    if get_technical_pattern(pair)["key_level_broken"]:
        key = "Major S/R break or clean pattern"
        checklist.append(key)

    # Catalyst
    catalyst = get_upcoming_catalyst(pair)
    if catalyst["bias_alignment"]:
        key = "Catalyst aligns"
        line = f"{key}: {catalyst['event']}"
        checklist.append(line)

    # ✅ COT — ENABLED
    cot = get_cot_positioning(base_ccy)
    if abs(cot["extreme_zscore"]) > 1.5:
        key = "COT extreme"
        line = f"{key}: z={cot['extreme_zscore']:.1f}"
        checklist.append(line)

    # Weighted Score
    score = 0.0
    for item in checklist:
        key = item.split(":")[0].split("+")[0].strip()
        score += WEIGHTS.get(key, 0)

    print("\n========= SCAN RESULT =========")
    print(f"Pair: {pair}")
    for item in checklist:
        print(f"✅ {item}")
    print(f"Weighted score: {score:.1f}")

    direction = "long" if base_strength >= quote_strength else "short"

    if score >= SCORE_THRESHOLD:
        print(f"✅ TRADE VALIDATED ({score:.1f} pts, {direction.upper()} {pair})")
        send_email_alert(pair, checklist, direction, score)
        log_trade(pair, checklist, score)
    else:
        print(f"❌ Not enough score ({score:.1f} / {SCORE_THRESHOLD})")

    print(f"📢 Direction Bias (based on checklist strength): {direction.upper()} {pair}")

# ───────────────────────────────────────────────────────────────
# Weighted checklist configuration
# ----------------------------------------------------------------
WEIGHTS = {
    "CB tone divergence hawk→dove":           1.0,
    "CB tone divergence dove→hawk":           1.0,
    "Yield spread":                           1.0,
    "COT extreme":                            1.5,   # when re-enabled
    "Retail crowd on wrong side":             1.0,
    "Inter-market correlation confirmed":     1.0,
    "Major S/R break or clean pattern":       0.5,
    "Catalyst aligns":                        0.5,
}

SCORE_THRESHOLD = 4        # minimum weighted points to validate a trade
# ───────────────────────────────────────────────────────────────
def auto_run_dashboard():
    print("🚀 __main__ reached — scheduled scan mode active", flush=True)
    scanned_hours_today = set()

    while True:
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=10)))  # AEST
        current_time = now.strftime("%H:%M")

        # Reset scanned hours at midnight
        if current_time == "00:00":
            scanned_hours_today.clear()

        # Scan exactly at every new hour
        if now.minute == 0 and now.hour not in scanned_hours_today:
            print(f"\n🕕 Running scheduled scan at {current_time} AEST", flush=True)
            print(f"[SCAN START] {datetime.datetime.utcnow()} UTC", flush=True)

            for pair, base, quote in TRADE_PAIRS:
                try:
                    scan_trade_opportunity(pair, base, quote)
                except Exception as e:
                    print(f"⚠️ Error during scan: {e}", flush=True)
                print("---------------------------------------", flush=True)

            scanned_hours_today.add(now.hour)

        time.sleep(60)

if __name__ == "__main__":
    auto_run_dashboard()
