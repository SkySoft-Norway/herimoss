#!/usr/bin/env python3
"""
Moss Avis Events Scraper
Extracts events from https://www.moss-avis.no/arrangementer
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from pathlib import Path
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
import re

from logging_utils import init_logging, log_info, log_error, log_warning
from models import Event
from uuid import uuid4


class MossAvisScraper:
    """Scraper for Moss Avis events"""
    
    def __init__(self):
        self.base_url = "https://www.moss-avis.no"
        self.events_url = f"{self.base_url}/arrangementer"
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'no,en;q=0.9'
            }
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def fetch_events_page(self) -> Optional[str]:
        """Fetch the events page HTML"""
        try:
            async with self.session.get(self.events_url) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    log_error("moss_avis_scraper", f"HTTP {response.status} for events page")
                    return None
                    
        except Exception as e:
            log_error("moss_avis_scraper", f"Failed to fetch events page: {e}")
            return None
    
    def parse_events(self, html: str) -> List[Dict[str, Any]]:
        """Parse events from HTML page"""
        events = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Look for event containers - try multiple selectors based on common patterns
            event_selectors = [
                '.event-item', '.event-card', '.event',
                '.post-item', '.article-item', '.item',
                '[class*="event"]', '[class*="arrangement"]',
                'article', '.card'
            ]
            
            event_elements = []
            for selector in event_selectors:
                elements = soup.select(selector)
                if elements and len(elements) > 2:  # Need reasonable number of elements
                    event_elements = elements
                    log_info(f"Using selector '{selector}' - found {len(elements)} elements")
                    break
            
            # Fallback: look for structured content in main content area
            if not event_elements:
                content_area = soup.find('main') or soup.find('div', class_=re.compile(r'content|main'))
                if content_area:
                    event_elements = content_area.find_all(['article', 'div'], class_=re.compile(r'item|post|card'))
            
            log_info(f"Found {len(event_elements)} potential event elements")
            
            for elem in event_elements:
                try:
                    event = self.extract_event_data(elem)
                    if event:
                        events.append(event)
                except Exception as e:
                    log_warning("moss_avis_parse", f"Failed to parse event element: {e}")
                    
        except Exception as e:
            log_error("moss_avis_parse", f"Failed to parse HTML: {e}")
            
        return events
    
    def extract_event_data(self, elem) -> Optional[Dict[str, Any]]:
        """Extract event data from an element"""
        try:
            # Extract title - try different header levels and link text
            title_elem = elem.find(['h1', 'h2', 'h3', 'h4', 'h5'])
            if not title_elem:
                title_elem = elem.find('a')
            
            if title_elem:
                title = title_elem.get_text(strip=True)
            else:
                # Last resort - get first significant text
                title = elem.get_text(strip=True).split('\n')[0]
            
            if not title or len(title) < 5:
                return None
                
            # Extract description - look for content paragraphs
            desc_elem = elem.find(['p', 'div'], class_=re.compile(r'desc|content|summary|excerpt'))
            if not desc_elem:
                # Try to find the first substantial paragraph
                paragraphs = elem.find_all('p')
                desc_elem = next((p for p in paragraphs if len(p.get_text(strip=True)) > 20), None)
            
            description = desc_elem.get_text(strip=True) if desc_elem else ""
            
            # Extract date - look for date patterns in text
            elem_text = elem.get_text()
            event_date = self.parse_norwegian_date(elem_text)
            
            # Extract link
            link_elem = elem.find('a', href=True)
            event_url = None
            if link_elem:
                href = link_elem['href']
                event_url = href if href.startswith('http') else f"{self.base_url}{href}"
            
            # Check if this seems to be an event (has date or event-related keywords)
            elem_text_lower = elem_text.lower()
            has_event_indicators = any(keyword in elem_text_lower for keyword in [
                'arrangement', 'konsert', 'forestilling', 'show', 'festival', 
                'utstilling', 'teater', 'kino', 'kultur', 'scene', 'moss'
            ])
            
            if not event_date and not has_event_indicators:
                return None
            
            # Create event data
            event_data = {
                'title': title,
                'description': description[:500] if description else "",
                'start': event_date.isoformat() if event_date else None,
                'venue': self.extract_venue_from_text(elem_text),
                'location': "Moss, Norway",
                'price': "Se arrangør for pris",
                'info_url': event_url,
                'ticket_url': event_url,
                'source': "Moss Avis",
                'category': "Arrangement",
                'raw_text': elem_text[:300]
            }
            
            return event_data
            
        except Exception as e:
            log_error("moss_avis_extract", f"Failed to extract event: {e}")
            return None
    
    def extract_venue_from_text(self, text: str) -> str:
        """Try to extract venue information from text"""
        text_lower = text.lower()
        
        # Common venues in Moss
        venues = [
            'moss kulturhus', 'kulturhuset', 'moss bibliotek', 'biblioteket',
            'galleri f15', 'f15', 'odeon', 'kino', 'moss scene',
            'moss kirke', 'kirken', 'moss museum', 'verket kultursenter'
        ]
        
        for venue in venues:
            if venue in text_lower:
                return venue.title()
        
        # Look for "på [venue]" or "i [venue]" patterns
        venue_pattern = r'(?:på|i)\s+([A-ZÆØÅ][a-zæøå\s]+(?:hus|senter|scene|sal|teater|kino|bibliotek|museum|galleri|kirke))'
        match = re.search(venue_pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip().title()
        
        return "Moss"
    
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
            
            # Pattern for Norwegian dates: "15. mars 2024" or "15 mars"
            date_pattern = r'(\d{1,2})\.?\s*([a-zA-ZæøåÆØÅ]+)\s*(\d{4})?'
            match = re.search(date_pattern, text.lower())
            
            if match:
                day = int(match.group(1))
                month_name = match.group(2).strip('.')
                year = int(match.group(3)) if match.group(3) else datetime.now().year
                
                month = months.get(month_name) or months.get(month_name[:3])
                if month:
                    # Handle year rollover - if month has passed, assume next year
                    current_date = datetime.now()
                    if month < current_date.month - 1:
                        year += 1
                    
                    # Look for time in the text
                    time_pattern = r'(\d{1,2}):(\d{2})'
                    time_match = re.search(time_pattern, text)
                    
                    if time_match:
                        hour = int(time_match.group(1))
                        minute = int(time_match.group(2))
                        return datetime(year, month, day, hour, minute)
                    else:
                        # Default time for events
                        return datetime(year, month, day, 19, 0)
                        
        except Exception as e:
            log_warning("date_parse", f"Failed to parse date from '{text[:100]}': {e}")
            
        return None
    
    async def scrape_all_events(self) -> List[Dict[str, Any]]:
        """Main scraping method"""
        html = await self.fetch_events_page()
        if html:
            return self.parse_events(html)
        
        return []


async def crawl_moss_avis_events() -> List[Event]:
    """Main function to crawl Moss Avis events"""
    events = []
    
    try:
        async with MossAvisScraper() as scraper:
            event_data_list = await scraper.scrape_all_events()
            
            # Convert to Event objects
            for event_data in event_data_list:
                try:
                    # Skip events without dates for now
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
                        source="Moss Avis",
                        source_type="html",
                        category=event_data.get('category', 'Arrangement'),
                        age_restriction="",
                        organizer="Moss Avis",
                        first_seen=datetime.now(),
                        last_seen=datetime.now()
                    )
                    events.append(event)
                    
                except Exception as e:
                    log_error("moss_avis_convert", f"Failed to convert event: {e}")
        
        log_info(f"📰 Moss Avis: Successfully scraped {len(events)} events")
        
    except Exception as e:
        log_error("moss_avis_scraper", f"Scraping failed: {e}")
    
    return events


if __name__ == "__main__":
    async def main():
        init_logging()
        events = await crawl_moss_avis_events()
        
        # Save to JSON for debugging
        output_file = Path("/var/www/vhosts/herimoss.no/pythoncrawler/moss_avis_events.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump([{
                'title': e.title,
                'start': e.start.isoformat() if e.start else None,
                'venue': e.venue,
                'price': e.price,
                'description': e.description
            } for e in events], f, ensure_ascii=False, indent=2)
        
        print(f"Scraped {len(events)} Moss Avis events")
        for event in events[:5]:
            print(f"  {event.start.strftime('%Y-%m-%d %H:%M') if event.start else 'No date'} | {event.title}")
    
    asyncio.run(main())