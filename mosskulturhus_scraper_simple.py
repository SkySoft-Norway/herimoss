#!/usr/bin/env python3
"""
Improved Moss Kulturhus scraper.

Goals:
 - Parse only real event anchors (<a class="event" ...>) to avoid nav items ("her", "Min side").
 - Extract: title, info_url, venue (from span.venue-*), start date (first date in line after bullet), optional end date (ignored for now), ticket_url (same as info_url until explicit purchase link is exposed), price (optional detail fetch), start time default 19:00 unless detail page reveals time.
 - Robust Norwegian month parsing and year rollover (e.g. Jan dates when scraping in autumn -> next year).
 - Optional --detail flag to fetch each event page for price/time (heuristic).
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import logging
import re
from urllib.parse import urljoin
from pathlib import Path
from date_utils import parse_norwegian_date
import sys

BASE_URL = "https://www.mosskulturhus.no"
URL = f"{BASE_URL}/"
OUT_JSON = "/var/www/vhosts/herimoss.no/pythoncrawler/mosskulturhus_events.json"
SNAP = Path(__file__).parent / "debug_pages" / "mosskulturhus_curl.html"

DEFAULT_HOUR = 19
DEFAULT_MINUTE = 0

MONTH_MAP = {
    'jan':1,'jan.':1,'januar':1,
    'feb':2,'feb.':2,'februar':2,
    'mar':3,'mar.':3,'mars':3,
    'apr':4,'apr.':4,'april':4,
    'mai':5,
    'jun':6,'jun.':6,'juni':6,
    'jul':7,'jul.':7,'juli':7,
    'aug':8,'aug.':8,'august':8,
    'sep':9,'sept':9,'sep.':9,'sept.':9,'september':9,
    'okt':10,'okt.':10,'oktober':10,
    'nov':11,'nov.':11,'november':11,
    'des':12,'des.':12,'desember':12
}

WEEKDAYS = ['mandag','tirsdag','onsdag','torsdag','fredag','lørdag','søndag','sondag']

DATE_TOKEN_RE = re.compile(r"(\d{1,2})\.\s*([a-zA-ZæøåÆØÅ]{3,10})", re.I)
TIME_RE = re.compile(r"(\d{1,2}):(\d{2})")
PRICE_RE = re.compile(r"PRIS:\s*([0-9][0-9\s\.,-]{1,10})", re.I)
MEMBER_PRICE_RE = re.compile(r"MEDLEM[^(]*?:\s*([0-9][0-9\s\.,-]{1,10})", re.I)
DATE_HEADER_RE = re.compile(r"([A-Za-zæøåÆØÅ]+)\s+(\d{1,2})\.\s*([a-zA-ZæøåÆØÅ]{3,10})", re.I)  # e.g. Lørdag 30. aug
HEADER_TIME_RE = re.compile(r"Kl\.\s*(\d{1,2}:\d{2})", re.I)

def guess_year(month: int) -> int:
    now = datetime.now()
    # If month already passed more than 2 months ago -> assume next year
    if month < now.month - 2:
        return now.year + 1
    return now.year

def build_start_date(text: str) -> datetime | None:
    # Find first date token in text
    m = DATE_TOKEN_RE.search(text)
    if not m:
        return None
    day = int(m.group(1))
    mon_key = m.group(2).lower().strip('.')
    mon = MONTH_MAP.get(mon_key) or MONTH_MAP.get(mon_key[:3])
    if not mon:
        return None
    year = guess_year(mon)
    try:
        return datetime(year, mon, day, DEFAULT_HOUR, DEFAULT_MINUTE)
    except Exception:
        return None

def parse_detail_page(url: str, fallback_date: datetime) -> dict:
    """Parse Moss Kulturhus detail page for precise start time, duration, prices, ticket link and description.
    Returns dict with keys: start (iso), end (iso optional), price (string), description (string), ticket_url (string).
    """
    result = {}
    try:
        r = requests.get(url, timeout=25, headers={'User-Agent':'Mozilla/5.0 MossKulturCrawler detail'})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        # Event details column
        details_col = soup.select_one('.column.event-details .wrapper') or soup.select_one('.event-details')
        if details_col:
            # Header h4 with date and time
            h4 = details_col.find('h4')
            if h4:
                header_text = h4.get_text(' ', strip=True)
                # Extract time from 'Kl. 16:00'
                ht = HEADER_TIME_RE.search(header_text)
                if ht:
                    time_txt = ht.group(1)
                    try:
                        hh, mm = map(int, time_txt.split(':'))
                        fallback_date = fallback_date.replace(hour=hh, minute=mm)
                    except Exception:
                        pass
                # Extract date tokens if needed (day number + month)
                dm = DATE_HEADER_RE.search(header_text)
                if dm:
                    day = int(dm.group(2))
                    mon_key = dm.group(3).lower().strip('.')
                    mon = MONTH_MAP.get(mon_key) or MONTH_MAP.get(mon_key[:3])
                    if mon:
                        year = guess_year(mon)
                        # preserve time already set
                        fallback_date = fallback_date.replace(year=year, month=mon, day=day)
            # Venue / duration / prices paragraph (first p)
            info_p = details_col.find('p')
            if info_p:
                info_text = info_p.get_text('\n', strip=True)
                # Venue is after 'HVOR:' until line break
                venue_match = re.search(r'HVOR:\s*([^\n]+)', info_text, re.I)
                if venue_match:
                    result['venue'] = venue_match.group(1).strip()
                # Duration
                dur_match = re.search(r'VARIGHET:\s*(\d+)\s*time', info_text, re.I)
                duration_hours = None
                if dur_match:
                    duration_hours = int(dur_match.group(1))
                # Additional price paragraph may follow (the one with PRIS: )
            price_p = None
            for p in details_col.find_all('p'):
                if 'PRIS:' in p.get_text():
                    price_p = p
                    break
            if price_p:
                price_text = price_p.get_text('\n', strip=True)
                base_price_match = re.search(r'PRIS:\s*([0-9][0-9\s\.,-]{1,10})', price_text, re.I)
                member_price_match = re.search(r'MEDLEM[^:]*:\s*([0-9][0-9\s\.,-]{1,10})', price_text, re.I)
                if base_price_match:
                    base_price = base_price_match.group(1).strip()
                    if member_price_match:
                        result['price'] = f"kr {base_price} (medlem {member_price_match.group(1).strip()})"
                    else:
                        result['price'] = f"kr {base_price}"
            # Ticket url
            ticket_a = details_col.find('a', class_=re.compile(r'button'), href=True)
            if ticket_a:
                href = ticket_a['href']
                result['ticket_url'] = href if href.startswith('http') else urljoin(BASE_URL, href)
            # Compute end time if duration
            if 'venue' in result and fallback_date and 'start' not in result:
                # fallback_date has been updated with time
                result['start'] = fallback_date.isoformat()
            if fallback_date and 'start' in result:
                pass
            if fallback_date and 'start' not in result:
                result['start'] = fallback_date.isoformat()
            if fallback_date and 'start' in result and 'end' not in result and 'duration_hours' not in result:
                if 'duration_hours' in locals() and duration_hours:
                    end_dt = fallback_date + timedelta(hours=duration_hours)
                    result['end'] = end_dt.isoformat()
        # Description under body div
        body_div = soup.find('div', class_='body')
        if body_div:
            paragraphs = [p.get_text(' ', strip=True) for p in body_div.find_all('p') if p.get_text(strip=True)]
            if paragraphs:
                # Truncate overly long
                result['description'] = '\n\n'.join(paragraphs)[:4000]
    except Exception as e:
        logging.warning(f"Failed to parse detail page {url}: {e}")
    return result

logging.basicConfig(level=logging.INFO)

def scrape(detail: bool=False):
    # Load HTML
    if SNAP.exists():
        html = SNAP.read_text(encoding='utf-8', errors='ignore')
        soup = BeautifulSoup(html, 'html.parser')
        offline = True
    else:
        resp = requests.get(URL, timeout=20, headers={'User-Agent':'Mozilla/5.0 MossKulturCrawler'})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        offline = False
    events = []
    for a in soup.select('a.event[href]'):
        href = a['href']
        info_url = href if href.startswith('http') else urljoin(BASE_URL, href)
        article = a.find('article') or a
        title_el = article.find(['h3','h2'])
        title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)[:120]
        info_line = article.find('p')
        line_text = info_line.get_text(' ', strip=True) if info_line else ''
        venue_span = info_line.find('span', class_=re.compile(r'venue-')) if info_line else None
        venue = venue_span.get_text(strip=True) if venue_span else None
        start_dt = build_start_date(line_text)
        start_iso = start_dt.isoformat() if start_dt else None
        rec = {
            'title': title,
            'info_url': info_url,
            'ticket_url': info_url,
            'venue': venue,
            'start': start_iso,
            'price': None,
            'raw': line_text
        }
        # Detail enrichment
        if detail and start_dt:
            enriched = parse_detail_page(info_url, start_dt)
            if enriched.get('start'):
                rec['start'] = enriched['start']
            if enriched.get('end'):
                rec['end'] = enriched['end']
            if enriched.get('price'):
                rec['price'] = enriched['price']
            if enriched.get('description'):
                rec['description'] = enriched['description']
            if enriched.get('ticket_url'):
                rec['ticket_url'] = enriched['ticket_url']
            if enriched.get('venue'):
                rec['venue'] = enriched['venue']
        events.append(rec)

    # Filter out clearly invalid (missing start or venue)
    events = [e for e in events if e.get('start') and e.get('venue')]
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump({'scraped_at': datetime.utcnow().isoformat(), 'url': URL, 'events': events, 'mode': 'offline' if offline else 'live', 'detail': detail}, f, ensure_ascii=False, indent=2)
    for e in events:
        print(f"{e['start']} | {e['venue']} | {e['title']} -> {e['info_url']} price={e.get('price')}")
    logging.info(f"Saved {len(events)} events to {OUT_JSON} (detail={detail} offline={offline})")

def main():
    detail = '--detail' in sys.argv or '--enrich' in sys.argv
    scrape(detail=detail)

if __name__ == '__main__':
    main()
