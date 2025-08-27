#!/usr/bin/env python3
"""
Webscraper for Verket Scene events fra ticketmaster.no
Alle arrangement får klikkbar lenke til original eventside
"""

import requests
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime
import logging
import re

logging.basicConfig(level=logging.INFO)

TICKETMASTER_URL = "https://www.ticketmaster.no/venue/verket-scene-moss-billetter/mvsc/3"
DB_PATH = "/var/www/vhosts/herimoss.no/pythoncrawler/events.db"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def fetch_verket_events():
    resp = requests.get(TICKETMASTER_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    events = []
    for card in soup.select('div.event-list__item'):
        try:
            title_tag = card.select_one('.event-list__event-name')
            title = title_tag.get_text(strip=True) if title_tag else 'Uten tittel'
            link_tag = card.select_one('a.event-list__event-link')
            url = 'https://www.ticketmaster.no' + link_tag['href'] if link_tag and link_tag.has_attr('href') else TICKETMASTER_URL
            date_tag = card.select_one('.event-list__event-date')
            date_str = date_tag.get_text(strip=True) if date_tag else ''
            # Prøv å parse dato
            start_time = None
            if date_str:
                m = re.search(r'(\d{2}\.\d{2}\.\d{4})', date_str)
                if m:
                    try:
                        start_time = datetime.strptime(m.group(1), '%d.%m.%Y').strftime('%Y-%m-%d')
                    except Exception:
                        start_time = m.group(1)
            # Venue
            venue = 'Verket Scene'
            # Pris (Ticketmaster viser sjelden pris på oversikt)
            price = ''
            # Beskrivelse (ikke tilgjengelig på oversikt)
            description = ''
            # Event ID fra URL
            event_id = None
            m = re.search(r'/event/(\d+)', url)
            if m:
                event_id = m.group(1)
            events.append({
                'title': title,
                'venue': venue,
                'description': description,
                'start_time': start_time,
                'source_url': url,
                'price_info': price,
                'category': 'konsert',
                'status': 'active',
                'external_id': event_id,
                'source': 'ticketmaster-scrape'
            })
        except Exception as e:
            logging.warning(f"Feil ved parsing av event: {e}")
    return events

def save_events_to_db(events):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    saved = 0
    for event in events:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO events 
                (title, venue, description, start_time, source_url, price_info, category, status, external_id, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event['title'], event['venue'], event['description'], event['start_time'], event['source_url'],
                event['price_info'], event['category'], event['status'], event['external_id'], event['source']
            ))
            saved += 1
        except Exception as e:
            logging.warning(f"Feil ved lagring av event: {e}")
    conn.commit()
    conn.close()
    logging.info(f"💾 Lagret {saved} events fra Verket Scene (Ticketmaster)")
    return saved

def main():
    logging.info("🔗 Henter events fra Verket Scene (Ticketmaster.no)...")
    try:
        events = fetch_verket_events()
        if not events:
            logging.warning("Ingen events funnet fra Verket Scene på Ticketmaster.no")
            return
        save_events_to_db(events)
    except Exception as e:
        logging.error(f"Ticketmaster-scraping feilet: {e}")

if __name__ == "__main__":
    main()
