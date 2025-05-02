### scanner.py — Core Macro Sentiment Checklist Logic

import time
import csv
from config import TRADE_PAIRS, WEIGHTS, SCORE_THRESHOLD, LOG_FILE, RUN_INTERVAL_SECONDS
from cot_data import get_cot_positioning
from cb_tone import get_central_bank_tone
from yield_spread import get_yield_spread
from sentiment import get_retail_sentiment
from intermarket import get_intermarket_agreement
from filters import in_kill_zone as is_in_killzone, is_volatility_sufficient, passes_structural_breakout, passes_daily_trend
from alerts import send_email_alert, send_telegram_alert


def scan_trade_opportunity(pair: str, base: str, quote: str):
    print(f"\n========= SCAN RESULT =========\nPair: {pair}")

    score = 0.0
    reasons = []

    # Central Bank Tone
    tone_base = get_central_bank_tone(base).get("tone")
    tone_quote = get_central_bank_tone(quote).get("tone")
    if tone_base == "hawkish" and tone_quote == "dovish":
        score += WEIGHTS["CB tone divergence hawk→dove"]
        reasons.append("CB tone divergence hawk→dove")
    elif tone_base == "dovish" and tone_quote == "hawkish":
        score += WEIGHTS["CB tone divergence dove→hawk"]
        reasons.append("CB tone divergence dove→hawk")

    # Yield Spread
    yspread = get_yield_spread(base, quote)
    if abs(yspread["cross_10"]) > 0.2:
        score += WEIGHTS["Yield spread"]
        reasons.append("Yield spread")

    # COT Positioning
    cot_base = get_cot_positioning(base)
    cot_quote = get_cot_positioning(quote)
    if cot_base["sentiment_reversal"] or cot_quote["sentiment_reversal"]:
        score += WEIGHTS["COT extreme"]
        reasons.append("COT extreme")

    # Retail Sentiment
    sentiment = get_retail_sentiment(pair)
    if sentiment["retail_against"]:
        score += WEIGHTS["Retail crowd on wrong side"]
        reasons.append("Retail crowd on wrong side")

    # Intermarket Drivers
    if get_intermarket_agreement(pair):
        score += WEIGHTS["Inter-market correlation confirmed"]
        reasons.append("Inter-market correlation confirmed")

    # Precision Filters (directional)
    direction = "long" if yspread["cross_10"] > 0 else "short"
    if passes_structural_breakout(pair, direction):
        score += WEIGHTS["Major S/R break or clean pattern"]
        reasons.append("Major S/R break or clean pattern")

    if passes_daily_trend(pair, direction):
        score += WEIGHTS["Major S/R break or clean pattern"] * 0.5  # partial boost

    # TODO: Catalyst alignment logic here if added

    if score >= SCORE_THRESHOLD:
        send_email_alert(pair, direction, reasons, score)
        send_telegram_alert(pair, direction, reasons, score)
        log_trade(pair, direction, score, reasons)
    else:
        print(f"❌ No trade — Score {score}/7")


def log_trade(pair, direction, score, reasons):
    with open(LOG_FILE, mode="a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([time.strftime("%Y-%m-%d %H:%M"), pair, direction, score, " | ".join(reasons)])


def run_macro_sentiment_scan(run_once=False, force=False):
    while True:
        print("\n==============================")
        print("🧠 Running Macro Checklist Scan")
        print("==============================")

        for pair, base, quote in TRADE_PAIRS:
            if is_in_killzone(force_override=force) and is_volatility_sufficient(pair):
                scan_trade_opportunity(pair, base, quote)
            else:
                print(f"Skipping {pair} due to killzone/volatility")

        if run_once:
            break

        print(f"Sleeping {RUN_INTERVAL_SECONDS/3600:.1f} hrs before next scan...")
        time.sleep(RUN_INTERVAL_SECONDS)
