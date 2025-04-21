# === FULL MAIN.PY WITH 5-MINUTE SCANS, LOGGING, AND FAIL-SAFE ===
import datetime
with open("boot_log.txt", "a") as f:
    f.write(f"✅ Booted at {datetime.datetime.utcnow()}\n")

print("⚙️ main.py has started execution")
import requests
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bs4 import BeautifulSoup
import time
import os
import sys
import schedule
print("✅ All libraries imported")
print(f"🛠 Running Python version: {sys.version}")

# --- CONFIG ---
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "benjihornetrades@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "Ben135790!")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "benhorne6@gmail.com")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
LOG_FILE = "trade_log.csv"
QUANDL_API_KEY = os.getenv("QUANDL_API_KEY", "jmA5k4Z8BwXLW_6hkw-2")
FRED_API_KEY = os.getenv("FRED_API_KEY", "03041666822ce885ee3462500fa93cd5")
TRADE_PAIRS = [("GBP/USD", "GBP", "USD"), ("EUR/USD", "EUR", "USD"), ("USD/JPY", "USD", "JPY")]

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

# [...unchanged utility functions get_cot_data to get_upcoming_catalyst remain as-is...]

# --- EMAIL ---
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

# --- LOGGING ---
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

# --- SCANNING ---
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
    if len(checklist) >= 5:
        print(f"✅ TRADE VALIDATED ({len(checklist)}/7, {direction.upper()} {pair})")
        send_email_alert(pair, checklist, direction)
        log_trade(pair, checklist)
    else:
        print("❌ Not enough edge for swing entry")

def run_all_pairs():
    print(f"\n[SCAN START] {datetime.datetime.utcnow()} UTC")
    for pair, base, quote in TRADE_PAIRS:
        try:
            scan_trade_opportunity(pair, base, quote)
        except Exception as e:
            print(f"⚠️ Error scanning {pair}: {e}")
        print("---------------------------------------")

def auto_run_dashboard():
    print("📅 5-minute scanning activated")
    schedule.every(5).minutes.do(run_all_pairs)
    last_log = datetime.datetime.utcnow()
    while True:
        try:
            schedule.run_pending()
            now = datetime.datetime.utcnow()
            if (now - last_log).seconds > 60:
                print(f"⏳ Waiting... {now}")
                last_log = now
        except Exception as loop_err:
            print(f"⚠️ Schedule loop error: {loop_err}")
        time.sleep(5)

if __name__ == "__main__":
    print("🚀 __main__ reached — beginning bot loop")
    auto_run_dashboard()