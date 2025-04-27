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
    ("USD/JPY", "USD", "JPY"),
    ("USD/CAD", "USD", "CAD"),
    ("AUD/USD", "AUD", "USD"),
    ("GBP/JPY", "GBP", "JPY"),
    ("EUR/USD", "EUR", "USD"),  # Optional: Keep if you want one slower, bigger liquidity pair
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
        # Mapping forex currency to TradingView futures symbol
        futures_map = {
            "GBP": "CME_GBP1!",
            "EUR": "CME_EUR1!",
            "JPY": "CME_JPY1!",
            "AUD": "CME_AD1!",
            "CAD": "CME_CD1!",
            "CHF": "CME_CHF1!",
            "NZD": "CME_NZD1!"
        }

        symbol = futures_map.get(currency.upper())
        if not symbol:
            return {"net_spec_position": 0, "extreme_zscore": 0.0}

        url = f"https://www.tradingview.com/symbols/{symbol}/technicals/"
        page = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(page.content, "html.parser")

        # TradingView stores COT net speculator positioning in a JavaScript variable inside the page
        scripts = soup.find_all("script")
        for script in scripts:
            if "net_position" in script.text:
                # Brutal but simple parsing
                text = script.text
                start = text.find("net_position") + len("net_position") + 2
                end = text.find(",", start)
                net_position = int(text[start:end])
                
                # Rough proxy: if positioning is very high or very low compared to historic norm
                extreme = abs(net_position) > 20000  # Customize threshold if needed
                extreme_zscore = 2.0 if extreme else 0.5
                return {
                    "net_spec_position": net_position,
                    "extreme_zscore": extreme_zscore
                }

        # If parsing fails
        return {"net_spec_position": 0, "extreme_zscore": 0.0}

    except Exception as e:
        print(f"⚠️ TradingView COT fetch error for {currency}: {e}")
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

def precision_filters(pair, base_ccy, quote_ccy, direction):
    now_utc = datetime.datetime.utcnow()

    # 1. Time of Day Filter (only trade between 08:00–16:00 UTC)
    if not (8 <= now_utc.hour <= 16):
        print(f"❌ Skipping {pair} — Outside optimal trading hours ({now_utc.hour}:00 UTC)")
        return False

    # 2. Volatility Filter (ATR 14 Daily)
    try:
        url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{base_ccy}{quote_ccy}=X?serietype=line&timeseries=20&apikey={FMP_API_KEY}"
        res = requests.get(url).json()
        closes = [float(day['close']) for day in res['historical']]
        atr = np.mean([abs(closes[i] - closes[i-1]) for i in range(1, len(closes))])
        minimum_atr_threshold = 0.0025  # Adjust this if needed based on your pairs
        if atr < minimum_atr_threshold:
            print(f"❌ Skipping {pair} — Volatility too low (ATR={atr:.5f})")
            return False
    except Exception as e:
        print(f"⚠️ ATR fetch error for {pair}: {e}")
        return False

    return True  # Temporary — we'll add more filters after this

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

    # 4. Structural Level Breakout Filter (10-day high/low)
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

