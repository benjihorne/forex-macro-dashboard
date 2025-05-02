### filters.py — Volatility, Time, Breakout & Trend Filters

import datetime
import requests
import pandas as pd
import numpy as np
from config import FMP_API_KEY


def is_in_killzone() -> bool:
    aest = datetime.timezone(datetime.timedelta(hours=10))  # AEST (UTC+10)
    now = datetime.datetime.now(tz=aest)
    return 14 <= now.hour <= 22  # 2PM to 10PM AEST


def is_volatility_sufficient(pair: str) -> bool:
    base, quote = pair.split("/")
    symbol = f"{base}{quote}=X"
    try:
        url = f"https://financialmodelingprep.com/api/v3/historical-chart/4hour/{symbol}?apikey={FMP_API_KEY}"
        res = requests.get(url)
        df = pd.DataFrame(res.json())

        if df.empty or "close" not in df.columns:
            return True  # fail-safe: allow trade

        df["datetime"] = pd.to_datetime(df["date"])
        df.set_index("datetime", inplace=True)

        df["H-L"] = df["high"] - df["low"]
        df["H-PC"] = abs(df["high"] - df["close"].shift(1))
        df["L-PC"] = abs(df["low"] - df["close"].shift(1))
        df["TR"] = df[["H-L", "H-PC", "L-PC"]].max(axis=1)
        df["ATR"] = df["TR"].rolling(window=14).mean()

        latest_atr = df["ATR"].iloc[-1]
        latest_close = df["close"].iloc[-1]
        atr_percent = (latest_atr / latest_close) * 100

        if atr_percent >= 0.3:
            return True
        else:
            print(f"⚠️ Skipping {pair} — 4H volatility too low ({atr_percent:.2f}%)")
            return False

    except Exception as e:
        print(f"⚠️ Volatility check error for {pair}: {e}")
        return True  # fail-safe


def passes_structural_breakout(pair: str, direction: str) -> bool:
    base, quote = pair.split("/")
    symbol = f"{base}{quote}=X"
    try:
        url = f"https://financialmodelingprep.com/api/v3/historical-chart/1hour/{symbol}?apikey={FMP_API_KEY}"
        res = requests.get(url).json()
        df = pd.DataFrame(res)

        df["datetime"] = pd.to_datetime(df["date"])
        df.set_index("datetime", inplace=True)
        closes = df["close"].sort_index()
        closes_daily = closes.resample("D").last().dropna()

        if len(closes_daily) < 60:
            print(f"⚠️ Not enough daily data for {pair} to check breakout")
            return False

        recent_high = closes_daily[-10:].max()
        recent_low  = closes_daily[-10:].min()
        last_close  = closes_daily.iloc[-1]

        if direction == "long" and last_close < recent_high:
            print(f"❌ Skipping {pair} — No breakout above recent high")
            return False
        if direction == "short" and last_close > recent_low:
            print(f"❌ Skipping {pair} — No breakdown below recent low")
            return False

        return True

    except Exception as e:
        print(f"⚠️ Structure level check error for {pair}: {e}")
        return False


def passes_daily_trend(pair: str, direction: str) -> bool:
    base, quote = pair.split("/")
    symbol = f"{base}{quote}=X"
    try:
        url = f"https://financialmodelingprep.com/api/v3/historical-chart/1hour/{symbol}?apikey={FMP_API_KEY}"
        res = requests.get(url).json()
        df = pd.DataFrame(res)

        df["datetime"] = pd.to_datetime(df["date"])
        df.set_index("datetime", inplace=True)
        closes = df["close"].sort_index()
        closes_daily = closes.resample("D").last().dropna()

        if len(closes_daily) < 60:
            print(f"⚠️ Not enough data for {pair} to check daily trend")
            return False

        ma50 = closes_daily.rolling(window=50).mean()
        last_close = closes_daily.iloc[-1]
        last_ma50 = ma50.iloc[-1]

        daily_trend = "long" if last_close > last_ma50 else "short"
        if daily_trend != direction:
            print(f"❌ Skipping {pair} — Daily trend mismatch ({daily_trend.upper()} vs {direction.upper()})")
            return False

        return True

    except Exception as e:
        print(f"⚠️ Daily trend check error for {pair}: {e}")
        return False