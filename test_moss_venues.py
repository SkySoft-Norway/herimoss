#!/usr/bin/env python3
"""
Test script for scraping Moss Kulturhus and Verket Scene specifically.
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
from scrapers.html_scraper import scrape_moss_kulturhus, scrape_verket_scene
from database import get_database
from logging_utils import init_logging, log_info, log_error

async def test_moss_venues():
    """Test scraping from Moss Kulturhus and Verket Scene."""
    
    # Initialize logging
    init_logging()
    
    log_info("🎭 Starting targeted scraping of Moss venues...")
    
    # Load configuration
    with open('/var/www/vhosts/herimoss.no/pythoncrawler/options.json', 'r') as f:
        config = json.load(f)
    
    client = HttpClient()
    all_events = []
    
    try:
        # Test Moss Kulturhus
        log_info("🎪 Scraping Moss Kulturhus...")
        moss_config = config['sources']['moss_kulturhus']
        log_info(f"URLs to scrape: {moss_config.get('html_urls', [])}")
        
        moss_events = await scrape_moss_kulturhus(moss_config, client)
        log_info(f"✅ Found {len(moss_events)} events from Moss Kulturhus")
        
        for event in moss_events:
            log_info(f"  - {event.title} at {event.venue} on {event.start}")
        
        all_events.extend(moss_events)
        
        # Test Verket Scene
        log_info("🎬 Scraping Verket Scene...")
        verket_config = config['sources']['verket_scene']
        log_info(f"URLs to scrape: {verket_config.get('html_urls', [])}")
        
        verket_events = await scrape_verket_scene(verket_config, client)
        log_info(f"✅ Found {len(verket_events)} events from Verket Scene")
        
        for event in verket_events:
            log_info(f"  - {event.title} at {event.venue} on {event.start}")
        
        all_events.extend(verket_events)
        
        # Save to database
        if all_events:
            log_info(f"💾 Saving {len(all_events)} events to database...")
            db = await get_database()
            
            new_count = 0
            updated_count = 0
            
            for event in all_events:
                saved = await db.save_event(event)
                if saved:
                    new_count += 1
                else:
                    updated_count += 1
            
            log_info(f"✨ {new_count} new events, 🔄 {updated_count} updated events")
        else:
            log_info("ℹ️ No events found to save")
        
    except Exception as e:
        log_error(f"❌ Error during scraping: {e}")
        raise
    finally:
        await client.client.aclose()  # Use aclose() instead of close()
    
    return all_events

if __name__ == "__main__":
    try:
        events = asyncio.run(test_moss_venues())
        print(f"\n🎉 Successfully scraped {len(events)} events from Moss venues!")
        
        # Print summary
        if events:
            print("\n📋 Event Summary:")
            for i, event in enumerate(events[:10], 1):  # Show first 10
                print(f"{i:2d}. {event.title}")
                print(f"    📍 {event.venue}")
                if event.start:
                    oslo_tz = pytz.timezone('Europe/Oslo')
                    local_time = event.start.astimezone(oslo_tz)
                    print(f"    📅 {local_time.strftime('%d.%m.%Y %H:%M')}")
                print(f"    🔗 {event.url}")
                print()
            
            if len(events) > 10:
                print(f"... and {len(events) - 10} more events")
    
    except Exception as e:
        print(f"❌ Failed to scrape events: {e}")
        sys.exit(1)
