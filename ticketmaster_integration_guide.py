#!/usr/bin/env python3
"""
Ticketmaster Discovery API Integration Guide
Guide for setting up Ticketmaster Developer account and API integration
"""

import json

def create_ticketmaster_setup_guide():
    """
    Complete guide for Ticketmaster API integration
    """
    
    setup_guide = {
        "ticketmaster_developer_setup": {
            "api_name": "Ticketmaster Discovery API",
            "documentation": "https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/",
            "registration": "https://developer.ticketmaster.com/",
            
            "application_details": {
                "application_name_suggestions": [
                    "Moss Kulturkalender",
                    "Herimoss Event Calendar",
                    "Moss Cultural Events Aggregator",
                    "Local Events Norway - Moss",
                    "MossEvents.no API Client"
                ],
                
                "redirect_uri_suggestions": [
                    "https://herimoss.no/api/ticketmaster/callback",
                    "https://herimoss.no/auth/ticketmaster",
                    "https://www.herimoss.no/api/oauth/ticketmaster",
                    "http://localhost:8000/callback",  # For testing
                    "https://herimoss.no/admin/integrations/ticketmaster"
                ],
                
                "logo_url_suggestions": [
                    "https://herimoss.no/assets/logo.png",
                    "https://herimoss.no/images/moss-kalender-logo.png",
                    "https://raw.githubusercontent.com/yourusername/moss-events/main/logo.png",
                    # Note: Logo must be publicly accessible HTTPS URL
                    # Recommended size: 300x300px, PNG or JPG
                ]
            },
            
            "api_key_setup": {
                "authentication_type": "API Key (Consumer Key)",
                "no_oauth_required": "For basic Discovery API access",
                "rate_limits": "5000 requests per day (free tier)",
                "paid_plans": "Available for higher limits"
            }
        },
        
        "api_endpoints_for_moss": {
            "event_search": {
                "endpoint": "https://app.ticketmaster.com/discovery/v2/events.json",
                "parameters": {
                    "city": "Moss",
                    "countryCode": "NO",
                    "classificationName": "Music,Arts & Theatre",
                    "size": "20",
                    "sort": "date,asc",
                    "apikey": "YOUR_API_KEY"
                },
                "example_url": "https://app.ticketmaster.com/discovery/v2/events.json?city=Moss&countryCode=NO&classificationName=Music&apikey=YOUR_KEY"
            },
            
            "venue_search": {
                "endpoint": "https://app.ticketmaster.com/discovery/v2/venues.json",
                "parameters": {
                    "city": "Moss",
                    "countryCode": "NO",
                    "apikey": "YOUR_API_KEY"
                }
            },
            
            "event_details": {
                "endpoint": "https://app.ticketmaster.com/discovery/v2/events/{id}.json",
                "description": "Get detailed information about a specific event"
            }
        },
        
        "implementation_steps": [
            "1. Register at https://developer.ticketmaster.com/",
            "2. Create new application with suggested names above",
            "3. Add redirect URI (use production URL)",
            "4. Upload logo (300x300px PNG recommended)",
            "5. Get API Consumer Key",
            "6. Test API with curl or Postman",
            "7. Implement Python client",
            "8. Add to automated scraping system"
        ],
        
        "python_implementation": '''
import requests
import json
from datetime import datetime

class TicketmasterAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://app.ticketmaster.com/discovery/v2"
        
    def search_events_in_moss(self, classification="Music,Arts & Theatre"):
        """Search for events in Moss, Norway"""
        
        params = {
            "city": "Moss",
            "countryCode": "NO", 
            "classificationName": classification,
            "size": 50,
            "sort": "date,asc",
            "apikey": self.api_key
        }
        
        try:
            response = requests.get(f"{self.base_url}/events.json", params=params)
            if response.status_code == 200:
                data = response.json()
                return data.get("_embedded", {}).get("events", [])
            else:
                print(f"API Error: {response.status_code}")
                return []
        except Exception as e:
            print(f"Error: {e}")
            return []
    
    def get_event_details(self, event_id):
        """Get detailed information about a specific event"""
        
        try:
            url = f"{self.base_url}/events/{event_id}.json"
            params = {"apikey": self.api_key}
            
            response = requests.get(url, params=params)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error getting event details: {e}")
            return None

# Usage example:
# api = TicketmasterAPI("YOUR_API_KEY_HERE")
# events = api.search_events_in_moss()
# for event in events:
#     print(f"{event['name']} - {event['dates']['start']['localDate']}")
        ''',
        
        "data_mapping": {
            "ticketmaster_to_moss_db": {
                "title": "event['name']",
                "venue": "event['_embedded']['venues'][0]['name']",
                "start_time": "event['dates']['start']['localDate'] + event['dates']['start']['localTime']",
                "description": "event['info'] or event['pleaseNote']",
                "price": "event['priceRanges'][0] (if available)",
                "booking_url": "event['url']",
                "category": "event['classifications'][0]['segment']['name']",
                "external_id": "event['id']"
            }
        },
        
        "error_handling": {
            "common_errors": {
                "401": "Invalid API key",
                "403": "Rate limit exceeded or API access denied",
                "404": "No events found for the criteria",
                "429": "Too many requests - implement rate limiting"
            },
            "best_practices": [
                "Implement exponential backoff for rate limiting",
                "Cache API responses to reduce requests",
                "Monitor daily API usage",
                "Handle empty results gracefully",
                "Store API responses for debugging"
            ]
        }
    }
    
    return setup_guide

def generate_ticketmaster_client():
    """Generate complete Ticketmaster API client"""
    
    client_code = '''#!/usr/bin/env python3
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

logging.basicConfig(level=logging.INFO)

class MossTicketmasterClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://app.ticketmaster.com/discovery/v2"
        self.requests_made = 0
        self.daily_limit = 5000
        
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
        
        conn = sqlite3.connect('/var/www/vhosts/herimoss.no/pythoncrawler/events.db')
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
    # Replace with your actual API key
    API_KEY = "YOUR_TICKETMASTER_API_KEY_HERE"
    
    if API_KEY == "YOUR_TICKETMASTER_API_KEY_HERE":
        print("⚠️  Please set your Ticketmaster API key in the script")
        print("Get your key from: https://developer.ticketmaster.com/")
    else:
        client = MossTicketmasterClient(API_KEY)
        client.sync_ticketmaster_events()
    '''
    
    return client_code

def main():
    """Main function to generate Ticketmaster setup guide"""
    print("🎫 TICKETMASTER API INTEGRATION GUIDE")
    print("=" * 45)
    
    guide = create_ticketmaster_setup_guide()
    
    # Developer account setup
    print("\n📝 DEVELOPER ACCOUNT SETUP:")
    dev_setup = guide['ticketmaster_developer_setup']
    
    print(f"Registration URL: {dev_setup['registration']}")
    print(f"Documentation: {dev_setup['documentation']}")
    
    print("\n🏷️  APPLICATION DETAILS for your developer account:")
    app_details = dev_setup['application_details']
    
    print("\nApplication Name suggestions:")
    for name in app_details['application_name_suggestions']:
        print(f"  • {name}")
    
    print("\nRedirect URI suggestions:")
    for uri in app_details['redirect_uri_suggestions']:
        print(f"  • {uri}")
    
    print("\nLogo URL suggestions:")
    for logo in app_details['logo_url_suggestions']:
        print(f"  • {logo}")
    print("  📝 Note: Logo must be publicly accessible HTTPS URL, 300x300px recommended")
    
    # API implementation
    print(f"\n🔧 API IMPLEMENTATION:")
    print("Rate limits: 5000 requests/day (free tier)")
    print("Authentication: API Key only (no OAuth required)")
    
    # Example API calls
    endpoints = guide['api_endpoints_for_moss']
    print(f"\n📡 KEY API ENDPOINTS:")
    print(f"Events: {endpoints['event_search']['endpoint']}")
    print(f"Example: {endpoints['event_search']['example_url']}")
    
    # Save files
    client_code = generate_ticketmaster_client()
    
    with open('/var/www/vhosts/herimoss.no/pythoncrawler/ticketmaster_setup_guide.json', 'w', encoding='utf-8') as f:
        json.dump(guide, f, indent=2, ensure_ascii=False)
    
    with open('/var/www/vhosts/herimoss.no/pythoncrawler/ticketmaster_client.py', 'w') as f:
        f.write(client_code)
    
    print(f"\n✅ Ticketmaster setup files created:")
    print(f"  • ticketmaster_setup_guide.json (complete guide)")
    print(f"  • ticketmaster_client.py (ready-to-use client)")
    
    print(f"\n🚀 IMPLEMENTATION STEPS:")
    for i, step in enumerate(guide['implementation_steps'], 1):
        print(f"{i}. {step}")
    
    print(f"\n⚠️  IMPORTANT:")
    print(f"- Use your production domain (herimoss.no) for Redirect URI")
    print(f"- Logo must be publicly accessible via HTTPS")
    print(f"- API key will be provided after application approval")
    print(f"- Test thoroughly before going live")

if __name__ == "__main__":
    main()
