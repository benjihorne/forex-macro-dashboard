### cb_tone.py — Central Bank Hawkish/Dovish Tone via RSS

import feedparser
import datetime

# RSS feeds for G10 central banks
RSS_FEEDS = {
    "USD": ["https://www.federalreserve.gov/feeds/press_all.xml"],
    "GBP": ["https://www.bankofengland.co.uk/boeapps/RSSFeeds/Pages/News.xml"],
    "EUR": ["https://www.ecb.europa.eu/rss/press.html"],
    "JPY": ["https://www.boj.or.jp/en/announcements/release_2024.xml"],
    "AUD": ["https://www.rba.gov.au/rss/media-releases.xml"],
    "CAD": ["https://www.bankofcanada.ca/feeds/speeches"]
}

# Sentiment keywords
HAWKISH = ("hike", "tighten", "restrictive", "inflation too high")
DOVISH  = ("cut", "ease", "accommodative", "downside risk")

def get_central_bank_tone(ccy: str) -> dict:
    """
    Scrape central bank press releases and detect tone using keywords.
    Only headlines from today are considered.
    """
    try:
        texts = []
        today = datetime.datetime.utcnow().date()
        for url in RSS_FEEDS.get(ccy, []):
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                ts = datetime.datetime(*entry.published_parsed[:6]).date()
                if ts == today:
                    title = entry.title if hasattr(entry, "title") else ""
                    summary = getattr(entry, "summary", "")
                    texts.append((title + " " + summary).lower())

        blob = " ".join(texts)
        if any(word in blob for word in HAWKISH):
            return {"tone": "hawkish"}
        if any(word in blob for word in DOVISH):
            return {"tone": "dovish"}
        return {"tone": "neutral"}

    except Exception as e:
        print(f"⚠️ CB tone fetch error for {ccy.upper()}: {e}")
        return {"tone": "neutral"}
