#!/usr/bin/env python3
"""
Visit Østfold Events Scraper
Extracts events from https://www.visitoestfold.com/moss/hva-skjer/
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from pathlib import Path
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
import re
from playwright.async_api import async_playwright

from logging_utils import init_logging, log_info, log_error, log_warning
from models import Event
from uuid import uuid4


class VisitOstfoldScraper:
    """Scraper for Visit Østfold events"""
    
    def __init__(self):
        self.base_url = "https://www.visitoestfold.com"
        self.events_url = f"{self.base_url}/moss/hva-skjer/?bounds=false&view=list&sort=date&filter_regions%5B0%5D=506503"
        self.api_endpoints = [
            f"{self.base_url}/api/events",
            f"{self.base_url}/api/v1/events", 
            f"{self.base_url}/ajax/events"
        ]
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json, text/html, */*',
                'Accept-Language': 'no,en;q=0.9'
            }
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def try_rss_feed(self) -> Optional[List[Dict]]:
        """Try to fetch events from RSS feed"""
        rss_url = "https://www.visitoestfold.com/event/rss/"
        
        try:
            log_info(f"Trying RSS feed: {rss_url}")
            
            async with self.session.get(rss_url) as response:
                if response.status == 200:
                    rss_content = await response.text()
                    events = self.parse_rss_feed(rss_content)
                    if events:
                        log_info(f"Found {len(events)} events via RSS feed")
                        return events
                    else:
                        log_warning("rss_parse", "No events found in RSS feed")
                else:
                    log_warning("rss_fetch", f"HTTP {response.status} for RSS feed")
                    
        except Exception as e:
            log_warning("rss_fetch", f"RSS feed request failed: {e}")
        
        return None
    
    def parse_rss_feed(self, rss_content: str) -> List[Dict]:
        """Parse RSS feed content to extract events"""
        import xml.etree.ElementTree as ET
        from html import unescape
        
        events = []
        
        try:
            # Parse the RSS XML
            root = ET.fromstring(rss_content)
            
            # Find all item elements
            for item in root.findall('.//item'):
                try:
                    # Extract basic info
                    title = item.find('title')
                    title = unescape(title.text) if title is not None else ""
                    
                    description = item.find('description')
                    description = unescape(description.text) if description is not None else ""
                    
                    link = item.find('link')
                    link = link.text if link is not None else ""
                    
                    pub_date = item.find('pubDate')
                    pub_date = pub_date.text if pub_date is not None else ""
                    
                    # Check if event is related to Moss
                    content_lower = f"{title} {description}".lower()
                    if 'moss' not in content_lower:
                        continue
                    
                    # Parse publication date as event date (RSS items usually have event dates in pubDate)
                    event_date = self.parse_rss_date(pub_date)
                    
                    # Try to extract additional info from description
                    venue = self.extract_venue_from_description(description)
                    
                    event_data = {
                        'title': title,
                        'description': description[:500] if description else "",
                        'start': event_date.isoformat() if event_date else None,
                        'venue': venue or "Moss",
                        'location': "Moss, Norway",
                        'price': "Se arrangør for pris",
                        'info_url': link,
                        'ticket_url': link,
                        'source': "Visit Østfold",
                        'category': "Arrangement",
                        'raw_content': content_lower[:200]
                    }
                    
                    events.append(event_data)
                    
                except Exception as e:
                    log_warning("rss_item_parse", f"Failed to parse RSS item: {e}")
                    continue
                    
        except ET.ParseError as e:
            log_error("rss_parse", f"Failed to parse RSS XML: {e}")
        except Exception as e:
            log_error("rss_parse", f"RSS parsing error: {e}")
            
        return events
    
    def parse_rss_date(self, date_str: str) -> Optional[datetime]:
        """Parse RSS date format (RFC 2822)"""
        if not date_str:
            return None
            
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except Exception as e:
            log_warning("rss_date_parse", f"Failed to parse RSS date '{date_str}': {e}")
            return None
    
    def extract_venue_from_description(self, description: str) -> Optional[str]:
        """Extract venue information from event description"""
        if not description:
            return None
            
        text_lower = description.lower()
        
        # Look for common venue patterns in Moss
        venues = [
            'moss kulturhus', 'kulturhuset', 'moss bibliotek', 'biblioteket',
            'galleri f15', 'f15', 'verket scene', 'verket', 'moss scene',
            'moss kirke', 'kirken', 'moss museum', 'parkteatret'
        ]
        
        for venue in venues:
            if venue in text_lower:
                return venue.title()
        
        # Look for address patterns or "ved/på/i [location]"
        import re
        venue_pattern = r'(?:ved|på|i)\s+([A-ZÆØÅ][a-zæøå\s]+(?:vei|gate|plass|sentrum|hus|senter|scene))'
        match = re.search(venue_pattern, description, re.IGNORECASE)
        if match:
            return match.group(1).strip().title()
        
        return None
    
    async def scrape_with_playwright(self) -> Optional[str]:
        """Use Playwright to scrape the page with JavaScript rendering"""
        try:
            log_info(f"Using Playwright to scrape: {self.events_url}")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    locale='no-NO'
                )
                page = await context.new_page()
                
                # Navigate to the events page with filters
                await page.goto(self.events_url, wait_until='networkidle', timeout=30000)
                
                # Wait for events to load - look for common event container patterns
                selectors_to_wait_for = [
                    '.event-item',
                    '.event-card', 
                    '.event',
                    '[class*="event"]',
                    '.card',
                    '.item',
                    '.listing-item'
                ]
                
                # Try to wait for events to appear
                for selector in selectors_to_wait_for:
                    try:
                        await page.wait_for_selector(selector, timeout=10000)
                        log_info(f"Found events with selector: {selector}")
                        break
                    except:
                        continue
                else:
                    # If no specific selectors work, just wait a bit for general content
                    log_info("No specific event selectors found, waiting for general content")
                    await page.wait_for_timeout(5000)
                
                # Get the page content after JavaScript execution
                html_content = await page.content()
                await browser.close()
                
                log_info(f"Successfully retrieved page content with Playwright ({len(html_content)} chars)")
                return html_content
                
        except Exception as e:
            log_error("playwright_scrape", f"Playwright scraping failed: {e}")
            return None
    
    async def try_api_endpoints(self) -> Optional[List[Dict]]:
        """Fallback: Try to find API endpoints for events data"""
        for endpoint in self.api_endpoints:
            try:
                log_info(f"Trying API endpoint: {endpoint}")
                
                # Try different parameters for Moss events
                params_list = [
                    {'location': 'moss', 'limit': 50},
                    {'city': 'moss', 'limit': 50},
                    {'region': 'moss', 'limit': 50},
                    {'area': 'moss'},
                    {}  # No params
                ]
                
                for params in params_list:
                    async with self.session.get(endpoint, params=params) as response:
                        if response.status == 200:
                            try:
                                data = await response.json()
                                if isinstance(data, dict) and 'events' in data:
                                    events = data['events']
                                elif isinstance(data, list) and len(data) > 0:
                                    events = data
                                else:
                                    continue
                                    
                                log_info(f"Found {len(events)} events via API: {endpoint}")
                                return events
                                
                            except Exception as e:
                                log_warning("api_parse", f"API response not JSON: {e}")
                                continue
                        
            except Exception as e:
                log_warning("api_request", f"API request failed for {endpoint}: {e}")
                continue
        
        return None
    
    async def scrape_html_page(self) -> Optional[str]:
        """Fallback: scrape HTML page"""
        try:
            async with self.session.get(self.events_url) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    log_error("html_scraper", f"HTTP {response.status} for main page")
                    return None
                    
        except Exception as e:
            log_error("html_scraper", f"Failed to fetch HTML: {e}")
            return None
    
    def parse_api_events(self, events_data: List[Dict]) -> List[Dict[str, Any]]:
        """Parse events from API response"""
        parsed_events = []
        
        for event_data in events_data:
            try:
                # Extract common fields
                title = event_data.get('title') or event_data.get('name', '')
                description = event_data.get('description', '') or event_data.get('summary', '')
                
                # Parse date
                start_date = self.parse_api_date(
                    event_data.get('start_date') or 
                    event_data.get('date') or 
                    event_data.get('startDate')
                )
                
                # Location info
                venue = event_data.get('venue', '') or event_data.get('location', '')
                if 'moss' not in venue.lower() and 'moss' not in title.lower():
                    # Skip if not clearly in Moss
                    continue
                
                # Price
                price = event_data.get('price')
                if price and str(price) != '0':
                    price_str = f"kr {price}"
                else:
                    price_str = "Gratis"
                
                # URL
                event_url = event_data.get('url') or event_data.get('link')
                if event_url and not event_url.startswith('http'):
                    event_url = f"{self.base_url}{event_url}"
                
                parsed_event = {
                    'title': title,
                    'description': description[:500] if description else "",
                    'start': start_date.isoformat() if start_date else None,
                    'venue': venue or "Moss",
                    'location': "Moss, Norway",
                    'price': price_str,
                    'info_url': event_url,
                    'ticket_url': event_url,
                    'source': "Visit Østfold",
                    'category': event_data.get('category', 'Arrangement')
                }
                
                if parsed_event['start']:  # Only include events with valid dates
                    parsed_events.append(parsed_event)
                    
            except Exception as e:
                log_warning("api_parse", f"Failed to parse event: {e}")
                continue
        
        return parsed_events
    
    def parse_html_events(self, html: str) -> List[Dict[str, Any]]:
        """Parse events from HTML using improved selectors for Visit Østfold"""
        events = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Visit Østfold specific selectors
            event_selectors = [
                '.event-item', '.event-card', '.event',
                '.listing-item', '.listing-card', '.listing',
                '.activity-item', '.activity-card', '.activity',
                '.card', '.item',
                '[class*="event"]', '[class*="listing"]', '[class*="activity"]',
                'article', '.post', '.entry'
            ]
            
            event_elements = []
            for selector in event_selectors:
                elements = soup.select(selector)
                if elements and len(elements) > 0:
                    event_elements = elements
                    log_info(f"Using selector '{selector}' - found {len(elements)} elements")
                    break
            
            # If no specific selectors work, try generic content areas
            if not event_elements:
                generic_selectors = ['main', '.main-content', '.content', '#content']
                for selector in generic_selectors:
                    container = soup.select_one(selector)
                    if container:
                        # Look for any elements that might contain event info
                        event_elements = container.find_all(['div', 'article', 'section'], 
                                                          class_=re.compile(r'.+'))
                        if event_elements:
                            log_info(f"Found {len(event_elements)} elements in {selector}")
                            break
            
            log_info(f"Found {len(event_elements)} potential event elements")
            
            for elem in event_elements:
                try:
                    elem_text = elem.get_text().lower()
                    elem_html = str(elem)
                    
                    # Skip if element is too small or doesn't contain meaningful content
                    if len(elem_text.strip()) < 20:
                        continue
                    
                    # Look for event-like patterns (dates, venues, etc.)
                    has_date_pattern = bool(re.search(r'\b\d{1,2}\.?\s*(januar|februar|mars|april|mai|juni|juli|august|september|oktober|november|desember|jan|feb|mar|apr|mai|jun|jul|aug|sep|okt|nov|des)\b', elem_text))
                    has_moss_reference = 'moss' in elem_text
                    has_link = elem.find('a', href=True) is not None
                    
                    # Skip if not event-like
                    if not (has_date_pattern or has_moss_reference or has_link):
                        continue
                    
                    # Extract title
                    title_elem = elem.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                    if not title_elem:
                        # Try finding any bold or strong text
                        title_elem = elem.find(['strong', 'b']) 
                    
                    title = title_elem.get_text(strip=True) if title_elem else ""
                    
                    # If still no title, use first meaningful text
                    if not title and len(elem_text.strip()) > 0:
                        lines = [line.strip() for line in elem_text.split('\n') if line.strip()]
                        if lines:
                            title = lines[0][:100]  # Take first line as title
                    
                    if not title or len(title) < 5:
                        continue
                    
                    # Extract description
                    desc_elem = elem.find(['p', 'div'], class_=re.compile(r'desc|content|summary|text'))
                    if not desc_elem:
                        # Get all text except title
                        description = elem_text.replace(title.lower(), '', 1).strip()
                    else:
                        description = desc_elem.get_text(strip=True)
                    
                    # Extract link
                    link_elem = elem.find('a', href=True)
                    event_url = None
                    if link_elem:
                        href = link_elem['href']
                        event_url = href if href.startswith('http') else f"{self.base_url}{href}"
                    
                    # Extract venue from text
                    venue = self.extract_venue_from_description(elem_text)
                    
                    # Parse date from text
                    event_date = self.parse_norwegian_date_text(elem_text)
                    
                    # Create event data
                    event_data = {
                        'title': title.strip(),
                        'description': description[:500] if description else "",
                        'start': event_date.isoformat() if event_date else None,
                        'venue': venue or "Moss",
                        'location': "Moss, Norway",
                        'price': "Se arrangør for pris",
                        'info_url': event_url,
                        'ticket_url': event_url,
                        'source': "Visit Østfold",
                        'category': "Arrangement",
                        'raw_content': elem_text[:200]
                    }
                    
                    events.append(event_data)
                    log_info(f"Found event: {title[:50]}...")
                        
                except Exception as e:
                    log_warning("html_parse", f"Failed to parse HTML event: {e}")
                    continue
        
        except Exception as e:
            log_error("html_parse", f"Failed to parse HTML: {e}")
        
        return events
    
    def parse_api_date(self, date_str: Any) -> Optional[datetime]:
        """Parse date from API response"""
        if not date_str:
            return None
            
        try:
            # Handle different date formats
            if isinstance(date_str, str):
                # ISO format
                if 'T' in date_str:
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                # Date only
                elif '-' in date_str:
                    return datetime.fromisoformat(f"{date_str}T19:00:00")
            
            # Unix timestamp
            elif isinstance(date_str, (int, float)):
                return datetime.fromtimestamp(date_str)
                
        except Exception as e:
            log_warning("date_parse", f"Failed to parse API date '{date_str}': {e}")
        
        return None
    
    def parse_norwegian_date_text(self, text: str) -> Optional[datetime]:
        """Parse Norwegian date from text"""
        try:
            months = {
                'januar': 1, 'jan': 1,
                'februar': 2, 'feb': 2, 
                'mars': 3, 'mar': 3,
                'april': 4, 'apr': 4,
                'mai': 5,
                'juni': 6, 'jun': 6,
                'juli': 7, 'jul': 7,
                'august': 8, 'aug': 8,
                'september': 9, 'sep': 9, 'sept': 9,
                'oktober': 10, 'okt': 10,
                'november': 11, 'nov': 11,
                'desember': 12, 'des': 12
            }
            
            # Pattern for Norwegian dates
            pattern = r'(\d{1,2})\.?\s*([a-zA-ZæøåÆØÅ]+)\s*(\d{4})?'
            match = re.search(pattern, text.lower())
            
            if match:
                day = int(match.group(1))
                month_name = match.group(2).strip('.')
                year = int(match.group(3)) if match.group(3) else datetime.now().year
                
                month = months.get(month_name)
                if month:
                    # Handle year rollover
                    if month < datetime.now().month - 1:
                        year += 1
                    
                    return datetime(year, month, day, 19, 0)
                    
        except Exception as e:
            log_warning("date_parse", f"Failed to parse date from text: {e}")
            
        return None
    
    async def scrape_all_events(self) -> List[Dict[str, Any]]:
        """Main scraping method - now uses Playwright first for JavaScript rendering"""
        # Try Playwright first for JavaScript-rendered content
        log_info("Using Playwright for JavaScript rendering")
        playwright_html = await self.scrape_with_playwright()
        if playwright_html:
            events = self.parse_html_events(playwright_html)
            if events:
                log_info(f"Successfully found {len(events)} events with Playwright")
                return events
            else:
                log_info("Playwright HTML parsing found no events, trying other methods")
        
        # Try RSS feed as backup
        rss_events = await self.try_rss_feed()
        if rss_events:
            log_info("Successfully fetched events from RSS feed")
            return rss_events
        
        # Try API endpoints as fallback
        log_info("RSS feed not available, trying API endpoints")
        api_events = await self.try_api_endpoints()
        if api_events:
            return self.parse_api_events(api_events)
        
        # Final fallback to basic HTML scraping
        log_info("API not available, falling back to basic HTML scraping")
        html = await self.scrape_html_page()
        if html:
            return self.parse_html_events(html)
        
        return []


async def crawl_visitostfold_events() -> List[Event]:
    """Main function to crawl Visit Østfold events"""
    events = []
    
    try:
        async with VisitOstfoldScraper() as scraper:
            event_data_list = await scraper.scrape_all_events()
            
            # Convert to Event objects
            for event_data in event_data_list:
                try:
                    if not event_data.get('start'):
                        continue
                        
                    start_time = datetime.fromisoformat(event_data['start'])
                    
                    event = Event(
                        id=str(uuid4()),
                        title=event_data.get('title', 'Unknown Event'),
                        description=event_data.get('description', ''),
                        start=start_time,
                        end=None,
                        venue=event_data.get('venue', 'Moss'),
                        location=event_data.get('location', 'Moss, Norway'),
                        price=event_data.get('price', ''),
                        ticket_url=event_data.get('ticket_url', ''),
                        info_url=event_data.get('info_url', ''),
                        source="Visit Østfold",
                        source_type="html",
                        category=event_data.get('category', 'Arrangement'),
                        age_restriction="",
                        organizer="Visit Østfold",
                        first_seen=datetime.now(),
                        last_seen=datetime.now()
                    )
                    events.append(event)
                    
                except Exception as e:
                    log_error("visitostfold_convert", f"Failed to convert event: {e}")
        
        log_info(f"🌐 Visit Østfold: Successfully scraped {len(events)} events")
        
    except Exception as e:
        log_error("visitostfold_scraper", f"Scraping failed: {e}")
    
    return events


if __name__ == "__main__":
    async def main():
        init_logging()
        events = await crawl_visitostfold_events()
        
        # Save to JSON for debugging
        output_file = Path("/var/www/vhosts/herimoss.no/pythoncrawler/visitostfold_events.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump([{
                'title': e.title,
                'start': e.start.isoformat() if e.start else None,
                'venue': e.venue,
                'price': e.price,
                'description': e.description
            } for e in events], f, ensure_ascii=False, indent=2)
        
        print(f"Scraped {len(events)} Visit Østfold events")
        for event in events[:5]:
            print(f"  {event.start.strftime('%Y-%m-%d %H:%M') if event.start else 'No date'} | {event.title}")
    
    asyncio.run(main())