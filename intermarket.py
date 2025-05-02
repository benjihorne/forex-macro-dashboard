### intermarket.py — Asset Correlation Drivers (Oil, Gold, DXY, etc)

import requests
from config import FMP_API_KEY

cached_assets = {}

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

def fetch_change(symbol, label):
    try:
        if symbol in cached_assets:
            return cached_assets[symbol]

        url = f"https://financialmodelingprep.com/api/v3/quote/{symbol}?apikey={FMP_API_KEY}"
        res = requests.get(url).json()

        if not res or not isinstance(res, list) or "changesPercentage" not in res[0]:
            print(f"⚠️ Intermarket data not available for {symbol}")
            return None

        change = float(res[0]["changesPercentage"])
        cached_assets[symbol] = change
        print(f"🔢 {label} change: {change:.2f}%")
        return change

    except Exception as e:
        print(f"⚠️ Intermarket fetch error for {symbol}: {e}")
        return None

def get_intermarket_agreement(pair: str) -> bool:
    try:
        base, quote = pair.split("/")
        confluences = []

        for side in [base, quote]:
            if side in asset_map:
                symbol, label = asset_map[side]
                change = fetch_change(symbol, label)

                if change is None and symbol in fallback_map:
                    fallback = fallback_map[symbol]
                    change = fetch_change(fallback, label + " (fallback)")

                if change is not None:
                    if side == base and change > 0.5:
                        confluences.append(f"{side} supported by {label}")
                    elif side == quote and change < -0.5:
                        confluences.append(f"{side} weakness from {label}")
            else:
                print(f"❌ No intermarket logic for {side}")

        if base in ["JPY", "CHF"] or quote in ["JPY", "CHF"]:
            vix = fetch_change("^VIX", "VIX Proxy") or fetch_change("VIXY", "VIXY ETF")
            if vix and vix > 2:
                if base in ["JPY", "CHF"]:
                    confluences.append(f"{base} supported by risk-off (VIX ↑)")
                if quote in ["JPY", "CHF"]:
                    confluences.append(f"{quote} weakness from risk-off (VIX ↑)")

        if base == "AUD":
            china = fetch_change("000001.SS", "Shanghai Index") or fetch_change("SSEC", "Shanghai Comp (alt)")
            if china and china > 0.5:
                confluences.append("AUD strength from China optimism")

        if confluences:
            print(f"✅ Intermarket agreement confirmed: {' & '.join(confluences)}")
            return True
        else:
            print("❌ No intermarket alignment confirmed")
            return False

    except Exception as e:
        print(f"⚠️ Intermarket agreement error for {pair}: {e}")
        return False
