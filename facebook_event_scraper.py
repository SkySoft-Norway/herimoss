#!/usr/bin/env python3
"""
Facebook Event Scraper for Moss
Searches for local events in Moss kommune through public Facebook pages
"""

import requests
import sqlite3
import json
import re
from datetime import datetime, timedelta
import logging
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class FacebookEventScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'no,en-US;q=0.7,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })
        
        # Known Facebook pages for Moss cultural venues
        self.moss_facebook_pages = [
            'mosskulturhus',           # Moss Kulturhus
            'verketscene',             # Verket Scene  
            'mosskunstforening',       # Moss Kunstforening
            'gallerimoss',             # Galleri Moss
            'mosslibrary',             # Moss bibliotek
            'visitsorlandet',          # Visit Sørlandet (includes Moss)
            'mosskommune',             # Moss kommune
        ]
        
    def search_facebook_events(self, query="moss event kultur"):
        """
        Search for Facebook events related to Moss
        Note: Facebook heavily restricts scraping, so this is limited
        """
        events = []
        
        # Alternative: Search public Facebook pages by URL pattern
        for page in self.moss_facebook_pages:
            try:
                events.extend(self._scrape_page_events(page))
            except Exception as e:
                logging.warning(f"Could not scrape {page}: {e}")
                continue
                
        return events
    
    def _scrape_page_events(self, page_name):
        """
        Attempt to find events from a Facebook page
        Limited due to Facebook's anti-scraping measures
        """
        events = []
        
        try:
            # Try to access events section of Facebook page
            url = f"https://www.facebook.com/{page_name}/events"
            
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                logging.warning(f"Could not access {url}: {response.status_code}")
                return events
                
            # Facebook heavily uses JavaScript, so basic scraping is limited
            # We can only get basic information from meta tags and static content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for event information in meta tags
            title_tag = soup.find('meta', property='og:title')
            description_tag = soup.find('meta', property='og:description')
            
            if title_tag and 'event' in title_tag.get('content', '').lower():
                event = {
                    'title': title_tag.get('content', ''),
                    'description': description_tag.get('content', '') if description_tag else '',
                    'venue': page_name.replace('moss', 'Moss ').title(),
                    'source': f"https://www.facebook.com/{page_name}",
                    'start_time': None,  # Difficult to extract without API
                    'category': 'facebook-event'
                }
                events.append(event)
                
        except Exception as e:
            logging.error(f"Error scraping {page_name}: {e}")
            
        return events
    
    def get_alternative_facebook_events(self):
        """
        Alternative method: Look for Facebook events through other sources
        """
        events = []
        
        # Check local websites that might embed Facebook events
        local_sites = [
            'https://www.moss.kommune.no',
            'https://www.visitostfold.com',
            'https://www.mossavis.no',
        ]
        
        for site in local_sites:
            try:
                events.extend(self._check_site_for_facebook_events(site))
            except Exception as e:
                logging.warning(f"Could not check {site}: {e}")
                
        return events
    
    def _check_site_for_facebook_events(self, url):
        """
        Check if a website embeds or links to Facebook events
        """
        events = []
        
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return events
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for Facebook event links
            fb_links = soup.find_all('a', href=re.compile(r'facebook\.com.*event'))
            
            for link in fb_links:
                href = link.get('href')
                text = link.get_text(strip=True)
                
                if text and len(text) > 10:  # Reasonable event title length
                    event = {
                        'title': text,
                        'description': f'Facebook event linked from {urlparse(url).netloc}',
                        'venue': 'Moss området',
                        'source': href,
                        'start_time': None,
                        'category': 'facebook-linked'
                    }
                    events.append(event)
                    
        except Exception as e:
            logging.error(f"Error checking {url}: {e}")
            
        return events
    
    def save_events_to_db(self, events):
        """Save Facebook events to database"""
        if not events:
            logging.info("No Facebook events found to save")
            return
            
        conn = sqlite3.connect('/var/www/vhosts/herimoss.no/pythoncrawler/events.db')
        cursor = conn.cursor()
        
        # Ensure table exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS facebook_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                venue TEXT,
                description TEXT,
                source TEXT,
                start_time TEXT,
                category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        saved_count = 0
        for event in events:
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO facebook_events 
                    (title, venue, description, source, start_time, category)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    event['title'],
                    event['venue'],
                    event['description'],
                    event['source'],
                    event['start_time'],
                    event['category']
                ))
                saved_count += 1
            except Exception as e:
                logging.error(f"Error saving event {event['title']}: {e}")
                
        conn.commit()
        conn.close()
        
        logging.info(f"💾 Saved {saved_count} Facebook events to database")
        return saved_count

def main():
    """Main function to run Facebook event scraping"""
    logging.info("🔍 Starting Facebook event search for Moss...")
    
    scraper = FacebookEventScraper()
    
    # Method 1: Direct Facebook page scraping (limited)
    logging.info("📘 Searching Facebook pages...")
    fb_events = scraper.search_facebook_events()
    
    # Method 2: Alternative sources
    logging.info("🔗 Checking alternative sources for Facebook events...")
    alt_events = scraper.get_alternative_facebook_events()
    
    all_events = fb_events + alt_events
    
    if all_events:
        logging.info(f"📊 Found {len(all_events)} potential Facebook events")
        
        # Print found events
        for event in all_events:
            print(f"📅 {event['title']}")
            print(f"   📍 {event['venue']}")
            print(f"   🔗 {event['source']}")
            print()
        
        # Save to database
        scraper.save_events_to_db(all_events)
    else:
        logging.info("❌ No Facebook events found")
        print("\n🔍 FACEBOOK SCRAPING LIMITATIONS:")
        print("• Facebook heavily restricts automated access")
        print("• Most content requires JavaScript/login")
        print("• API access requires app approval")
        print("\n💡 ALTERNATIVES FOR FACEBOOK EVENTS:")
        print("• Manual collection from Facebook pages")
        print("• Partnership with venues for event feeds")
        print("• User-submitted event form on website")
        print("• Integration with Ticketmaster/Eventbrite APIs")

if __name__ == "__main__":
    main()
