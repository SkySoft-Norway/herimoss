#!/usr/bin/env python3
"""
Selenium-based scraper for Verket Scene events from ticketmaster.no
Bypasses 403 blocks by using a real browser session.
"""
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime
import logging
import re

TICKETMASTER_URL = "https://www.ticketmaster.no/venue/verket-scene-moss-billetter/mvsc/3"
DB_PATH = "/var/www/vhosts/herimoss.no/pythoncrawler/events.db"

logging.basicConfig(level=logging.INFO)

def fetch_verket_events_selenium():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--window-size=1920,1080')
    driver = webdriver.Chrome(options=options)
    driver.get(TICKETMASTER_URL)
    try:
        # Try several selectors and give more time for dynamic loading
        selectors = [
            'div.event-list__item',
            'li.event-card',
            'div.event-card',
            'article.event',
            'div.eds-event-card-content__content',
            'div.event'
        ]
        found = False
        wait_seconds = 30
        for sel in selectors:
            try:
                WebDriverWait(driver, wait_seconds).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                )
                found = True
                used_selector = sel
                break
            except Exception:
                used_selector = None
                # try next selector
                continue

        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        events = []
        target_selector = used_selector or selectors[0]
        for card in soup.select(target_selector):
            try:
                title_tag = card.select_one('.event-list__event-name')
                title = title_tag.get_text(strip=True) if title_tag else 'Uten tittel'
                link_tag = card.select_one('a.event-list__event-link')
                url = 'https://www.ticketmaster.no' + link_tag['href'] if link_tag and link_tag.has_attr('href') else TICKETMASTER_URL
                date_tag = card.select_one('.event-list__event-date')
                date_str = date_tag.get_text(strip=True) if date_tag else ''
                start_time = None
                if date_str:
                    m = re.search(r'(\d{2}\.\d{2}\.\d{4})', date_str)
                    if m:
                        try:
                            start_time = datetime.strptime(m.group(1), '%d.%m.%Y').strftime('%Y-%m-%d')
                        except Exception:
                            start_time = m.group(1)
                venue = 'Verket Scene'
                price = ''
                description = ''
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
                    'source': 'ticketmaster-selenium'
                })
            except Exception as e:
                logging.warning(f"Feil ved parsing av event: {e}")
        # If nothing found, save debug artifacts
        if not events:
            import os
            debug_dir = '/var/www/vhosts/herimoss.no/pythoncrawler/debug_pages'
            os.makedirs(debug_dir, exist_ok=True)
            ts = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
            html_path = f"{debug_dir}/verket_ticketmaster_{ts}.html"
            png_path = f"{debug_dir}/verket_ticketmaster_{ts}.png"
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            try:
                driver.save_screenshot(png_path)
            except Exception:
                logging.warning('Kunne ikke ta skjermbilde')
            logging.info(f"Ingen events funnet. Lagret debug HTML: {html_path} og skjermbilde: {png_path}")
        return events
    finally:
        driver.quit()

def save_events_to_db(events):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    saved = 0
    for event in events:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO events 
                (title, venue, description, start_time, source_url, price_info, category, status, external_id, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event['title'], event['venue'], event['description'], event['start_time'], event['source_url'],
                event['price_info'], event['category'], event['status'], event['external_id'], event['source']
            ))
            saved += 1
        except Exception as e:
            logging.warning(f"Feil ved lagring av event: {e}")
    conn.commit()
    conn.close()
    logging.info(f"💾 Lagret {saved} events fra Verket Scene (Ticketmaster, Selenium)")
    return saved

def main():
    logging.info("🔗 Henter events fra Verket Scene (Ticketmaster.no, Selenium)...")
    try:
        events = fetch_verket_events_selenium()
        if not events:
            logging.warning("Ingen events funnet fra Verket Scene på Ticketmaster.no (Selenium)")
            return
        save_events_to_db(events)
    except Exception as e:
        logging.error(f"Ticketmaster-scraping (Selenium) feilet: {e}")

if __name__ == "__main__":
    main()
