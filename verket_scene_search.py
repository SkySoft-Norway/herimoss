#!/usr/bin/env python3
import requests
import json
import os
from dotenv import load_dotenv

def search_verket_scene():
    """Search for Verket Scene venue and events using multiple approaches"""
    
    load_dotenv()
    api_key = os.getenv('TICKETMASTER_API_KEY')
    if not api_key:
        print("ERROR: TICKETMASTER_API_KEY not found")
        return
    
    base_url = "https://app.ticketmaster.com/discovery/v2"
    
    searches = [
        {
            "name": "1. Search events by keyword 'Verket Scene'",
            "endpoint": "/events.json",
            "params": {
                'apikey': api_key,
                'keyword': 'Verket Scene',
                'countryCode': 'NO',
                'size': 20
            }
        },
        {
            "name": "2. Search events by keyword 'Verket'",
            "endpoint": "/events.json", 
            "params": {
                'apikey': api_key,
                'keyword': 'Verket',
                'countryCode': 'NO',
                'size': 20
            }
        },
        {
            "name": "3. Search venues by name 'Verket Scene'",
            "endpoint": "/venues.json",
            "params": {
                'apikey': api_key,
                'keyword': 'Verket Scene',
                'countryCode': 'NO',
                'size': 20
            }
        },
        {
            "name": "4. Search venues by name 'Verket'",
            "endpoint": "/venues.json",
            "params": {
                'apikey': api_key,
                'keyword': 'Verket',
                'countryCode': 'NO', 
                'size': 20
            }
        },
        {
            "name": "5. Search venues in Moss city",
            "endpoint": "/venues.json",
            "params": {
                'apikey': api_key,
                'city': 'Moss',
                'countryCode': 'NO',
                'size': 20
            }
        },
        {
            "name": "6. Search all venues within 10km of Moss",
            "endpoint": "/venues.json",
            "params": {
                'apikey': api_key,
                'geoPoint': '59.4369,10.6567',
                'radius': '10',
                'unit': 'km',
                'size': 20
            }
        },
        {
            "name": "7. Search events with broader Moss area terms",
            "endpoint": "/events.json",
            "params": {
                'apikey': api_key,
                'keyword': 'Moss',
                'countryCode': 'NO',
                'size': 20
            }
        }
    ]
    
    for search in searches:
        print(f"\n{'='*80}")
        print(f"{search['name']}")
        print(f"Endpoint: {search['endpoint']}")
        print(f"Parameters: {search['params']}")
        print(f"{'='*80}")
        
        try:
            url = base_url + search['endpoint']
            response = requests.get(url, params=search['params'])
            print(f"Status Code: {response.status_code}")
            print(f"Rate Limit Available: {response.headers.get('Rate-Limit-Available', 'N/A')}")
            
            if response.status_code == 200:
                data = response.json()
                total = data.get('page', {}).get('totalElements', 0)
                print(f"Total results found: {total}")
                
                # Handle events
                if 'events' in search['endpoint']:
                    events = data.get('_embedded', {}).get('events', [])
                    if events:
                        print(f"\nEvents found:")
                        for i, event in enumerate(events):
                            print(f"\nEvent {i+1}:")
                            print(f"  Name: {event.get('name', 'N/A')}")
                            print(f"  Date: {event.get('dates', {}).get('start', {}).get('localDate', 'N/A')}")
                            
                            venue_info = event.get('_embedded', {}).get('venues', [{}])[0]
                            print(f"  Venue: {venue_info.get('name', 'N/A')}")
                            print(f"  City: {venue_info.get('city', {}).get('name', 'N/A')}")
                            print(f"  Address: {venue_info.get('address', {}).get('line1', 'N/A')}")
                
                # Handle venues
                elif 'venues' in search['endpoint']:
                    venues = data.get('_embedded', {}).get('venues', [])
                    if venues:
                        print(f"\nVenues found:")
                        for i, venue in enumerate(venues):
                            print(f"\nVenue {i+1}:")
                            print(f"  Name: {venue.get('name', 'N/A')}")
                            print(f"  City: {venue.get('city', {}).get('name', 'N/A')}")
                            print(f"  Address: {venue.get('address', {}).get('line1', 'N/A')}")
                            print(f"  Postal Code: {venue.get('postalCode', 'N/A')}")
                            location = venue.get('location', {})
                            if location:
                                print(f"  Coordinates: {location.get('latitude', 'N/A')}, {location.get('longitude', 'N/A')}")
                            print(f"  Venue ID: {venue.get('id', 'N/A')}")
                
                if total == 0:
                    print("No results found")
                    
            else:
                print(f"Error Response:")
                print(f"Status: {response.status_code}")
                print(f"Body: {response.text}")
                
        except Exception as e:
            print(f"Request failed: {e}")

if __name__ == "__main__":
    search_verket_scene()