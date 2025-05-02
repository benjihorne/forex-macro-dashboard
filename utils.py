### utils.py — Common Helpers (for future use)

import datetime
import pytz

def get_current_aest_time():
    """Returns current datetime in AEST timezone"""
    tz = pytz.timezone("Australia/Sydney")
    return datetime.datetime.now(tz)

def format_percentage(value, decimals=2):
    try:
        return f"{round(value * 100, decimals)}%"
    except:
        return "N/A"

def flatten_list_string(lst):
    return " | ".join(str(i) for i in lst)
