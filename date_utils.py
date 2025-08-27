#!/usr/bin/env python3
"""Utility helpers: parse Norwegian date strings, normalize prices and detect venues."""
from datetime import datetime
import re
from typing import Optional

# month name mapping (Norwegian common abbreviations)
_MONTHS = {
    'jan':1, 'januar':1,
    'feb':2, 'februar':2,
    'mar':3, 'mars':3,
    'apr':4, 'april':4,
    'mai':5,
    'jun':6, 'juni':6,
    'jul':7, 'juli':7,
    'aug':8, 'august':8,
    'sep':9, 'september':9,
    'okt':10, 'oktober':10,
    'nov':11, 'november':11,
    'des':12, 'desember':12,
}

VENUES = [
    'House Of Foundation', 'Moss', 'Moss Kirke', 'Parkteatret', 'Samfunnshuset', 'Verket Scene',
    'Parkteateret', 'Salen', 'Ambio', 'Foyen'
]


def parse_norwegian_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    s = s.strip()
    now = datetime.now()

    # ISO first
    try:
        return datetime.fromisoformat(s)
    except Exception:
        pass

    # patterns: '9. okt', '9. okt 2025', '9. okt 19:30', '10.10.2025', '10.10.2025 19:30'
    # normalize whitespace
    s2 = re.sub(r'\s+', ' ', s.lower())

    # try numeric date dd.mm.yyyy
    m = re.search(r'(\d{1,2})[\./](\d{1,2})(?:[\./](\d{2,4}))?(?:\s+(\d{1,2}:\d{2}))?', s2)
    if m:
        day = int(m.group(1))
        mon = int(m.group(2))
        year = int(m.group(3)) if m.group(3) else now.year
        time_str = m.group(4)
        hour = 0
        minute = 0
        if time_str:
            hh, mm = time_str.split(':')
            hour = int(hh); minute = int(mm)
        try:
            return datetime(year, mon, day, hour, minute)
        except Exception:
            return None

    # try '9. okt' style
    m = re.search(r'(\d{1,2})\.\s*([a-zæøå]+)(?:\s*(\d{4}))?(?:\s*(\d{1,2}:\d{2}))?', s2)
    if m:
        day = int(m.group(1))
        mon_name = m.group(2)
        year = int(m.group(3)) if m.group(3) else now.year
        time_str = m.group(4)
        mon = _MONTHS.get(mon_name[:3]) or _MONTHS.get(mon_name)
        if not mon:
            return None
        hour = 0; minute = 0
        if time_str:
            hh, mm = time_str.split(':')
            hour = int(hh); minute = int(mm)
        try:
            return datetime(year, mon, day, hour, minute)
        except Exception:
            return None

    # try time-only '19:30'
    m = re.search(r'(\d{1,2}:\d{2})', s2)
    if m:
        hh, mm = m.group(1).split(':')
        return datetime(now.year, now.month, now.day, int(hh), int(mm))

    return None


def normalize_date_to_iso(s: Optional[str]) -> Optional[str]:
    dt = parse_norwegian_date(s)
    return dt.isoformat() if dt else None


def parse_price(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    t = text.lower()
    if 'gratis' in t or 'free' in t:
        return 'Gratis'
    # find patterns like 'kr 350', '350,-', '350'
    m = re.search(r'kr\s*([\d\s,.-]+)', t)
    if m:
        num = re.sub(r'[^0-9]', '', m.group(1))
        return f'kr {num}' if num else None
    m2 = re.search(r'(\d{2,4}[\d\s,.-]*)(?:\s*nok)?', t)
    if m2:
        num = re.sub(r'[^0-9]', '', m2.group(1))
        if len(num) >= 2:
            return f'kr {num}'
    return None


def detect_venue(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    t = text.lower()
    for v in VENUES:
        if v.lower() in t:
            return v
    return None
