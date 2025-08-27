#!/usr/bin/env python3
"""
Galleri F15 Events Scraper
Extracts events from https://gallerif15.no/kalender/
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


class GalleriF15Scraper:
    """Scraper for Galleri F15 events"""
    
    def __init__(self):
        self.base_url = "https://gallerif15.no"
        self.events_url = f"{self.base_url}/kalender/"
        self.api_endpoints = [
            f"{self.base_url}/wp-json/wp/v2/events",
            f"{self.base_url}/api/events",
            f"{self.base_url}/wp-json/tribe/events/v1/events"  # Common WordPress events plugin
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
    
    async def fetch_with_playwright(self) -> Optional[str]:
        """Use Playwright to fetch the calendar page with full rendering"""
        try:
            log_info(f"Using Playwright to fetch: {self.events_url}")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    locale='no-NO'
                )
                page = await context.new_page()
                
                # Navigate to the calendar page with longer timeout
                await page.goto(self.events_url, wait_until='load', timeout=60000)
                
                # Wait for content to load - look for the event list structure
                try:
                    # Based on the analysis: .lists .container .list .item
                    await page.wait_for_selector('#c .lists .container .list .item', timeout=10000)
                    log_info("Calendar events loaded successfully")
                except:
                    log_info("Using generic wait for content loading")
                    await page.wait_for_timeout(3000)
                
                # Get the page content after full rendering
                html_content = await page.content()
                await browser.close()
                
                log_info(f"Successfully retrieved calendar page with Playwright ({len(html_content)} chars)")
                return html_content
                
        except Exception as e:
            log_error("galleri_playwright", f"Playwright fetch failed: {e}")
            return None
    
    async def try_api_endpoints(self) -> Optional[List[Dict]]:
        """Try to find API endpoints for events data"""
        for endpoint in self.api_endpoints:
            try:
                log_info(f"Trying API endpoint: {endpoint}")
                
                # Try different parameters
                params_list = [
                    {'per_page': 50, 'status': 'publish'},
                    {'limit': 50},
                    {'_embed': True},
                    {}  # No params
                ]
                
                for params in params_list:
                    async with self.session.get(endpoint, params=params) as response:
                        if response.status == 200:
                            try:
                                data = await response.json()
                                if isinstance(data, list) and len(data) > 0:
                                    log_info(f"Found {len(data)} events via API: {endpoint}")
                                    return data
                                elif isinstance(data, dict) and 'events' in data:
                                    events = data['events']
                                    log_info(f"Found {len(events)} events via API: {endpoint}")
                                    return events
                                    
                            except Exception as e:
                                log_warning("api_parse", f"API response not JSON: {e}")
                                continue
                        
            except Exception as e:
                log_warning("api_request", f"API request failed for {endpoint}: {e}")
                continue
        
        return None
    
    async def fetch_html_page(self) -> Optional[str]:
        """Fallback: scrape HTML page"""
        try:
            async with self.session.get(self.events_url) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    log_error("galleri_scraper", f"HTTP {response.status} for calendar page")
                    return None
                    
        except Exception as e:
            log_error("galleri_scraper", f"Failed to fetch HTML: {e}")
            return None
    
    def parse_api_events(self, events_data: List[Dict]) -> List[Dict[str, Any]]:
        """Parse events from API response"""
        parsed_events = []
        
        for event_data in events_data:
            try:
                # Extract WordPress/REST API fields
                title = event_data.get('title', {})
                if isinstance(title, dict):
                    title = title.get('rendered', '') or title.get('raw', '')
                else:
                    title = str(title)
                
                content = event_data.get('content', {})
                if isinstance(content, dict):
                    description = content.get('rendered', '') or content.get('raw', '')
                else:
                    description = str(content)
                
                # Clean HTML from description
                if description:
                    soup = BeautifulSoup(description, 'html.parser')
                    description = soup.get_text(strip=True)
                
                # Parse date - try different field names
                start_date = self.parse_api_date(
                    event_data.get('start_date') or 
                    event_data.get('date') or 
                    event_data.get('event_start_date') or
                    event_data.get('meta', {}).get('start_date')
                )
                
                # Event URL
                event_url = event_data.get('link') or event_data.get('url')
                
                # Venue/location
                venue = event_data.get('venue') or event_data.get('location', '')
                if not venue:
                    venue = "Galleri F15"
                
                parsed_event = {
                    'title': title,
                    'description': description[:500] if description else "",
                    'start': start_date.isoformat() if start_date else None,
                    'venue': venue,
                    'location': "Alby, Moss, Norway",
                    'price': "Se galleri for pris",
                    'info_url': event_url,
                    'ticket_url': event_url,
                    'source': "Galleri F15",
                    'category': "Kunst"
                }
                
                if parsed_event['start']:  # Only include events with valid dates
                    parsed_events.append(parsed_event)
                    
            except Exception as e:
                log_warning("api_parse", f"Failed to parse API event: {e}")
                continue
        
        return parsed_events
    
    def parse_html_events(self, html: str) -> List[Dict[str, Any]]:
        """Parse events from HTML using Galleri F15 specific structure"""
        events = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Galleri F15 specific selectors based on site analysis
            event_selectors = [
                '#c .lists .container .list .item',  # Main structure identified
                '.lists .container .list .item',     # Alternative without id
                '.list .item',                       # Shorter version
                '.item'                              # Generic item fallback
            ]
            
            event_elements = []
            for selector in event_selectors:
                elements = soup.select(selector)
                if elements:
                    event_elements = elements
                    log_info(f"Using Galleri F15 selector '{selector}' - found {len(elements)} elements")
                    break
            
            # Fallback: look for any structure that might contain events
            if not event_elements:
                log_info("Using fallback selectors for event detection")
                fallback_selectors = [
                    'article', '.post', '.entry',
                    '[class*="item"]', '[class*="card"]',
                    'div[class*="event"]'
                ]
                
                for selector in fallback_selectors:
                    elements = soup.select(selector)
                    if elements and len(elements) > 1:
                        # Filter elements that look like events
                        potential_events = []
                        for elem in elements:
                            elem_text = elem.get_text().lower()
                            # Check if it contains gallery-related keywords
                            if any(word in elem_text for word in ['utstilling', 'verksted', 'omvisning', 'galleri', 'kunst', 'exhibition']):
                                potential_events.append(elem)
                        
                        if potential_events:
                            event_elements = potential_events
                            log_info(f"Using fallback selector '{selector}' - found {len(potential_events)} relevant elements")
                            break
            
            log_info(f"Found {len(event_elements)} potential event elements")
            
            for i, elem in enumerate(event_elements):
                try:
                    event = self.extract_html_event_data(elem)
                    if event:
                        events.append(event)
                        log_info(f"Successfully extracted event {i+1}: {event['title'][:50]}...")
                except Exception as e:
                    log_warning("html_parse", f"Failed to parse HTML event {i+1}: {e}")
                    continue
        
        except Exception as e:
            log_error("html_parse", f"Failed to parse HTML: {e}")
        
        return events
    
    def extract_html_event_data(self, elem) -> Optional[Dict[str, Any]]:
        """Extract event data from HTML element - enhanced for Galleri F15"""
        try:
            elem_text = elem.get_text()
            elem_html = str(elem)
            
            # Skip if element is too small
            if len(elem_text.strip()) < 10:
                return None
            
            # Extract title with multiple approaches
            title = None
            
            # 1. Look for heading tags
            title_elem = elem.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            if title_elem:
                title = title_elem.get_text(strip=True)
            
            # 2. Look for title in link text
            if not title:
                link_elem = elem.find('a')
                if link_elem:
                    title = link_elem.get_text(strip=True)
            
            # 3. Look for title in specific classes
            if not title:
                for class_name in ['title', 'heading', 'name']:
                    title_elem = elem.find(class_=re.compile(class_name, re.I))
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        break
            
            # 4. Use first significant line as title
            if not title or len(title) < 5:
                lines = [line.strip() for line in elem_text.split('\n') if line.strip()]
                if lines:
                    title = lines[0]
            
            # 5. Special handling for Galleri F15 - look for event titles in description
            if title and len(title) < 15 and re.match(r'\d{2}\.\d{2}\.\d{2}', title):
                # Title is just a date, look for better title in text
                lines = [line.strip() for line in elem_text.split('\n') if line.strip()]
                
                # Extract better title from common patterns in the text
                for line in lines:
                    line_clean = line.strip()
                    
                    # Look for specific event types and artist names
                    if 'omvisning' in line_clean.lower():
                        if 'torsdagskveld' in line_clean.lower():
                            title = "Torsdagskveld på Alby: Utendørs kveldsomvisning"
                        elif 'søndagsomvisning' in line_clean.lower():
                            title = "Søndagsomvisning"
                        elif 'babyomvisning' in line_clean.lower():
                            title = "Babyomvisning"
                        break
                    elif 'drop-in verksted' in line_clean.lower():
                        title = "Drop-in verksted"
                        break
                    elif 'vernissasje' in line_clean.lower():
                        # Extract artist name from vernissage
                        if 'marina abramović' in line_clean.lower():
                            title = "Vernissasje: Marina Abramović"
                        else:
                            title = "Vernissasje"
                        break
                    elif 'momentum' in line_clean.lower():
                        title = "MOMENTUM 13"
                        break
                        
                # If still no good title found, try other patterns
                if title and len(title) < 15:
                    for line in lines[1:]:  # Skip the date line
                        line_clean = line.strip()
                        # Look for lines that seem like titles
                        if (5 < len(line_clean) < 100 and 
                            not line_clean.startswith('Vi ') and 
                            not line_clean.startswith('Hver ') and
                            not line_clean.startswith('Velkommen ') and
                            not any(word in line_clean.lower() for word in ['inviterer', 'åpner', 'arrangeres', 'regnes'])):
                            
                            # Clean up the line
                            potential_title = line_clean
                            if 'galleri f' in potential_title.lower():
                                potential_title = potential_title.replace('Galleri F 15', '').strip()
                            
                            if potential_title and len(potential_title) > 5:
                                title = potential_title
                                break
                    
            if not title or len(title) < 5:
                return None
            
            # Extract description
            description = ""
            
            # Look for description in paragraphs or specific classes
            desc_selectors = ['p', '.description', '.excerpt', '.summary', '.content']
            for selector in desc_selectors:
                desc_elem = elem.select_one(selector)
                if desc_elem:
                    desc_text = desc_elem.get_text(strip=True)
                    if desc_text and len(desc_text) > 20:
                        description = desc_text
                        break
            
            # If no specific description, use text content excluding title
            if not description:
                description = elem_text.replace(title, '', 1).strip()
            
            # Extract link
            event_url = None
            link_elem = elem.find('a', href=True)
            if link_elem:
                href = link_elem['href']
                event_url = href if href.startswith('http') else f"{self.base_url}{href}"
            
            # Enhanced date parsing for multiple formats
            event_date = self.parse_norwegian_date(elem_text)
            
            # If no date found, try parsing from different formats
            if not event_date:
                # Look for DD.MM.YYYY or DD/MM/YYYY patterns
                date_patterns = [
                    r'(\d{1,2})[./](\d{1,2})[./](\d{4})',
                    r'(\d{1,2})[./](\d{1,2})[./](\d{2})',
                ]
                
                for pattern in date_patterns:
                    match = re.search(pattern, elem_text)
                    if match:
                        try:
                            day, month = int(match.group(1)), int(match.group(2))
                            year = int(match.group(3))
                            if year < 100:  # 2-digit year
                                year = 2000 + year
                            event_date = datetime(year, month, day, 18, 0)  # Default to 6 PM
                            break
                        except ValueError:
                            continue
            
            # Check if this looks like a relevant gallery event
            elem_text_lower = elem_text.lower()
            gallery_keywords = [
                'utstilling', 'exhibition', 'kunst', 'art', 'galleri', 'vernissage',
                'åpning', 'opening', 'kunstner', 'artist', 'verksted', 'workshop',
                'omvisning', 'tour', 'maleri', 'painting', 'skulptur', 'sculpture',
                'installasjon', 'installation', 'foto', 'photo'
            ]
            
            has_gallery_indicators = any(keyword in elem_text_lower for keyword in gallery_keywords)
            
            # Only include if it has a date OR strong gallery indicators
            if not event_date and not has_gallery_indicators:
                return None
            
            # Determine event category based on content
            category = "Kunst"
            if 'verksted' in elem_text_lower or 'workshop' in elem_text_lower:
                category = "Verksted"
            elif 'omvisning' in elem_text_lower or 'tour' in elem_text_lower:
                category = "Omvisning"
            elif 'utstilling' in elem_text_lower or 'exhibition' in elem_text_lower:
                category = "Utstilling"
            
            event_data = {
                'title': title.strip(),
                'description': description[:500] if description else "",
                'start': event_date.isoformat() if event_date else None,
                'venue': "Galleri F15",
                'location': "Alby, Moss, Norway",
                'price': "Se galleri for pris",
                'info_url': event_url,
                'ticket_url': event_url,
                'source': "Galleri F15",
                'category': category,
                'raw_text': elem_text[:300]
            }
            
            return event_data
            
        except Exception as e:
            log_error("html_extract", f"Failed to extract HTML event: {e}")
            return None
    
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
                    return datetime.fromisoformat(f"{date_str}T18:00:00")
            
            # Unix timestamp
            elif isinstance(date_str, (int, float)):
                return datetime.fromtimestamp(date_str)
                
        except Exception as e:
            log_warning("date_parse", f"Failed to parse API date '{date_str}': {e}")
        
        return None
    
    def parse_norwegian_date(self, text: str) -> Optional[datetime]:
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
            date_pattern = r'(\d{1,2})\.?\s*([a-zA-ZæøåÆØÅ]+)\s*(\d{4})?'
            match = re.search(date_pattern, text.lower())
            
            if match:
                day = int(match.group(1))
                month_name = match.group(2).strip('.')
                year = int(match.group(3)) if match.group(3) else datetime.now().year
                
                month = months.get(month_name) or months.get(month_name[:3])
                if month:
                    # Handle year rollover
                    if month < datetime.now().month - 1:
                        year += 1
                    
                    # Default time for gallery events (often afternoon/evening)
                    return datetime(year, month, day, 18, 0)
                    
        except Exception as e:
            log_warning("date_parse", f"Failed to parse date from text: {e}")
            
        return None
    
    async def scrape_all_events(self) -> List[Dict[str, Any]]:
        """Main scraping method - now uses Playwright first for full rendering"""
        # Try Playwright first for full JavaScript rendering
        log_info("Using Playwright for complete page rendering")
        playwright_html = await self.fetch_with_playwright()
        if playwright_html:
            events = self.parse_html_events(playwright_html)
            if events:
                log_info(f"Successfully found {len(events)} events with Playwright")
                return events
            else:
                log_info("Playwright HTML parsing found no events, trying other methods")
        
        # Try API as backup
        log_info("Playwright didn't find events, trying API endpoints")
        api_events = await self.try_api_endpoints()
        if api_events:
            return self.parse_api_events(api_events)
        
        # Final fallback to basic HTML scraping
        log_info("API not available, falling back to basic HTML scraping")
        html = await self.fetch_html_page()
        if html:
            return self.parse_html_events(html)
        
        return []


async def crawl_galleri_f15_events() -> List[Event]:
    """Main function to crawl Galleri F15 events"""
    events = []
    
    try:
        async with GalleriF15Scraper() as scraper:
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
                        venue=event_data.get('venue', 'Galleri F15'),
                        location=event_data.get('location', 'Alby, Moss, Norway'),
                        price=event_data.get('price', ''),
                        ticket_url=event_data.get('ticket_url', ''),
                        info_url=event_data.get('info_url', ''),
                        source="Galleri F15",
                        source_type="html",
                        category=event_data.get('category', 'Kunst'),
                        age_restriction="",
                        organizer="Galleri F15",
                        first_seen=datetime.now(),
                        last_seen=datetime.now()
                    )
                    events.append(event)
                    
                except Exception as e:
                    log_error("galleri_convert", f"Failed to convert event: {e}")
        
        log_info(f"🎨 Galleri F15: Successfully scraped {len(events)} events")
        
    except Exception as e:
        log_error("galleri_scraper", f"Scraping failed: {e}")
    
    return events


if __name__ == "__main__":
    async def main():
        init_logging()
        events = await crawl_galleri_f15_events()
        
        # Save to JSON for debugging
        output_file = Path("/var/www/vhosts/herimoss.no/pythoncrawler/galleri_f15_events.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump([{
                'title': e.title,
                'start': e.start.isoformat() if e.start else None,
                'venue': e.venue,
                'price': e.price,
                'description': e.description
            } for e in events], f, ensure_ascii=False, indent=2)
        
        print(f"Scraped {len(events)} Galleri F15 events")
        for event in events[:5]:
            print(f"  {event.start.strftime('%Y-%m-%d %H:%M') if event.start else 'No date'} | {event.title}")
    
    asyncio.run(main())