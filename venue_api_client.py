
#!/usr/bin/env python3
"""
Venue API Integration Client
Fetches events from partner venues with direct API access
"""

import requests
import sqlite3
import json
from datetime import datetime, timedelta
import logging

class VenueAPIClient:
    def __init__(self):
        self.venues = {
            "moss_kulturhus": {
                "name": "Moss Kulturhus",
                "api_url": "https://www.mosskulturhus.no/api/events",
                "api_key": "YOUR_API_KEY_HERE",
                "auth_method": "header"  # or "basic"
            },
            "verket_scene": {
                "name": "Verket Scene", 
                "api_url": "https://www.verketscene.no/api/events",
                "api_key": "YOUR_API_KEY_HERE",
                "auth_method": "header"
            }
        }
        
    def fetch_venue_events(self, venue_id):
        """Fetch events from a specific venue API"""
        
        venue_config = self.venues.get(venue_id)
        if not venue_config:
            logging.error(f"Unknown venue: {venue_id}")
            return []
        
        try:
            headers = {'User-Agent': 'MossKalender/1.0'}
            
            if venue_config['auth_method'] == 'header':
                headers['X-API-Key'] = venue_config['api_key']
            
            response = requests.get(venue_config['api_url'], headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                events = data.get('events', [])
                logging.info(f"Fetched {len(events)} events from {venue_config['name']}")
                return events
            else:
                logging.error(f"API error from {venue_config['name']}: {response.status_code}")
                return []
                
        except Exception as e:
            logging.error(f"Error fetching from {venue_config['name']}: {e}")
            return []
    
    def save_venue_events(self, events, venue_name):
        """Save venue events to database"""
        
        conn = sqlite3.connect('/var/www/vhosts/herimoss.no/pythoncrawler/events.db')
        cursor = conn.cursor()
        
        saved_count = 0
        for event in events:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO events 
                    (title, venue, description, start_time, end_time, source_url, 
                     price_info, category, status, external_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
                """, (
                    event.get('title'),
                    venue_name,
                    event.get('description'),
                    f"{event.get('start_date')} {event.get('start_time')}",
                    f"{event.get('end_date')} {event.get('end_time')}" if event.get('end_date') else None,
                    event.get('booking_url'),
                    event.get('price'),
                    event.get('category', 'other'),
                    event.get('id')
                ))
                saved_count += 1
            except Exception as e:
                logging.error(f"Error saving event {event.get('title')}: {e}")
        
        conn.commit()
        conn.close()
        
        logging.info(f"Saved {saved_count} events from {venue_name}")
        return saved_count
    
    def sync_all_venues(self):
        """Sync events from all partner venues"""
        
        total_events = 0
        
        for venue_id, venue_config in self.venues.items():
            logging.info(f"Syncing events from {venue_config['name']}...")
            
            events = self.fetch_venue_events(venue_id)
            if events:
                saved = self.save_venue_events(events, venue_config['name'])
                total_events += saved
        
        logging.info(f"Total events synced: {total_events}")
        return total_events

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    client = VenueAPIClient()
    client.sync_all_venues()
    