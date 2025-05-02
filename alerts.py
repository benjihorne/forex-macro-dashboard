### alerts.py — Email & Telegram Notifications

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from config import EMAIL_SENDER, EMAIL_PASS, EMAIL_RECEIVER, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, SMTP_SERVER, SMTP_PORT


def send_telegram_alert(pair: str, direction: str, reasons: list, score: float):
    try:
        msg = f"🚨 Trade Alert: {pair} ({direction.upper()})\n\n"
        msg += f"✅ Score: {score}/7\n"
        msg += "\n".join([f"• {r}" for r in reasons])

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown"
        }
        r = requests.post(url, json=payload)
        r.raise_for_status()
        print("📲 Telegram alert sent")

    except Exception as e:
        print(f"⚠️ Telegram send error: {e}")


def send_email_alert(pair: str, direction: str, reasons: list, score: float):
    try:
        subject = f"📈 Trade Signal: {pair} — {direction.upper()} ({score}/7)"
        body = f"Signal generated for {pair} in direction: {direction.upper()}\n\n"
        body += "Checklist Reasons:\n" + "\n".join([f"- {r}" for r in reasons])

        msg = MIMEMultipart()
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECEIVER
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASS)
            server.send_message(msg)

        print("📧 Email alert sent")

    except Exception as e:
        print(f"⚠️ Email send error: {e}")


def test_telegram_alert():
    send_telegram_alert("GBP/USD", "long", ["Mock test", "Ignore this alert"], 5.0)