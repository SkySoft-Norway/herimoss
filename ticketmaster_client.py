#!/usr/bin/env python3
"""
Ticketmaster API Client for Moss Events
Complete implementation with error handling and database integration
"""

import requests
import sqlite3
import json
import time
from datetime import datetime, timedelta
import logging
from config_manager import config

logging.basicConfig(level=logging.INFO)

class MossTicketmasterClient:
    def __init__(self, api_key=None):
        # Load configuration from .env
        tm_config = config.get_ticketmaster_config()
        
        self.api_key = api_key or tm_config['api_key']
        self.base_url = tm_config['base_url']
        self.daily_limit = tm_config['rate_limit']
        self.requests_made = 0
        
        if not self.api_key or self.api_key == 'YOUR_TICKETMASTER_API_KEY_HERE':
            raise ValueError("Ticketmaster API key not configured. Please update .env file.")
        
        logging.info(f"🎫 Initialized Ticketmaster client with {self.daily_limit} daily requests")
        
    def search_moss_events(self):
        """Search for all events in Moss area"""
        
        all_events = []
        
        # Different classifications to search
        classifications = [
            "Music",
            "Arts & Theatre", 
            "Film",
            "Miscellaneous"
        ]
        
        for classification in classifications:
            logging.info(f"Searching for {classification} events...")
            
            events = self._search_events_by_classification(classification)
            all_events.extend(events)
            
            # Rate limiting
            time.sleep(0.2)  # 200ms between requests
            
        # Remove duplicates based on event ID
        unique_events = {}
        for event in all_events:
            unique_events[event['id']] = event
            
        logging.info(f"Found {len(unique_events)} unique events from Ticketmaster")
        return list(unique_events.values())
    
    def _search_events_by_classification(self, classification):
        """Search events by specific classification"""
        
        params = {
            "city": "Moss",
            "countryCode": "NO",
            "classificationName": classification,
            "size": 50,
            "sort": "date,asc", 
            "apikey": self.api_key,
            "startDateTime": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endDateTime": (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        
        try:
            response = requests.get(f"{self.base_url}/events.json", params=params, timeout=10)
            self.requests_made += 1
            
            if response.status_code == 200:
                data = response.json()
                events = data.get("_embedded", {}).get("events", [])
                return events
            elif response.status_code == 429:
                logging.warning("Rate limit hit, waiting...")
                time.sleep(60)  # Wait 1 minute
                return []
            else:
                logging.error(f"API Error {response.status_code}: {response.text}")
                return []
                
        except Exception as e:
            logging.error(f"Error searching {classification}: {e}")
            return []
    
    def process_ticketmaster_event(self, tm_event):
        """Convert Ticketmaster event to our database format"""
        
        try:
            # Basic event info
            title = tm_event.get('name', 'Unknown Event')
            event_id = tm_event.get('id')
            url = tm_event.get('url', '')
            
            # Date and time
            dates = tm_event.get('dates', {}).get('start', {})
            start_date = dates.get('localDate')
            start_time = dates.get('localTime', '19:00')  # Default time
            
            if start_date:
                start_datetime = f"{start_date} {start_time}"
            else:
                start_datetime = None
            
            # Venue information
            venues = tm_event.get('_embedded', {}).get('venues', [])
            venue_name = venues[0].get('name') if venues else 'Moss'
            
            # Price information
            price_ranges = tm_event.get('priceRanges', [])
            price_info = ""
            if price_ranges:
                min_price = price_ranges[0].get('min', 0)
                max_price = price_ranges[0].get('max', 0)
                currency = price_ranges[0].get('currency', 'NOK')
                price_info = f"{min_price}-{max_price} {currency}"
            
            # Category
            classifications = tm_event.get('classifications', [{}])
            category = classifications[0].get('segment', {}).get('name', 'other').lower()
            
            # Description
            description = tm_event.get('info', '') or tm_event.get('pleaseNote', '')
            
            return {
                'title': title,
                'venue': venue_name,
                'start_time': start_datetime,
                'description': description,
                'source_url': url,
                'price_info': price_info,
                'category': category,
                'external_id': event_id,
                'source': 'ticketmaster'
            }
            
        except Exception as e:
            logging.error(f"Error processing Ticketmaster event: {e}")
            return None
    
    def save_events_to_database(self, events):
        """Save Ticketmaster events to database"""
        
        # Save to database
        conn = sqlite3.connect(config.get('DATABASE_PATH', '/var/www/vhosts/herimoss.no/pythoncrawler/events.db'))
        cursor = conn.cursor()
        
        saved_count = 0
        for tm_event in events:
            processed_event = self.process_ticketmaster_event(tm_event)
            
            if processed_event:
                try:
                    cursor.execute("""
                        INSERT OR REPLACE INTO events 
                        (title, venue, start_time, description, source_url, 
                         price_info, category, status, external_id, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
                    """, (
                        processed_event['title'],
                        processed_event['venue'],
                        processed_event['start_time'],
                        processed_event['description'],
                        processed_event['source_url'],
                        processed_event['price_info'],
                        processed_event['category'],
                        processed_event['external_id'],
                        processed_event['source']
                    ))
                    saved_count += 1
                except Exception as e:
                    logging.error(f"Database error for {processed_event['title']}: {e}")
        
        conn.commit()
        conn.close()
        
        logging.info(f"Saved {saved_count} Ticketmaster events to database")
        return saved_count
    
    def sync_ticketmaster_events(self):
        """Complete sync of Ticketmaster events"""
        
        logging.info("🎫 Starting Ticketmaster sync for Moss...")
        
        if self.requests_made >= self.daily_limit:
            logging.warning("Daily API limit reached, skipping sync")
            return 0
        
        # Search for events
        events = self.search_moss_events()
        
        if events:
            # Save to database
            saved_count = self.save_events_to_database(events)
            
            logging.info(f"✅ Ticketmaster sync completed: {saved_count} events saved")
            logging.info(f"📊 API requests used: {self.requests_made}/{self.daily_limit}")
            
            return saved_count
        else:
            logging.info("No Ticketmaster events found for Moss")
            return 0

if __name__ == "__main__":
    # Load API key from configuration
    try:
        client = MossTicketmasterClient()
        client.sync_ticketmaster_events()
    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
        print("💡 Please update your .env file with:")
        print("   TICKETMASTER_API_KEY=your_actual_api_key_here")
        print("   Get your key from: https://developer.ticketmaster.com/")
    