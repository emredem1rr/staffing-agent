import json
import re
from datetime import datetime, timedelta

# ─────────────────────────────────────────────
# SAFE JSON PARSER
# ─────────────────────────────────────────────

def safe_parse_json(text: str) -> dict:
    """LLM çıktısını güvenli parse eder"""
    if not text:
        return {}

    try:
        return json.loads(text)
    except:
        pass

    # JSON extract etmeye çalış
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except:
            pass

    return {}


# ─────────────────────────────────────────────
# DATE NORMALIZER
# ─────────────────────────────────────────────

def normalize_date(date_str: str) -> str | None:
    if not date_str:
        return None

    date_str = date_str.lower()
    today = datetime.now()

    if "yarın" in date_str:
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")

    if "bugün" in date_str:
        return today.strftime("%Y-%m-%d")

    # dd.mm.yyyy
    match = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", date_str)
    if match:
        d, m, y = match.groups()
        return f"{y}-{int(m):02d}-{int(d):02d}"

    # yyyy-mm-dd
    match = re.search(r"\d{4}-\d{2}-\d{2}", date_str)
    if match:
        return match.group()

    return None


# ─────────────────────────────────────────────
# TIME NORMALIZER
# ─────────────────────────────────────────────

def normalize_time(time_str: str) -> str | None:
    if not time_str:
        return None

    time_str = time_str.lower()

    # "18:30"
    match = re.search(r"(\d{1,2}):(\d{2})", time_str)
    if match:
        h, m = match.groups()
        return f"{int(h):02d}:{m}"

    # "18"
    match = re.search(r"\b(\d{1,2})\b", time_str)
    if match:
        h = int(match.group(1))
        if 0 <= h <= 23:
            return f"{h:02d}:00"

    # Türkçe ifadeler
    if "akşam" in time_str:
        return "18:00"
    if "sabah" in time_str:
        return "09:00"
    if "öğlen" in time_str:
        return "12:00"

    return None


# ─────────────────────────────────────────────
# END TIME AUTO
# ─────────────────────────────────────────────

def infer_end_time(start_time: str) -> str:
    try:
        h = int(start_time.split(":")[0])
        h = min(h + 5, 23)
        return f"{h:02d}:00"
    except:
        return "23:00"


# ─────────────────────────────────────────────
# FULL NORMALIZER
# ─────────────────────────────────────────────

def normalize_parsed_data(parsed: dict) -> dict:
    """LLM çıktısını production-ready hale getirir"""

    if not parsed:
        return {}

    date = normalize_date(parsed.get("date"))
    time = normalize_time(parsed.get("time"))
    end_time = normalize_time(parsed.get("end_time"))

    if time and not end_time:
        end_time = infer_end_time(time)

    return {
        "date": date,
        "time": time,
        "end_time": end_time,
        "location": parsed.get("location"),
        "needs": parsed.get("needs", [])
    }