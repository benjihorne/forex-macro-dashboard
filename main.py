import datetime

with open("render_alive.txt", "a") as f:
    f.write(f"✅ Render booted at {datetime.datetime.utcnow()}\n")
