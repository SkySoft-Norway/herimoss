#!/usr/bin/env python3
import requests
import json
import os
from dotenv import load_dotenv

def test_regional_coverage():
    """Test if the API supports Norwegian events and check regional settings"""
    
    load_dotenv()
    api_key = os.getenv('TICKETMASTER_API_KEY')
    if not api_key:
        print("ERROR: TICKETMASTER_API_KEY not found")
        return
    
    base_url = "https://app.ticketmaster.com/discovery/v2"
    
    tests = [
        {
            "name": "1. Check supported countries list",
            "endpoint": "/classifications/countries.json",
            "params": {'apikey': api_key}
        },
        {
            "name": "2. Search events with locale parameter (Norwegian)",
            "endpoint": "/events.json",
            "params": {
                'apikey': api_key,
                'venueId': 'Z698xZb_Za7Ia',
                'locale': 'no-no',
                'size': 20
            }
        },
        {
            "name": "3. Search events with market/dma for Norway",
            "endpoint": "/events.json", 
            "params": {
                'apikey': api_key,
                'venueId': 'Z698xZb_Za7Ia',
                'marketId': 'NO',
                'size': 20
            }
        },
        {
            "name": "4. Search events with broader date range",
            "endpoint": "/events.json",
            "params": {
                'apikey': api_key,
                'venueId': 'Z698xZb_Za7Ia',
                'startDateTime': '2024-01-01T00:00:00Z',
                'endDateTime': '2026-12-31T23:59:59Z',
                'size': 50
            }
        },
        {
            "name": "5. Check available markets/DMAs",
            "endpoint": "/classifications/dmas.json",
            "params": {'apikey': api_key}
        },
        {
            "name": "6. Search with alternative venue IDs from our previous results",
            "endpoint": "/events.json",
            "params": {
                'apikey': api_key,
                'venueId': 'Z698xZb_ZaAE-',  # Rabben - Verket Moss
                'size': 20
            }
        }
    ]
    
    for test in tests:
        print(f"\n{'='*80}")
        print(f"{test['name']}")
        print(f"Endpoint: {test['endpoint']}")
        print(f"Parameters: {test['params']}")
        print(f"{'='*80}")
        
        try:
            url = base_url + test['endpoint']
            response = requests.get(url, params=test['params'])
            print(f"Status: {response.status_code}")
            print(f"Rate Limit: {response.headers.get('Rate-Limit-Available', 'N/A')}")
            
            if response.status_code == 200:
                data = response.json()
                
                # Handle different response types
                if 'countries' in test['endpoint']:
                    countries = data.get('_embedded', {}).get('countries', [])
                    print(f"Total countries: {len(countries)}")
                    norway_found = False
                    for country in countries:
                        if country.get('countryCode') == 'NO' or 'norway' in country.get('name', '').lower():
                            print(f"✅ FOUND NORWAY: {country}")
                            norway_found = True
                            break
                    if not norway_found:
                        print("❌ Norway not found in countries list")
                        print("First 10 countries:")
                        for country in countries[:10]:
                            print(f"  - {country.get('name', 'N/A')} ({country.get('countryCode', 'N/A')})")
                
                elif 'dmas' in test['endpoint']:
                    dmas = data.get('_embedded', {}).get('dmas', [])
                    print(f"Total DMAs: {len(dmas)}")
                    print("Sample DMAs:")
                    for dma in dmas[:10]:
                        print(f"  - {dma.get('name', 'N/A')} ({dma.get('id', 'N/A')})")
                
                else:  # Events search
                    total = data.get('page', {}).get('totalElements', 0)
                    print(f"Total events: {total}")
                    
                    events = data.get('_embedded', {}).get('events', [])
                    if events:
                        print("Events found:")
                        for event in events:
                            print(f"  - {event.get('name', 'N/A')} - {event.get('dates', {}).get('start', {}).get('localDate', 'N/A')}")
                    elif total == 0:
                        print("No events found")
                        
            elif response.status_code == 429:
                print(f"❌ Rate limit exceeded")
                break
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    test_regional_coverage()