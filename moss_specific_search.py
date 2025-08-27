#!/usr/bin/env python3
import requests
import json
import os
from dotenv import load_dotenv

def search_moss_events():
    """Test specific searches for Moss city and nearby area"""
    
    load_dotenv()
    api_key = os.getenv('TICKETMASTER_API_KEY')
    if not api_key:
        print("ERROR: TICKETMASTER_API_KEY not found")
        return
    
    base_url = "https://app.ticketmaster.com/discovery/v2/events.json"
    
    searches = [
        {
            "name": "Search 1: City=Moss",
            "params": {
                'apikey': api_key,
                'city': 'Moss',
                'countryCode': 'NO',
                'size': 20
            }
        },
        {
            "name": "Search 2: Events within 5km of Moss coordinates",
            "params": {
                'apikey': api_key,
                'geoPoint': '59.4369,10.6567',  # Moss coordinates
                'radius': '5',
                'unit': 'km',
                'size': 20
            }
        }
    ]
    
    for search in searches:
        print(f"\n{'='*60}")
        print(f"{search['name']}")
        print(f"Parameters: {search['params']}")
        print(f"{'='*60}")
        
        try:
            response = requests.get(base_url, params=search['params'])
            print(f"Status Code: {response.status_code}")
            print(f"Rate Limit Available: {response.headers.get('Rate-Limit-Available', 'N/A')}")
            
            if response.status_code == 200:
                data = response.json()
                total = data.get('page', {}).get('totalElements', 0)
                events = data.get('_embedded', {}).get('events', [])
                
                print(f"Total events found: {total}")
                print(f"Page info: {data.get('page', {})}")
                
                if events:
                    print(f"\nDetailed event information:")
                    for i, event in enumerate(events):
                        print(f"\nEvent {i+1}:")
                        print(f"  Name: {event.get('name', 'N/A')}")
                        print(f"  Date: {event.get('dates', {}).get('start', {}).get('localDate', 'N/A')}")
                        print(f"  Time: {event.get('dates', {}).get('start', {}).get('localTime', 'N/A')}")
                        
                        # Venue information
                        venue_info = event.get('_embedded', {}).get('venues', [{}])[0]
                        print(f"  Venue: {venue_info.get('name', 'N/A')}")
                        print(f"  City: {venue_info.get('city', {}).get('name', 'N/A')}")
                        print(f"  Address: {venue_info.get('address', {}).get('line1', 'N/A')}")
                        print(f"  Postal Code: {venue_info.get('postalCode', 'N/A')}")
                        
                        # Location coordinates if available
                        location = venue_info.get('location', {})
                        if location:
                            print(f"  Coordinates: {location.get('latitude', 'N/A')}, {location.get('longitude', 'N/A')}")
                        
                        # Classification
                        classifications = event.get('classifications', [{}])[0]
                        print(f"  Category: {classifications.get('segment', {}).get('name', 'N/A')}")
                        print(f"  Genre: {classifications.get('genre', {}).get('name', 'N/A')}")
                        
                        # URL
                        print(f"  URL: {event.get('url', 'N/A')}")
                else:
                    print("No events found")
                    
                # Show full JSON structure for debugging
                print(f"\nFull API Response Structure:")
                print(json.dumps(data, indent=2))
                    
            else:
                print(f"Error Response:")
                print(f"Status: {response.status_code}")
                print(f"Body: {response.text}")
                
        except Exception as e:
            print(f"Request failed: {e}")

if __name__ == "__main__":
    search_moss_events()