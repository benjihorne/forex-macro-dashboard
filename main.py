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
QUANDL_API_KEY = os.getenv("QUANDL_API_KEY", "jmA5k4Z8BwXLW_6hkw-2")
FRED_API_KEY = os.getenv("FRED_API_KEY", "03041666822ce885ee3462500fa93cd5")
FMP_API_KEY = "czVnLpLUT3GA7bsOP6yci0eMStqe3hPQ"
TRADE_PAIRS = [
    ("GBP/USD", "GBP", "USD"),
    ("EUR/USD", "EUR", "USD"),
    ("USD/JPY", "USD", "JPY"),
    ("USD/CAD", "USD", "CAD"),     # 🛢 Crude Oil driver for CAD
    ("AUD/USD", "AUD", "USD")      # 🔩 Copper driver for AUD
]

RUN_INTERVAL_SECONDS = 60  # safer scan interval to avoid Render throttling


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
def get_cot_data(currency):
    code_map = {
        "EUR": "CHRIS/CME_EC1",
        "GBP": "CHRIS/CME_BP1",
        "JPY": "CHRIS/CME_JY1",
        "AUD": "CHRIS/CME_AD1",
        "CAD": "CHRIS/CME_CD1",
        "CHF": "CHRIS/CME_SF1"
    }
    try:
        code = code_map.get(currency.upper())
        if not code:
            return {"net_spec_position": 0, "extreme_zscore": 0.0}
        url = f"https://www.quandl.com/api/v3/datasets/{code}.json?api_key={QUANDL_API_KEY}&rows=20"
        response = requests.get(url)
        data = response.json()["dataset"]["data"]
        df = pd.DataFrame(data, columns=response.json()["dataset"]["column_names"])
        spec_net = df["Net Position"] if "Net Position" in df.columns else df.iloc[:, -1]
        zscore = (spec_net.iloc[0] - spec_net.mean()) / spec_net.std()
        return {"net_spec_position": spec_net.iloc[0], "extreme_zscore": round(zscore, 2)}
    except:
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
        url = f"https://financialmodelingprep.com/api/v3/quote/{symbol}?apikey=czVnLpLUT3GA7bsOP6yci0eMStqe3hPQ"
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

 def get_intermarket_agreement(pair):
    try:
        base, quote = pair.split("/")
        confluences = []

        # === MAPPING ===
        asset_map = {
            "CAD": ("CL=F", "Crude Oil"),
            "AUD": ("HG=F", "Copper"),
            "CHF": ("GC=F", "Gold"),
            "JPY": ("GC=F", "Gold"),
            "USD": ("DX-Y.NYB", "US Dollar Index (DXY)"),
            "EUR": ("DAX", "German DAX Index"),
            "GBP": ("UKX.L", "FTSE 100 Index"),
            "VIX": ("VXX", "VIX Proxy"),
            "AUD_CHINA": ("SSEC", "Shanghai Composite Index")
        }



        for side in [base, quote]:
            if side in asset_map:
                symbol, label = asset_map[side]
                change = fetch_change(symbol, label)
                if change is not None:
                    if side == base and change > 0.5:
                        confluences.append(f"{side} supported by {label}")
                    elif side == quote and change < -0.5:
                        confluences.append(f"{side} weakness from {label}")
            else:
                print(f"❌ No intermarket logic for {side}", flush=True)

        if base in ["JPY", "CHF"] or quote in ["JPY", "CHF"]:
            vix = fetch_change("^VIX", "VIX")
            if vix is not None and vix > 2:
                if base in ["JPY", "CHF"]:
                    confluences.append(f"{base} supported by risk-off (VIX ↑)")
                if quote in ["JPY", "CHF"]:
                    confluences.append(f"{quote} weakness from risk-off (VIX ↑)")

        if base == "AUD":
            china = fetch_change("000001.SS", "Shanghai Index")
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

def get_technical_pattern(pair):
    try:
        # Map Forex pairs to TwelveData format
        td_symbols = {
            "EUR/USD": "EUR/USD",
            "GBP/USD": "GBP/USD",
            "USD/JPY": "USD/JPY"
        }

        symbol = td_symbols.get(pair)
        if not symbol:
            return {"key_level_broken": False, "clean_pattern": "unsupported pair"}

        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=1h&outputsize=50&apikey=7e69098ce083444684fb4d5d601598b8"
        response = requests.get(url)
        data = response.json()

        if "values" not in data:
            return {"key_level_broken": False, "clean_pattern": "bad data"}

        closes = [float(entry["close"]) for entry in reversed(data["values"])]
        ema21 = pd.Series(closes).ewm(span=21).mean().iloc[-1]

        if closes[-1] > ema21 and closes[-1] > closes[-2]:
            return {"key_level_broken": True, "clean_pattern": "bullish breakout"}
        elif closes[-1] < ema21 and closes[-1] < closes[-2]:
            return {"key_level_broken": True, "clean_pattern": "bearish breakdown"}
        else:
            return {"key_level_broken": False, "clean_pattern": "neutral"}

    except Exception as e:
        print(f"⚠️ Technical pattern error: {e}", flush=True)
        return {"key_level_broken": False, "clean_pattern": "error"}



def get_upcoming_catalyst(pair):
    return {"event": "FOMC meeting", "bias_alignment": True}

def send_email_alert(pair, checklist, direction):
    confidence = len(checklist)
    print(f"[DEBUG] Attempting to send email: {pair}, confluences: {confidence}")
    if confidence < 5:
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
    cot = get_cot_data(base_ccy)
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

