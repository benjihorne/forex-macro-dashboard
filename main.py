### Directory Structure Plan
# /macro_bot/
# ├── main.py                  ← entry point (just calls modules)
# ├── config.py                ← environment variables & constants
# ├── scanner.py               ← core scan logic
# ├── data_sources/
# │   ├── cot_data.py          ← COT positioning + z-score
# │   ├── yield_spread.py      ← FRED/TE yield spreads
# │   ├── sentiment.py         ← retail sentiment logic
# │   ├── intermarket.py       ← intermarket drivers logic
# │   └── cb_tone.py           ← central bank tone via RSS
# ├── filters.py               ← precision filters: ATR, trend, kill zone
# ├── alerts.py                ← email & Telegram alerts
# └── utils.py                 ← shared helpers / formatting

### Let's begin with main.py which becomes the dispatcher:

from scanner import run_macro_sentiment_scan

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        match sys.argv[1]:
            case "run_once":
                run_macro_sentiment_scan(run_once=True)
            case "backtest":
                from backtest import run_backtest
                run_backtest()
            case "test_telegram":
                from alerts import test_telegram_alert
                test_telegram_alert()
    else:
        run_macro_sentiment_scan()

### Next, config.py will hold environment and shared constants (next step)
### Each module will be cleaned and dropped into the appropriate file
### I’ll now start migrating and cleaning your current script piece by piece
### beginning with config.py and cot_data.py unless you want to start elsewhere.
