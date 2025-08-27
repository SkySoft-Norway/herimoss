#!/usr/bin/env python3
"""
Ticketmaster API Setup and Testing Script
Use this to test your Ticketmaster API credentials and connection
"""

import requests
import json
from config_manager import config

def test_ticketmaster_api():
    """Test Ticketmaster API connection and credentials"""
    
    print("🎫 TICKETMASTER API SETUP AND TESTING")
    print("=" * 45)
    
    # Validate configuration
    validation = config.validate_ticketmaster_config()
    
    print(f"\n🔧 CONFIGURATION VALIDATION:")
    print(f"Status: {'✅ VALID' if validation['valid'] else '❌ INVALID'}")
    
    if validation['errors']:
        print("❌ Configuration Errors:")
        for error in validation['errors']:
            print(f"   • {error}")
        print(f"\n💡 TO FIX:")
        print(f"1. Edit /var/www/vhosts/herimoss.no/pythoncrawler/.env")
        print(f"2. Set TICKETMASTER_API_KEY=your_actual_api_key")
        print(f"3. Get API key from: https://developer.ticketmaster.com/")
        return False
    
    tm_config = validation['config']
    print(f"✅ API Key: {'Set' if tm_config['api_key'] != 'YOUR_TICKETMASTER_API_KEY_HERE' else 'Not set'}")
    print(f"✅ Base URL: {tm_config['base_url']}")
    print(f"✅ Rate Limit: {tm_config['rate_limit']} requests/day")
    
    # Test API connection
    print(f"\n🌐 API CONNECTION TEST:")
    
    api_key = tm_config['api_key']
    base_url = tm_config['base_url']
    
    # Test 1: Simple API call
    test_url = f"{base_url}/events.json"
    test_params = {
        'apikey': api_key,
        'size': 1,
        'countryCode': 'NO'
    }
    
    try:
        print("Testing basic API connection...")
        response = requests.get(test_url, params=test_params, timeout=10)
        
        if response.status_code == 200:
            print("✅ API Connection: SUCCESS")
            data = response.json()
            total_events = data.get('page', {}).get('totalElements', 0)
            print(f"✅ API Response: {total_events} total events found in Norway")
        elif response.status_code == 401:
            print("❌ API Connection: UNAUTHORIZED")
            print("   Your API key is invalid or expired")
            return False
        elif response.status_code == 403:
            print("❌ API Connection: FORBIDDEN")
            print("   Your API key may not have the required permissions")
            return False
        else:
            print(f"❌ API Connection: HTTP {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ API Connection: ERROR - {e}")
        return False
    
    # Test 2: Moss-specific search
    print(f"\n🏛️ MOSS EVENTS TEST:")
    
    moss_params = {
        'apikey': api_key,
        'city': 'Moss',
        'countryCode': 'NO',
        'size': 5
    }
    
    try:
        print("Searching for events in Moss...")
        response = requests.get(test_url, params=moss_params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            events = data.get('_embedded', {}).get('events', [])
            
            if events:
                print(f"✅ Found {len(events)} events in Moss:")
                for i, event in enumerate(events[:3], 1):
                    name = event.get('name', 'Unknown')
                    date = event.get('dates', {}).get('start', {}).get('localDate', 'Unknown date')
                    venue = 'Unknown venue'
                    if event.get('_embedded', {}).get('venues'):
                        venue = event['_embedded']['venues'][0].get('name', 'Unknown venue')
                    print(f"   {i}. {name} - {date} at {venue}")
            else:
                print("✅ API works, but no events found in Moss")
                print("   This is normal - Ticketmaster may not have many Moss events")
        else:
            print(f"❌ Moss search failed: HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ Moss search error: {e}")
    
    # Test 3: Rate limit info
    print(f"\n📊 RATE LIMIT INFO:")
    headers = response.headers if 'response' in locals() else {}
    
    rate_limit = headers.get('X-RateLimit-Limit', 'Unknown')
    rate_remaining = headers.get('X-RateLimit-Remaining', 'Unknown')
    rate_reset = headers.get('X-RateLimit-Reset', 'Unknown')
    
    print(f"Rate Limit: {rate_limit}")
    print(f"Remaining: {rate_remaining}")
    print(f"Reset Time: {rate_reset}")
    
    print(f"\n✅ TICKETMASTER API SETUP COMPLETE!")
    print(f"🚀 Ready to integrate with Moss Kulturkalender")
    
    return True

def generate_sample_requests():
    """Generate sample API requests for testing"""
    
    api_key = config.get('TICKETMASTER_API_KEY')
    base_url = config.get('TICKETMASTER_BASE_URL', 'https://app.ticketmaster.com/discovery/v2')
    
    samples = {
        "events_in_moss": f"{base_url}/events.json?city=Moss&countryCode=NO&apikey={api_key}",
        "music_events": f"{base_url}/events.json?city=Moss&countryCode=NO&classificationName=Music&apikey={api_key}",
        "theatre_events": f"{base_url}/events.json?city=Moss&countryCode=NO&classificationName=Arts%20%26%20Theatre&apikey={api_key}",
        "venues_in_moss": f"{base_url}/venues.json?city=Moss&countryCode=NO&apikey={api_key}",
        "all_norway_events": f"{base_url}/events.json?countryCode=NO&size=20&apikey={api_key}"
    }
    
    print(f"\n🔗 SAMPLE API REQUESTS:")
    print("Copy these URLs to test in your browser or Postman:")
    
    for name, url in samples.items():
        print(f"\n{name.replace('_', ' ').title()}:")
        print(f"   {url}")

if __name__ == "__main__":
    success = test_ticketmaster_api()
    
    if success:
        generate_sample_requests()
        
        print(f"\n🎯 NEXT STEPS:")
        print(f"1. API is working - you can now run: python3 ticketmaster_client.py")
        print(f"2. Set up automated scraping in cron job")
        print(f"3. Monitor your daily API usage (limit: 5000 requests)")
    else:
        print(f"\n🔧 TROUBLESHOOTING:")
        print(f"1. Verify your API key at https://developer.ticketmaster.com/")
        print(f"2. Check that your application is approved")
        print(f"3. Ensure you're using the Consumer Key (not Secret)")
        print(f"4. Update .env file with correct API key")
