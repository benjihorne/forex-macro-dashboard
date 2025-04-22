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

print(f"🛠 Running Python version: {sys.version}", flush=True)

# --- CONFIG ---
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "benjihornetrades@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "Ben135790!")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "benhorne6@gmail.com")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
LOG_FILE = "trade_log.csv"
QUANDL_API_KEY = os.getenv("QUANDL_API_KEY", "5aMXd383niMqhxwRic-2")  # ✅ New Nasdaq API Key
FRED_API_KEY = os.getenv("FRED_API_KEY", "03041666822ce885ee3462500fa93cd5")
FMP_API_KEY = "czVnLpLUT3GA7bsOP6yci0eMStqe3hPQ"

TRADE_PAIRS = [
    ("GBP/USD", "GBP", "USD"),
    ("EUR/USD", "EUR", "USD"),
    ("USD/JPY", "USD", "JPY"),
    ("USD/CAD", "USD", "CAD"),
    ("AUD/USD", "AUD", "USD"),
    ("NZD/USD", "NZD", "USD"),
    ("USD/CHF", "USD", "CHF"),
    ("EUR/GBP", "EUR", "GBP"),
    ("GBP/JPY", "GBP", "JPY")
]


RUN_INTERVAL_SECONDS = 21600  # Scan every 6 hours (6 * 60 * 60 seconds) to stay well within free API limits


CENTRAL_BANK_TONE = {
    "USD": "hawkish",
    "EUR": "neutral",
    "GBP": "hawkish",
    "JPY": "dovish",
    "AUD": "neutral",
    "CAD": "hawkish",
    "CHF": "neutral",
    "NZD": "neutral"
}


# --- DATA FUNCTIONS ---
def get_cot_positioning(currency):
    try:
        code_map = {
            "USD": None,
            "EUR": "CFTC/EU_F_L_ALL",
            "GBP": "CFTC/PO_F_L_ALL",
            "JPY": "CFTC/JY_F_L_ALL",
            "AUD": "CFTC/AU_F_L_ALL",
            "CAD": "CFTC/CD_F_L_ALL",
            "CHF": "CFTC/SF_F_L_ALL",
            "NZD": "CFTC/NE_F_L_ALL"
        }
        code = code_map.get(currency.upper())
        if not code:
            return {"net_spec_position": 0, "extreme_zscore": 0.0}
        
        url = f"https://data.nasdaq.com/api/v3/datasets/{code}.json?api_key={QUANDL_API_KEY}"
        response = requests.get(url)
        if response.status_code != 200:
            print(f"⚠️ COT fetch failed ({currency}): {response.status_code}")
            return {"net_spec_position": 0, "extreme_zscore": 0.0}
        
        data = response.json()["dataset"]["data"]
        df = pd.DataFrame(data, columns=response.json()["dataset"]["column_names"])
        spec_net = df["Net Position"] if "Net Position" in df.columns else df.iloc[:, -1]
        zscore = (spec_net.iloc[0] - spec_net.mean()) / spec_net.std()
        return {
            "net_spec_position": spec_net.iloc[0],
            "extreme_zscore": round(zscore, 2)
        }
    except Exception as e:
        print(f"⚠️ COT data fetch error for {currency}: {e}")
        return {"net_spec_position": 0, "extreme_zscore": 0.0}




def get_yield_spread(ccy1, ccy2):
    fred_series = {
        ("USD", "EUR"): ("DGS10", "IRLTLT01EZM156N"),
        ("USD", "GBP"): ("DGS10", "IRLTLT01GBM156N"),
        ("USD", "JPY"): ("DGS10", "IRLTLT01JPM156N"),
    }
    try:
        series_us, series_foreign = fred_series.get((ccy1, ccy2), (None, None))
        if not series_us or not series_foreign:
            return {"spread": 0.0, "momentum": "neutral"}
        url_us = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_us}&api_key={FRED_API_KEY}&file_type=json&sort_order=desc&limit=2"
        url_foreign = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_foreign}&api_key={FRED_API_KEY}&file_type=json&sort_order=desc&limit=2"
        data_us = requests.get(url_us).json()["observations"]
        data_foreign = requests.get(url_foreign).json()["observations"]
        us_now, us_prev = float(data_us[0]["value"]), float(data_us[1]["value"])
        f_now, f_prev = float(data_foreign[0]["value"]), float(data_foreign[1]["value"])
        spread_now = us_now - f_now
        spread_prev = us_prev - f_prev
        momentum = "rising" if spread_now > spread_prev else "falling" if spread_now < spread_prev else "neutral"
        return {"spread": round(spread_now, 2), "momentum": momentum}
    except:
        return {"spread": 0.0, "momentum": "neutral"}

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

def get_central_bank_tone(currency):
    tone = CENTRAL_BANK_TONE.get(currency.upper(), "neutral")
    recent_surprise = tone in ["hawkish", "dovish"]
    return {"tone": tone, "recent_surprise": recent_surprise}

FMP_API_KEY = "czVnLpLUT3GA7bsOP6yci0eMStqe3hPQ"

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
        url = f"https://financialmodelingprep.com/api/v3/historical-chart/5min/{symbol}?apikey={FMP_API_KEY}"
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
                    if event["country"] in currencies or event["currency"] in currencies:
                        upcoming.append(event["event"])
            except Exception:
                continue

        if upcoming:
            return {"event": ", ".join(upcoming), "bias_alignment": True}
        else:
            return {"event": None, "bias_alignment": False}

    except Exception as e:
        print(f"⚠️ Catalyst fetch error: {e}")
        return {"event": None, "bias_alignment": False}



def send_email_alert(pair, checklist, direction):
    confidence = len(checklist)
    print(f"[DEBUG] Attempting to send email: {pair}, confluences: {confidence}")
    if confidence < 4:
        print(f"❌ Email BLOCKED — only {confidence}/7 confluences for {pair}")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[{direction.upper()}] {pair} Trade Signal — {confidence}/7 Confluences"
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER
    html = f"""
    <html>
        <body style='font-family: Arial, sans-serif;'>
            <div style='max-width:600px;margin:auto;'>
                <h2 style='color:#1e90ff;'>📈 Trade Setup Triggered: {pair}</h2>
                <p><strong>📍 Direction:</strong> <span style='color:{'green' if direction == 'long' else 'red'};'>{direction.upper()}</span></p>
                <p><strong>✅ Confidence:</strong> {confidence}/7 confluences</p>
                <ul>{''.join(f'<li>✔️ {item}</li>' for item in checklist)}</ul>
                <p style='font-size: 12px; color: #888;'>UTC: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
        </body>
    </html>
    """
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())

def log_trade(pair, checklist):
    df = pd.DataFrame([{
        "timestamp": datetime.datetime.utcnow(),
        "pair": pair,
        "checklist": ", ".join(checklist),
        "confluences": len(checklist)
    }])
    try:
        existing = pd.read_csv(LOG_FILE)
        df = pd.concat([existing, df], ignore_index=True)
    except FileNotFoundError:
        pass
    df.to_csv(LOG_FILE, index=False)

def scan_trade_opportunity(pair, base_ccy, quote_ccy):
    checklist = []
    base_strength = 0
    quote_strength = 0
    tone = get_central_bank_tone(base_ccy)
    if tone['tone'] == 'hawkish':
        checklist.append("Macro favors base currency")
        base_strength += 1
    spread = get_yield_spread(base_ccy, quote_ccy)
    if spread['spread'] > 0 and spread['momentum'] == 'rising':
        checklist.append(f"Yield spread rising in favor: {spread['spread']}bps")
        base_strength += 1
    cot = get_cot_positioning(base_ccy)
    if abs(cot['extreme_zscore']) > 1.5:
        checklist.append(f"COT extreme position: z={cot['extreme_zscore']}")
    sentiment = get_retail_sentiment(pair)
    if sentiment['retail_against']:
        checklist.append("Retail is on wrong side")
    if get_intermarket_agreement(pair):
        checklist.append("Intermarket correlation confirmed")
    if get_technical_pattern(pair)['key_level_broken']:
        checklist.append("Major S/R break or clean pattern")
    catalyst = get_upcoming_catalyst(pair)
    if catalyst['bias_alignment']:
        checklist.append(f"Catalyst aligns: {catalyst['event']}")
    print("\n========= SCAN RESULT =========")
    print(f"Pair: {pair}")
    for item in checklist:
        print(f"✅ {item}")
    print(f"Total confluences: {len(checklist)}")
    direction = "long" if base_strength >= quote_strength else "short"
    if len(checklist) >= 2:
        print(f"✅ TRADE VALIDATED ({len(checklist)}/7, {direction.upper()} {pair})")
        send_email_alert(pair, checklist, direction)
        log_trade(pair, checklist)
    else:
        print("❌ Not enough edge for swing entry")

def auto_run_dashboard():
    print("🚀 __main__ reached — beginning bot loop", flush=True)
    while True:
        print("🌀 Loop tick...", flush=True)  # <-- ADD THIS
        print(f"\n[SCAN START] {datetime.datetime.utcnow()} UTC", flush=True)
        for pair, base, quote in TRADE_PAIRS:
            try:
                scan_trade_opportunity(pair, base, quote)
            except Exception as e:
                print(f"⚠️ Error during scan: {e}", flush=True)
            print("---------------------------------------", flush=True)
        time.sleep(RUN_INTERVAL_SECONDS)

if __name__ == "__main__":
    auto_run_dashboard()

