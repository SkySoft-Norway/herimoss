#!/usr/bin/env python3
import requests
import json
import os
from dotenv import load_dotenv

def test_specific_ticketmaster_events():
    """Test accessing specific Ticketmaster event IDs from Verket Scene website"""
    
    load_dotenv()
    api_key = os.getenv('TICKETMASTER_API_KEY')
    if not api_key:
        print("ERROR: TICKETMASTER_API_KEY not found")
        return
    
    # Event IDs extracted from Verket Scene website
    event_ids = [
        "1649387173",  # Levi Henriksen & Babylon Badlands
        "514232765",   # Cir. Cuz  
        "867349075",   # The Impossible Green
        "1659579801",  # Serve and protect
        "1813775691",  # Standup Moss
        "525128975",   # Honningbarna
        "737810214"    # Sondre Lerche
    ]
    
    base_url = "https://app.ticketmaster.com/discovery/v2/events"
    
    for event_id in event_ids:
        print(f"\n{'='*70}")
        print(f"Testing Event ID: {event_id}")
        print(f"{'='*70}")
        
        try:
            # Try direct event lookup
            event_url = f"{base_url}/{event_id}.json"
            params = {'apikey': api_key}
            
            print(f"URL: {event_url}")
            print(f"Params: {params}")
            
            response = requests.get(event_url, params=params)
            print(f"Status: {response.status_code}")
            print(f"Rate Limit: {response.headers.get('Rate-Limit-Available', 'N/A')}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ SUCCESS - Found event:")
                print(f"  Name: {data.get('name', 'N/A')}")
                print(f"  Date: {data.get('dates', {}).get('start', {}).get('localDate', 'N/A')}")
                print(f"  Time: {data.get('dates', {}).get('start', {}).get('localTime', 'N/A')}")
                
                venue_info = data.get('_embedded', {}).get('venues', [{}])[0]
                print(f"  Venue: {venue_info.get('name', 'N/A')}")
                print(f"  Venue ID: {venue_info.get('id', 'N/A')}")
                print(f"  City: {venue_info.get('city', {}).get('name', 'N/A')}")
                
            elif response.status_code == 404:
                print(f"❌ Event not found - {response.status_code}")
            else:
                print(f"❌ Error - {response.status_code}: {response.text}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")

    # Also test search with different parameters
    print(f"\n{'='*70}")
    print("Testing alternative search approaches")
    print(f"{'='*70}")
    
    searches = [
        {
            "name": "Search with source parameter",
            "params": {
                'apikey': api_key,
                'venueId': 'Z698xZb_Za7Ia',
                'source': 'ticketmaster,universe',
                'size': 20
            }
        },
        {
            "name": "Search including test events",
            "params": {
                'apikey': api_key,
                'venueId': 'Z698xZb_Za7Ia', 
                'includeTest': 'yes',
                'size': 20
            }
        },
        {
            "name": "Search with TBA/TBD events",
            "params": {
                'apikey': api_key,
                'venueId': 'Z698xZb_Za7Ia',
                'includeTBA': 'yes',
                'includeTBD': 'yes',
                'size': 20
            }
        }
    ]
    
    search_url = "https://app.ticketmaster.com/discovery/v2/events.json"
    
    for search in searches:
        print(f"\n{search['name']}:")
        try:
            response = requests.get(search_url, params=search['params'])
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                total = data.get('page', {}).get('totalElements', 0)
                print(f"Events found: {total}")
                
                if total > 0:
                    events = data.get('_embedded', {}).get('events', [])
                    for event in events[:3]:
                        print(f"  - {event.get('name', 'N/A')} - {event.get('dates', {}).get('start', {}).get('localDate', 'N/A')}")
                        
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_specific_ticketmaster_events()