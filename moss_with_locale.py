#!/usr/bin/env python3
import requests
import json
import os
from dotenv import load_dotenv

def search_moss_with_norwegian_locale():
    """Search for Moss events using Norwegian locale parameter"""
    
    load_dotenv()
    api_key = os.getenv('TICKETMASTER_API_KEY')
    if not api_key:
        print("ERROR: TICKETMASTER_API_KEY not found")
        return
    
    base_url = "https://app.ticketmaster.com/discovery/v2/events.json"
    
    searches = [
        {
            "name": "1. All events in Norway with Norwegian locale",
            "params": {
                'apikey': api_key,
                'countryCode': 'NO',
                'locale': 'no-no',
                'size': 50
            }
        },
        {
            "name": "2. Events in Moss city with Norwegian locale", 
            "params": {
                'apikey': api_key,
                'city': 'Moss',
                'countryCode': 'NO',
                'locale': 'no-no',
                'size': 20
            }
        },
        {
            "name": "3. Events within 5km of Moss with Norwegian locale",
            "params": {
                'apikey': api_key,
                'geoPoint': '59.4369,10.6567',
                'radius': '5',
                'unit': 'km',
                'locale': 'no-no',
                'size': 20
            }
        },
        {
            "name": "4. Events within 20km of Moss with Norwegian locale",
            "params": {
                'apikey': api_key,
                'geoPoint': '59.4369,10.6567',
                'radius': '20',
                'unit': 'km', 
                'locale': 'no-no',
                'size': 50
            }
        },
        {
            "name": "5. Music events in Moss area with Norwegian locale",
            "params": {
                'apikey': api_key,
                'geoPoint': '59.4369,10.6567',
                'radius': '20',
                'unit': 'km',
                'classificationName': 'music',
                'locale': 'no-no',
                'size': 20
            }
        }
    ]
    
    for search in searches:
        print(f"\n{'='*80}")
        print(f"{search['name']}")
        print(f"Parameters: {search['params']}")
        print(f"{'='*80}")
        
        try:
            response = requests.get(base_url, params=search['params'])
            print(f"Status: {response.status_code}")
            print(f"Rate Limit: {response.headers.get('Rate-Limit-Available', 'N/A')}")
            
            if response.status_code == 200:
                data = response.json()
                total = data.get('page', {}).get('totalElements', 0)
                events = data.get('_embedded', {}).get('events', [])
                
                print(f"Total events found: {total}")
                
                if events:
                    print(f"\nEvents:")
                    for i, event in enumerate(events):
                        name = event.get('name', 'N/A')
                        date = event.get('dates', {}).get('start', {}).get('localDate', 'N/A')
                        time = event.get('dates', {}).get('start', {}).get('localTime', 'N/A')
                        
                        venue_info = event.get('_embedded', {}).get('venues', [{}])[0]
                        venue_name = venue_info.get('name', 'N/A')
                        city = venue_info.get('city', {}).get('name', 'N/A')
                        
                        # Distance calculation if coordinates available
                        location = venue_info.get('location', {})
                        distance_info = ""
                        if location.get('latitude') and location.get('longitude'):
                            lat = float(location.get('latitude'))
                            lon = float(location.get('longitude'))
                            # Simple distance calculation from Moss center
                            moss_lat, moss_lon = 59.4369, 10.6567
                            dist = ((lat - moss_lat)**2 + (lon - moss_lon)**2)**0.5 * 111  # Rough km conversion
                            distance_info = f" (~{dist:.1f}km from Moss)"
                        
                        print(f"\n{i+1:2d}. {name}")
                        print(f"    Date: {date} {time}")
                        print(f"    Venue: {venue_name}, {city}{distance_info}")
                        
                        # Show classification
                        classifications = event.get('classifications', [{}])[0]
                        category = classifications.get('segment', {}).get('name', 'N/A')
                        genre = classifications.get('genre', {}).get('name', 'N/A')
                        print(f"    Category: {category} / {genre}")
                        
                        # Show URL
                        url = event.get('url', 'N/A')
                        print(f"    URL: {url}")
                        
                        if i >= 19:  # Limit display to first 20 events
                            if total > 20:
                                print(f"\n    ... and {total - 20} more events")
                            break
                else:
                    print("No events found")
                    
            elif response.status_code == 429:
                print("❌ Rate limit exceeded - pausing")
                import time
                time.sleep(2)
                
            else:
                print(f"Error: {response.status_code}")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"Request failed: {e}")

if __name__ == "__main__":
    search_moss_with_norwegian_locale()