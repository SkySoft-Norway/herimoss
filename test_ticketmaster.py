#!/usr/bin/env python3
import requests
import json
import sys
import os
from dotenv import load_dotenv

def test_ticketmaster_api():
    """Test Ticketmaster API access with Moss, Norway search"""
    
    # Load environment variables
    load_dotenv()
    
    # Get API key from environment
    api_key = os.getenv('TICKETMASTER_API_KEY')
    if not api_key:
        print("ERROR: TICKETMASTER_API_KEY not found in .env file")
        return
    
    # Ticketmaster Discovery API endpoint
    base_url = "https://app.ticketmaster.com/discovery/v2/events.json"
    
    # Parameters for Moss, Norway
    params = {
        'apikey': api_key,
        'city': 'Moss',
        'countryCode': 'NO',
        'size': 10
    }
    
    print("Testing Ticketmaster API access...")
    print(f"URL: {base_url}")
    print(f"Parameters: {params}")
    print("-" * 50)
    
    try:
        # Make the API request
        response = requests.get(base_url, params=params)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print("-" * 50)
        
        if response.status_code == 200:
            data = response.json()
            print("API Response (JSON):")
            print(json.dumps(data, indent=2))
        else:
            print("Error Response:")
            print(response.text)
            
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
    except json.JSONDecodeError as e:
        print(f"JSON decode failed: {e}")
        print("Raw response:", response.text)

if __name__ == "__main__":
    test_ticketmaster_api()