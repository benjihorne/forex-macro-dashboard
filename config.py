### config.py — Environment Variables & Constants

import os
from dotenv import load_dotenv

load_dotenv()

# ---- EMAIL CONFIG ----
EMAIL_SENDER   = os.getenv("EMAIL_SENDER", "benjihornetrades@gmail.com")
EMAIL_PASS     = os.getenv("EMAIL_PASS")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "benhorne6@gmail.com")

# ---- API KEYS ----
FMP_API_KEY    = os.getenv("FMP_API_KEY")
QUANDL_API_KEY = os.getenv("QUANDL_API_KEY")
FRED_API_KEY   = os.getenv("FRED_API_KEY")
TE_KEY         = os.getenv("TE_KEY", "guest:guest")

# ---- TELEGRAM ----
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

# ---- SMTP ----
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT   = 587

# ---- LOGGING ----
LOG_FILE = "trade_log.csv"

# ---- SCANNING ----
TRADE_PAIRS = [
    ("GBP/USD", "GBP", "USD"),
    ("USD/JPY", "USD", "JPY"),
    ("USD/CAD", "USD", "CAD"),
    ("AUD/USD", "AUD", "USD"),
    ("GBP/JPY", "GBP", "JPY"),
    ("EUR/USD", "EUR", "USD"),
    ("EUR/JPY", "EUR", "JPY"),
    ("EUR/GBP", "EUR", "GBP"),
    ("NZD/USD", "NZD", "USD"),
    ("USD/CHF", "USD", "CHF"),
    ("AUD/JPY", "AUD", "JPY"),
    ("NZD/JPY", "NZD", "JPY"),
    ("CAD/JPY", "CAD", "JPY"),
    ("EUR/CAD", "EUR", "CAD"),
    ("GBP/AUD", "GBP", "AUD"),
    ("GBP/CAD", "GBP", "CAD"),
    ("AUD/NZD", "AUD", "NZD")
]

RUN_INTERVAL_SECONDS = 21600  # 6 hours between scheduled scans

# ---- CHECKLIST WEIGHTS ----
WEIGHTS = {
    "CB tone divergence hawk→dove":           1.0,
    "CB tone divergence dove→hawk":           1.0,
    "Yield spread":                           1.0,
    "COT extreme":                            1.5,
    "Retail crowd on wrong side":             1.0,
    "Inter-market correlation confirmed":     1.0,
    "Major S/R break or clean pattern":       0.5,
    "Catalyst aligns":                        0.5,
}

SCORE_THRESHOLD = 4.0
