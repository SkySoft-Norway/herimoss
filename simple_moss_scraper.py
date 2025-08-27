#!/usr/bin/env python3
"""
Simple script to scrape Moss Kulturhus and save events to database.
"""
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
import pytz

# Add the pythoncrawler directory to the path
sys.path.insert(0, '/var/www/vhosts/herimoss.no/pythoncrawler')

from utils import HttpClient
from scrapers.html_scraper import scrape_moss_kulturhus
from database import get_database
from logging_utils import init_logging, log_info

async def scrape_and_save():
    """Scrape Moss Kulturhus and save to database."""
    
    # Initialize logging
    init_logging()
    log_info("🎭 Starting Moss Kulturhus scraping...")
    
    # Load configuration
    with open('/var/www/vhosts/herimoss.no/pythoncrawler/options.json', 'r') as f:
        config = json.load(f)
    
    async with HttpClient() as client:
        # Scrape Moss Kulturhus
        moss_config = config['sources']['moss_kulturhus']
        log_info(f"📍 Scraping URLs: {moss_config.get('html_urls', [])}")
        
        events = await scrape_moss_kulturhus(moss_config, client)
        log_info(f"✅ Found {len(events)} events from Moss Kulturhus")
        
        if events:
            # Save to database
            db = await get_database()
            
            new_count = 0
            updated_count = 0
            
            for event in events:
                try:
                    # Check if event already exists
                    existing = await db.get_event_by_id(event.id)
                    if existing:
                        await db.save_event(event)
                        updated_count += 1
                    else:
                        await db.save_event(event)
                        new_count += 1
                except Exception as e:
                    log_info(f"Error saving event {event.title}: {e}")
                    continue
            
            log_info(f"💾 Saved: ✨ {new_count} new events, 🔄 {updated_count} updated events")
            
            # Show some examples
            log_info("📋 Sample events:")
            for i, event in enumerate(events[:5], 1):
                oslo_tz = pytz.timezone('Europe/Oslo')
                local_time = event.start.astimezone(oslo_tz) if event.start else "No date"
                log_info(f"  {i}. {event.title}")
                log_info(f"     📍 {event.venue}")
                log_info(f"     📅 {local_time}")
                if event.url:
                    log_info(f"     🔗 {event.url}")
                log_info("")
        
        return len(events)

if __name__ == "__main__":
    try:
        count = asyncio.run(scrape_and_save())
        print(f"\n🎉 Successfully processed {count} events from Moss Kulturhus!")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
