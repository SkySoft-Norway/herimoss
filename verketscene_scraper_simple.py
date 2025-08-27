#!/usr/bin/env python3
"""
Verket Scene scraper.

Primary goals:
 - Produce clean event objects with: title, info_url, ticket_url (if any), start (ISO), optional end, description, venue, price.
 - Be robust when the live site structure (Squarespace) changes by supporting an offline snapshot parse.

Current implementation strategy:
 1. Try to load the locally saved snapshot (debug_pages/verketscene.html) first for determinism.
 2. If snapshot missing or --live flag provided, fetch the live program page.
 3. Parse each .summary-item.summary-item-record-type-event container.
 4. Extract date from the month/day badge (month abbreviations are English in snapshot: Sep/Oct/Nov, map manually).
 5. Use a default start time (19:00) when no time information is present (Squarespace listing view omits exact time).
 6. Detect ticket (purchase) link by heuristics: href containing ticketmaster, tix, hoopla, smaksrike, eventim, universe; or link text containing KJØP / BILLETT.
 7. Description: first paragraph in the excerpt not containing a purchase keyword.
 8. De-duplicate events by (title, start date).

NOTE: When later adding detail-page fetching for precise time, keep offline-mode fast by gating network calls behind a flag.
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import os
import sys
import json
import logging
import time
from urllib.parse import urljoin
from date_utils import parse_norwegian_date, parse_price
_NO_EN_MONTH_ALL = {
    'jan':1,'januar':1,'jan.':1,
    'feb':2,'februar':2,'feb.':2,
    'mar':3,'mars':3,'mar.':3,
    'apr':4,'april':4,'apr.':4,
    'mai':5,
    'jun':6,'juni':6,'jun.':6,
    'jul':7,'juli':7,'jul.':7,
    'aug':8,'august':8,'aug.':8,
    'sep':9,'sept':9,'september':9,'sep.':9,'sept.':9,
    'oct':10,'okt':10,'oktober':10,'oct.':10,'okt.':10,
    'nov':11,'november':11,'nov.':11,
    'dec':12,'des':12,'desember':12,'dec.':12,'des.':12
}


BASE_URL = "https://www.verketscene.no"
PROGRAM_URL = f"{BASE_URL}/programmet"
SNAPSHOT_PATH = "/var/www/vhosts/herimoss.no/pythoncrawler/debug_pages/verketscene.html"
OUT_JSON = "/var/www/vhosts/herimoss.no/pythoncrawler/verketscene_events.json"

DEFAULT_EVENT_HOUR = 19  # assumed default start hour when not specified
DEFAULT_EVENT_MINUTE = 0

# Map English (Squarespace badge) month abbreviations to month numbers (fallback to Norwegian mapping via parse if possible)
_EN_MONTH = {}
for i, m in enumerate(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], start=1):
    _EN_MONTH[m.lower()] = i

PURCHASE_KEYWORDS = [
    'ticketmaster', 'tix', 'tixly', 'eventim', 'billetto', 'hoopla', 'smaksrike', 'universe'
]

def _guess_year(month_num: int) -> int:
    """Return a plausible year for the event based on current date.
    Assumes events are not listed more than ~10 months ahead.
    """
    now = datetime.now()
    if month_num >= now.month - 2:  # allow a small negative drift (e.g., listing captured near year boundary)
        return now.year
    return now.year + 1

logging.basicConfig(level=logging.INFO)

def fetch(url: str) -> BeautifulSoup:
    r = requests.get(url, timeout=25, headers={'User-Agent': 'Mozilla/5.0 MossKulturCrawler'})
    r.raise_for_status()
    return BeautifulSoup(r.text, 'html.parser')


def parse_snapshot(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, 'html.parser')


def parse_listing(soup: BeautifulSoup, offline: bool = True) -> list:
    """Parse listing page (snapshot or live) into event dicts without hitting detail pages when offline.
    offline=True avoids network calls. Detail enrichment can be added later.
    """
    events = []
    seen = set()
    for item in soup.select('.summary-item.summary-item-record-type-event'):
        title_a = item.select_one('a.summary-title-link[href]')
        if not title_a:
            continue
        raw_title = title_a.get_text(strip=True)
        info_href = title_a.get('href')
        info_url = info_href if info_href.startswith('http') else urljoin(BASE_URL, info_href)

        # Date components
        month_el = item.select_one('.summary-thumbnail-event-date-month')
        day_el = item.select_one('.summary-thumbnail-event-date-day')
        start_iso = None
        if month_el and day_el:
            mon_txt = month_el.get_text(strip=True)[:3].lower()
            day_txt = day_el.get_text(strip=True)
            try:
                day = int(re.sub(r'[^0-9]', '', day_txt))
                mon = _EN_MONTH.get(mon_txt)
                if mon:
                    year = _guess_year(mon)
                    # default time
                    start_dt = datetime(year, mon, day, DEFAULT_EVENT_HOUR, DEFAULT_EVENT_MINUTE)
                    start_iso = start_dt.isoformat()
            except Exception as e:
                logging.warning(f"Failed to build date for {raw_title}: {e}; month={mon_txt} day={day_txt}")

        # Description & ticket link heuristics
        excerpt = item.select_one('.summary-excerpt')
        desc = None
        ticket_url = None
        if excerpt:
            # paragraphs inside excerpt
            for p in excerpt.find_all('p'):
                txt = p.get_text(' ', strip=True)
                if not txt:
                    continue
                a_in_p = p.find('a', href=True)
                href = a_in_p['href'].strip() if a_in_p else None
                # Purchase detection
                if href and any(k in href.lower() for k in PURCHASE_KEYWORDS):
                    ticket_url = href if href.startswith('http') else urljoin(BASE_URL, href)
                    continue
                if any(w in txt.lower() for w in ['kjøp billetter', 'kjøp billett', 'billetter', 'buy tickets']):
                    if a_in_p and not ticket_url:
                        ticket_url = href if href.startswith('http') else urljoin(BASE_URL, href)
                    continue
                # Use first non-purchase paragraph as description
                if not desc:
                    desc = txt
        if not desc:
            desc = raw_title

        # Dedupe by title+date day
        dedupe_key = (raw_title.lower(), start_iso[:10] if start_iso else None)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        events.append({
            'title': raw_title,
            'info_url': info_url,
            'ticket_url': ticket_url,
            'start': start_iso,
            'end': None,
            'description': desc,
            'venue': 'Verket Scene',
            'price': None
        })
    return events


DETAIL_DATE_RE = re.compile(r'(\d{1,2})[\.,]?\s*([a-zA-ZæøåÆØÅ]{3,12})\s*(\d{4})?', re.I)
TIME_RANGE_RE = re.compile(r'(\d{1,2}:\d{2})\s*[–\-]\s*(\d{1,2}:\d{2})')
TIME_SINGLE_RE = re.compile(r'(\d{1,2}:\d{2})')

def parse_event_detail_page(url: str, fallback_date: datetime) -> dict:
    """Fetch detail page and attempt to refine start/end times and description.
    fallback_date supplies year/month/day when page omits date.
    """
    out = {}
    try:
        r = requests.get(url, timeout=25, headers={'User-Agent': 'Mozilla/5.0 MossKulturCrawler detail'})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        text = soup.get_text('\n', strip=True)
        # Description meta first
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            out['description'] = meta_desc['content'].strip()

        # Date/time extraction
        start_dt = None
        end_dt = None
        # Look for explicit date line
        m_date = DETAIL_DATE_RE.search(text)
        if m_date:
            day = int(m_date.group(1))
            mon_name = m_date.group(2).lower().strip('.')
            year = int(m_date.group(3)) if m_date.group(3) else fallback_date.year
            mon = _NO_EN_MONTH_ALL.get(mon_name[:3]) or _NO_EN_MONTH_ALL.get(mon_name)
            if mon:
                # times (range or single)
                m_range = TIME_RANGE_RE.search(text)
                if m_range:
                    s_time, e_time = m_range.groups()
                    sh, sm = map(int, s_time.split(':'))
                    eh, em = map(int, e_time.split(':'))
                    start_dt = datetime(year, mon, day, sh, sm)
                    end_dt = datetime(year, mon, day, eh, em)
                else:
                    m_time = TIME_SINGLE_RE.search(text)
                    if m_time:
                        sh, sm = map(int, m_time.group(1).split(':'))
                        start_dt = datetime(year, mon, day, sh, sm)
                if start_dt and not end_dt and start_dt.hour < 23:
                    # Heuristic 3h duration for concerts if no end given
                    end_dt = start_dt.replace(hour=min(start_dt.hour + 3, 23))
        else:
            # If only time present, apply to fallback date
            m_range = TIME_RANGE_RE.search(text)
            if m_range:
                s_time, e_time = m_range.groups()
                sh, sm = map(int, s_time.split(':'))
                eh, em = map(int, e_time.split(':'))
                start_dt = fallback_date.replace(hour=sh, minute=sm)
                end_dt = fallback_date.replace(hour=eh, minute=em)
            else:
                m_time = TIME_SINGLE_RE.search(text)
                if m_time:
                    sh, sm = map(int, m_time.group(1).split(':'))
                    start_dt = fallback_date.replace(hour=sh, minute=sm)
                    if sh < 23:
                        end_dt = fallback_date.replace(hour=min(sh + 3, 23), minute=sm)

        if start_dt:
            out['start'] = start_dt.isoformat()
        if end_dt:
            out['end'] = end_dt.isoformat()
    except Exception as e:
        logging.warning(f"Detail fetch failed for {url}: {e}")
    return out


def scrape(live: bool = False, detail: bool = False):
    offline_used = False
    soup = None
    if not live and os.path.exists(SNAPSHOT_PATH):
        try:
            with open(SNAPSHOT_PATH, 'r', encoding='utf-8') as fh:
                html = fh.read()
            soup = parse_snapshot(html)
            offline_used = True
            logging.info("Parsed offline snapshot for Verket Scene.")
        except Exception as e:
            logging.warning(f"Failed reading snapshot, will fallback to live: {e}")
    if soup is None:
        soup = fetch(PROGRAM_URL)
        logging.info("Fetched live Verket Scene program page.")

    events = parse_listing(soup, offline=offline_used)

    # Fallback: if live fetch yielded zero events but snapshot exists, try snapshot parse
    if not offline_used and not events and os.path.exists(SNAPSHOT_PATH):
        try:
            with open(SNAPSHOT_PATH, 'r', encoding='utf-8') as fh:
                html = fh.read()
            snap_soup = parse_snapshot(html)
            snap_events = parse_listing(snap_soup, offline=True)
            if snap_events:
                logging.warning("Live page produced 0 events; fell back to snapshot parse.")
                events = snap_events
                offline_used = True
        except Exception as e:
            logging.warning(f"Fallback to snapshot failed: {e}")

    if detail and not offline_used:
        logging.info("Detail enrichment enabled; fetching individual event pages...")
        for ev in events:
            try:
                # Build fallback date from existing start (already month/day from listing)
                if ev.get('start'):
                    fb = datetime.fromisoformat(ev['start'])
                else:
                    fb = datetime.now()
                enriched = parse_event_detail_page(ev['info_url'], fb)
                # Override start if enriched start exists and differs (esp if default 19:00 assumption)
                if enriched.get('start') and (':00' in ev.get('start','') and enriched['start'] != ev['start']):
                    ev['start'] = enriched['start']
                if enriched.get('end'):
                    ev['end'] = enriched['end']
                if enriched.get('description') and (not ev.get('description') or ev['description'] == ev['title']):
                    ev['description'] = enriched['description']
                time.sleep(0.4)  # polite delay
            except Exception as e:
                logging.warning(f"Enrichment failed for {ev.get('info_url')}: {e}")
    elif detail and offline_used:
        logging.info("Detail flag ignored in offline snapshot mode (no network calls).")

    # Basic post-processing: ensure mandatory fields
    cleaned = []
    for ev in events:
        if not ev.get('start'):
            # Try salvage by adding date from title (not present currently) else skip
            continue
        if not ev.get('price'):
            ev['price'] = 'Ukjent'
        cleaned.append(ev)

    payload = {
        'scraped_at': datetime.utcnow().isoformat(),
        'mode': 'offline' if offline_used else 'live',
        'source_url': PROGRAM_URL,
        'events': cleaned
    }
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    for e in cleaned:
        print(f"{e['title']} -> {e['info_url']} (ticket: {e.get('ticket_url')}) start={e.get('start')}")
    logging.info(f"Saved {len(cleaned)} events to {OUT_JSON} (offline_used={offline_used})")

if __name__ == '__main__':
    live_flag = '--live' in sys.argv
    detail_flag = '--detail' in sys.argv or '--enrich' in sys.argv
    scrape(live=live_flag, detail=detail_flag)
