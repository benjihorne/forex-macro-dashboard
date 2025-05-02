### cot_data.py — COT Positioning with Z-Score Reversal Logic

import cot_reports as cot
import pandas as pd

# --- Maps currencies to futures contracts in CFTC legacy report ---
CONTRACT_MAP = {
    "EUR": "EURO FX - CHICAGO MERCANTILE EXCHANGE",
    "GBP": "BRITISH POUND STERLING - CHICAGO MERCANTILE EXCHANGE",
    "JPY": "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE",
    "AUD": "AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE",
    "CAD": "CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE"
}


def get_cot_positioning(currency: str) -> dict:
    """
    Fetch net non-commercial positioning from CFTC data
    Returns Z-score, net position, and reversal signal
    """
    try:
        df = cot.cot_all('legacy_fut', verbose=False)
        contract_name = CONTRACT_MAP.get(currency.upper())

        if not contract_name:
            print(f"❌ No contract mapping found for {currency}")
            return _empty_cot()

        cot_filtered = df[df['Market and Exchange Names'].str.contains(contract_name, case=False)]
        if cot_filtered.empty:
            print(f"⚠️ No COT data found for {currency}")
            return _empty_cot()

        cot_filtered = cot_filtered.sort_values("As of Date in Form YYYY-MM-DD")
        net_spec = cot_filtered['Noncommercial Positions-Long (All)'] - cot_filtered['Noncommercial Positions-Short (All)']

        latest_net = net_spec.iloc[-1]
        trailing = net_spec.iloc[-52:] if len(net_spec) >= 52 else net_spec
        zscore = ((latest_net - trailing.mean()) / trailing.std()).round(2)

        sentiment_reversal = abs(zscore) > 1.5

        return {
            "net_spec_position": int(latest_net),
            "extreme_zscore": float(zscore),
            "sentiment_reversal": sentiment_reversal
        }

    except Exception as e:
        print(f"⚠️ COT fetch error for {currency.upper()}: {e}")
        return _empty_cot()


def _empty_cot():
    return {
        "net_spec_position": 0,
        "extreme_zscore": 0.0,
        "sentiment_reversal": False
    }
