#!/usr/bin/env python3
"""
Direct database insertion for Moss Kulturhus events.
"""
import asyncio
import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import pytz

# Add the pythoncrawler directory to the path
sys.path.insert(0, '/var/www/vhosts/herimoss.no/pythoncrawler')

from utils import HttpClient
from scrapers.html_scraper import scrape_moss_kulturhus
from logging_utils import init_logging, log_info

def event_to_hash(title, start_time, venue):
    """Generate unique hash for event."""
    data = f"{title}|{start_time}|{venue}".lower()
    return hashlib.md5(data.encode()).hexdigest()

async def scrape_and_save_direct():
    """Scrape Moss Kulturhus and save directly to database."""
    
    # Initialize logging
    init_logging()
    log_info("🎭 Starting Moss Kulturhus scraping with direct DB save...")
    
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
            # Connect to SQLite database
            conn = sqlite3.connect('/var/www/vhosts/herimoss.no/pythoncrawler/events.db')
            cursor = conn.cursor()
            
            saved_count = 0
            now = datetime.now(timezone.utc).isoformat()
            
            for event in events:
                try:
                    # Generate event hash
                    event_hash = event_to_hash(event.title, str(event.start), event.venue or "")
                    
                    # Prepare data
                    start_time = event.start.isoformat() if event.start else now
                    end_time = event.end.isoformat() if event.end else None
                    
                    # Insert or replace event
                    cursor.execute("""
                        INSERT OR REPLACE INTO events (
                            event_hash, title, description, start_time, end_time,
                            venue, address, city, country, price_info, source,
                            source_url, ticket_url, categories, status,
                            created_at, updated_at, first_seen, last_verified
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        event_hash,
                        event.title or "Untitled Event",
                        event.description,
                        start_time,
                        end_time,
                        event.venue or "Moss",
                        event.address,
                        "Moss",
                        "Norway",
                        event.price,
                        "moss_kulturhus",
                        event.url,
                        event.url,  # ticket_url same as url for now
                        json.dumps([event.category]) if hasattr(event, 'category') and event.category else json.dumps(["kultur"]),
                        "active",
                        now,
                        now,
                        now,
                        now
                    ))
                    saved_count += 1
                    
                except Exception as e:
                    log_info(f"Error saving event {event.title}: {e}")
                    continue
            
            # Commit changes
            conn.commit()
            conn.close()
            
            log_info(f"💾 Successfully saved {saved_count} events to database!")
            
            # Show some examples
            log_info("📋 Sample events:")
            oslo_tz = pytz.timezone('Europe/Oslo')
            for i, event in enumerate(events[:5], 1):
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
        count = asyncio.run(scrape_and_save_direct())
        print(f"\n🎉 Successfully processed and saved {count} events from Moss Kulturhus!")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
