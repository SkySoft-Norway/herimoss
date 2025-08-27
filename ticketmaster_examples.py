#!/usr/bin/env python3
import requests
import json
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

def test_ticketmaster_searches():
    """Test 10 different Ticketmaster API search examples"""
    
    load_dotenv()
    api_key = os.getenv('TICKETMASTER_API_KEY')
    if not api_key:
        print("ERROR: TICKETMASTER_API_KEY not found")
        return
    
    base_url = "https://app.ticketmaster.com/discovery/v2/events.json"
    
    # Calculate date ranges
    today = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
    next_month = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    searches = [
        {
            "name": "1. All events in Norway",
            "params": {
                'apikey': api_key,
                'countryCode': 'NO',
                'size': 20
            }
        },
        {
            "name": "2. Music events in Norway",
            "params": {
                'apikey': api_key,
                'countryCode': 'NO',
                'classificationName': 'music',
                'size': 20
            }
        },
        {
            "name": "3. Events in Oslo (closest major city)",
            "params": {
                'apikey': api_key,
                'city': 'Oslo',
                'countryCode': 'NO',
                'size': 20
            }
        },
        {
            "name": "4. Events within 100km of Moss coordinates",
            "params": {
                'apikey': api_key,
                'geoPoint': '59.4369,10.6567',  # Moss coordinates
                'radius': '100',
                'unit': 'km',
                'size': 20
            }
        },
        {
            "name": "5. Sports events in Norway",
            "params": {
                'apikey': api_key,
                'countryCode': 'NO',
                'classificationName': 'sports',
                'size': 20
            }
        },
        {
            "name": "6. Events in next 30 days in Norway",
            "params": {
                'apikey': api_key,
                'countryCode': 'NO',
                'startDateTime': today,
                'endDateTime': next_month,
                'size': 20
            }
        },
        {
            "name": "7. Family-friendly events in Norway",
            "params": {
                'apikey': api_key,
                'countryCode': 'NO',
                'includeFamily': 'yes',
                'size': 20
            }
        },
        {
            "name": "8. Theater/Arts events in Norway",
            "params": {
                'apikey': api_key,
                'countryCode': 'NO',
                'classificationName': 'arts',
                'size': 20
            }
        },
        {
            "name": "9. Events by keyword 'festival' in Norway",
            "params": {
                'apikey': api_key,
                'countryCode': 'NO',
                'keyword': 'festival',
                'size': 20
            }
        },
        {
            "name": "10. Events in postal codes around Moss (1500-1599)",
            "params": {
                'apikey': api_key,
                'postalCode': '1500',
                'countryCode': 'NO',
                'size': 20
            }
        }
    ]
    
    for search in searches:
        print(f"\n{'='*60}")
        print(f"{search['name']}")
        print(f"{'='*60}")
        
        try:
            response = requests.get(base_url, params=search['params'])
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                total = data.get('page', {}).get('totalElements', 0)
                events = data.get('_embedded', {}).get('events', [])
                
                print(f"Total events found: {total}")
                
                if events:
                    print(f"First few events:")
                    for i, event in enumerate(events[:3]):
                        name = event.get('name', 'N/A')
                        date = event.get('dates', {}).get('start', {}).get('localDate', 'N/A')
                        venue_info = event.get('_embedded', {}).get('venues', [{}])[0]
                        venue_name = venue_info.get('name', 'N/A')
                        city = venue_info.get('city', {}).get('name', 'N/A')
                        print(f"  {i+1}. {name} - {date} - {venue_name}, {city}")
                else:
                    print("No events found")
                    
            else:
                print(f"Error: {response.text}")
                
        except Exception as e:
            print(f"Request failed: {e}")

if __name__ == "__main__":
    test_ticketmaster_searches()