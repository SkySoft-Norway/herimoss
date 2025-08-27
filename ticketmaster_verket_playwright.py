#!/usr/bin/env python3
"""
Playwright stealth scraper for Verket Scene (Ticketmaster.no)
Saves clickable event links to DB and outputs debug artifacts on failure.
"""
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime
import logging
import re
import json

TICKETMASTER_URL = "https://www.ticketmaster.no/venue/verket-scene-moss-billetter/mvsc/3"
DB_PATH = "/var/www/vhosts/herimoss.no/pythoncrawler/events.db"

logging.basicConfig(level=logging.INFO)

async def fetch_verket_events_playwright():
    events = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = await browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36')
        page = await context.new_page()
        await page.goto(TICKETMASTER_URL, wait_until='networkidle', timeout=60000)
        # Wait a bit more for dynamic content
        await page.wait_for_timeout(2000)
        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')
        # Try selectors used previously
        selectors = [
            'div.event-list__item',
            'li.event-card',
            'div.event-card',
            'article.event',
            'div.eds-event-card-content__content',
            'div.event'
        ]
        used = None
        for sel in selectors:
            if soup.select_one(sel):
                used = sel
                break
        if not used:
            # Save debug
            ts = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
            debug_dir = '/var/www/vhosts/herimoss.no/pythoncrawler/debug_pages'
            import os
            os.makedirs(debug_dir, exist_ok=True)
            html_path = f"{debug_dir}/pw_verket_{ts}.html"
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html)
            logging.info(f"No selector matched. Saved debug HTML to {html_path}")
            await browser.close()
            return []
        for card in soup.select(used):
            try:
                title_tag = card.select_one('.event-list__event-name') or card.select_one('.eds-event-card__formatted-name--is-clamped')
                title = title_tag.get_text(strip=True) if title_tag else 'Uten tittel'
                link_tag = card.select_one('a')
                url = 'https://www.ticketmaster.no' + link_tag['href'] if link_tag and link_tag.has_attr('href') else TICKETMASTER_URL
                date_tag = card.select_one('.event-list__event-date') or card.select_one('.eds-text-bs')
                date_str = date_tag.get_text(strip=True) if date_tag else ''
                start_time = None
                if date_str:
                    m = re.search(r'(\d{2}\.\d{2}\.\d{4})', date_str)
                    if m:
                        start_time = m.group(1)
                event_id = None
                m = re.search(r'/event/(\d+)', url)
                if m:
                    event_id = m.group(1)
                events.append({
                    'title': title,
                    'venue': 'Verket Scene',
                    'description': None,
                    'start_time': start_time,
                    'source_url': url,
                    'price_info': None,
                    'category': 'konsert',
                    'status': 'active',
                    'external_id': event_id,
                    'source': 'ticketmaster-playwright'
                })
            except Exception as e:
                logging.warning(f"Parse error: {e}")
        await browser.close()
    return events

async def main():
    logging.info('Running Playwright verket scraper...')
    events = await fetch_verket_events_playwright()
    if not events:
        logging.info('No events found with Playwright')
    else:
        logging.info(f'Found {len(events)} events')
        for e in events:
            print(f"{e['title']} -> {e['source_url']}")

if __name__ == '__main__':
    asyncio.run(main())
