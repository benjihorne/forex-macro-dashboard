### sentiment.py — Retail Sentiment via IG Client Data

import requests
from bs4 import BeautifulSoup


def get_retail_sentiment(pair: str) -> dict:
    """
    Scrape IG client sentiment for given forex pair
    Looks for extreme positioning (over 75% long/short)
    """
    url = "https://www.ig.com/au/trading-strategies/client-sentiment"
    try:
        page = requests.get(url)
        soup = BeautifulSoup(page.content, "html.parser")
        tables = soup.find_all("table")

        pair_id = pair.replace("/", "").upper()

        for table in tables:
            if pair_id in table.text.replace(" ", ""):
                rows = table.find_all("tr")
                long_percent = short_percent = 50

                for row in rows:
                    if "Long" in row.text:
                        long_percent = int(row.find_all("td")[1].text.replace("%", "").strip())
                    if "Short" in row.text:
                        short_percent = int(row.find_all("td")[1].text.replace("%", "").strip())

                retail_against = long_percent > 75 or short_percent > 75
                return {
                    "long_percent": long_percent,
                    "retail_against": retail_against
                }

        return {"long_percent": 50, "retail_against": False}

    except Exception as e:
        print(f"⚠️ Sentiment scrape error for {pair}: {e}")
        return {"long_percent": 50, "retail_against": False}
