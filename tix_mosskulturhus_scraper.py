#!/usr/bin/env python3
"""
Tix EventAPI integrasjon for Moss Kulturhus
Henter arrangementer direkte fra Tix API
"""

import requests
import sqlite3
from datetime import datetime
import logging
import os

logging.basicConfig(level=logging.INFO)

TIX_API_BASE = "https://eventapi.tix.uk/v2/"
ORGANIZER_ID = 1000002  # Moss Kulturhus sin Tix-organizer ID (må bekreftes)

DB_PATH = "/var/www/vhosts/herimoss.no/pythoncrawler/events.db"

def get_tix_api_key():
    return os.environ.get('TIX_API_KEY') or os.getenv('TIX_API_KEY')

def fetch_tix_events():
    """Hent alle kommende events fra Moss Kulturhus via Tix API"""
    api_key = get_tix_api_key()
    if not api_key:
        raise Exception("TIX_API_KEY mangler i miljøvariabler eller .env")
    url = f"{TIX_API_BASE}Events"
    params = {
        "key": api_key
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()

def save_events_to_db(events):
    """Lagre Tix events til lokal database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    saved = 0
    for event in events:
        try:
            title = event.get('name', 'Uten tittel')
            description = event.get('description', '')
            start = event.get('startDate')
            end = event.get('endDate')
            url = event.get('url') or event.get('webUrl') or ''
            venue = event.get('venue', {}).get('name', 'Moss Kulturhus')
            price = event.get('price', '')
            category = event.get('category', 'kultur')
            external_id = event.get('id')
            
            # Konverter dato
            start_time = None
            if start:
                try:
                    start_time = datetime.fromisoformat(start.replace('Z','+00:00')).strftime('%Y-%m-%d %H:%M')
                except Exception:
                    start_time = start
            
            cursor.execute("""
                INSERT OR REPLACE INTO events 
                (title, venue, description, start_time, end_time, source_url, price_info, category, status, external_id, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, 'tix')
            """, (
                title, venue, description, start_time, end, url, price, category, external_id
            ))
            saved += 1
        except Exception as e:
            logging.warning(f"Feil ved lagring av event: {e}")
    conn.commit()
    conn.close()
    logging.info(f"💾 Lagret {saved} Tix-events fra Moss Kulturhus")
    return saved

def main():
    logging.info("🔗 Henter events fra Tix for Moss Kulturhus...")
    try:
        events = fetch_tix_events()
        if not events:
            logging.warning("Ingen events funnet fra Tix API")
            return
        save_events_to_db(events)
    except Exception as e:
        logging.error(f"Tix-integrasjon feilet: {e}")

if __name__ == "__main__":
    main()
