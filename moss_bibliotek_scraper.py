#!/usr/bin/env python3
"""
Moss Bibliotekene Events Scraper
Extracts events from https://www.mossebibliotekene.no/bibliotek/moss/arrangementer
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


class MossBibliotekScraper:
    """Scraper for Moss Bibliotekene events"""
    
    def __init__(self):
        self.base_url = "https://www.mossebibliotekene.no"
        self.events_url = f"{self.base_url}/arrangementer"
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def fetch_page_with_playwright(self, page_num: int = 1) -> Optional[str]:
        """Fetch page using Playwright for JavaScript rendering"""
        try:
            url = f"{self.events_url}?page={page_num}" if page_num > 1 else self.events_url
            log_info(f"Using Playwright to fetch: {url}")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    locale='no-NO'
                )
                page = await context.new_page()
                
                # Navigate to the events page
                await page.goto(url, wait_until='networkidle', timeout=30000)
                
                # Wait for events to load
                try:
                    await page.wait_for_selector('.views-row, .event-item, .node-event', timeout=10000)
                    log_info("Events loaded successfully")
                except:
                    log_info("No specific event selectors found, proceeding with content")
                    await page.wait_for_timeout(3000)
                
                # Get the page content
                html_content = await page.content()
                await browser.close()
                
                log_info(f"Successfully retrieved page content with Playwright ({len(html_content)} chars)")
                return html_content
                
        except Exception as e:
            log_error("bibliotek_playwright", f"Playwright fetch failed for page {page_num}: {e}")
            return None
    
    async def fetch_page(self, page_num: int = 1) -> Optional[str]:
        """Fetch events page HTML"""
        try:
            url = f"{self.events_url}?page={page_num}" if page_num > 1 else self.events_url
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    log_error("bibliotek_scraper", f"HTTP {response.status} for page {page_num}")
                    return None
                    
        except Exception as e:
            log_error("bibliotek_scraper", f"Failed to fetch page {page_num}: {e}")
            return None
    
    def parse_events(self, html: str) -> List[Dict[str, Any]]:
        """Parse events from HTML page - improved for Drupal/Views structure"""
        events = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Drupal Views typically use .views-row for each item
            event_selectors = [
                '.views-row',           # Drupal Views rows
                '.node-event',          # Event node
                '.event-item',          # Generic event item
                '.ding-event',          # Ding event (library system)
                '.event-list-item',     # Event list item
                'article[class*="event"]', # Article with event class
                '.item-list .item',     # Generic item list
                '.field-content .item'  # Field content items
            ]
            
            event_cards = []
            for selector in event_selectors:
                cards = soup.select(selector)
                if cards and len(cards) > 0:
                    event_cards = cards
                    log_info(f"Using selector '{selector}' - found {len(cards)} elements")
                    break
            
            # If no specific selectors work, try broader search
            if not event_cards:
                # Look for any div/article that contains event-like content
                potential_cards = soup.find_all(['div', 'article'])
                for card in potential_cards:
                    card_text = card.get_text().lower()
                    # Check if it looks like an event (has date patterns)
                    if re.search(r'\b\d{1,2}\.?\s*(januar|februar|mars|april|mai|juni|juli|august|september|oktober|november|desember|jan|feb|mar|apr|mai|jun|jul|aug|sep|okt|nov|des)\b', card_text):
                        event_cards.append(card)
                
                log_info(f"Using fallback search - found {len(event_cards)} potential event elements")
            else:
                log_info(f"Found {len(event_cards)} event cards using primary selectors")
            
            for card in event_cards:
                try:
                    event = self.extract_event_data(card)
                    if event:
                        events.append(event)
                        log_info(f"Successfully extracted event: {event['title'][:50]}...")
                except Exception as e:
                    log_warning("bibliotek_parse", f"Failed to parse event card: {e}")
                    
        except Exception as e:
            log_error("bibliotek_parse", f"Failed to parse HTML: {e}")
            
        return events
    
    def extract_event_data(self, card) -> Optional[Dict[str, Any]]:
        """Extract event data from a card element - improved for library events"""
        try:
            card_text = card.get_text()
            card_html = str(card)
            
            # Skip if this doesn't look like an event
            if len(card_text.strip()) < 20:
                return None
            
            # Extract title - try multiple approaches
            title = None
            
            # 1. Look for title in common Drupal/Views field classes
            title_selectors = [
                '.field-name-title a',
                '.field-title a',
                '.views-field-title a',
                'h2 a', 'h3 a', 'h4 a',
                '.field-name-title',
                '.field-title',
                '.views-field-title',
                'h1', 'h2', 'h3', 'h4'
            ]
            
            for selector in title_selectors:
                title_elem = card.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    if title and len(title) > 5:
                        break
            
            # 2. Fallback: look for link text or first significant text
            if not title:
                link_elem = card.find('a')
                if link_elem:
                    title = link_elem.get_text(strip=True)
                
            # 3. Last resort: use first line of text
            if not title or len(title) < 5:
                lines = [line.strip() for line in card_text.split('\n') if line.strip()]
                if lines:
                    title = lines[0]
                    
            if not title or len(title) < 5:
                return None
                
            # Extract description from various field types
            description = ""
            desc_selectors = [
                '.field-name-body',
                '.field-body',
                '.views-field-body',
                '.field-name-field-teaser',
                '.field-teaser',
                '.description',
                'p'
            ]
            
            for selector in desc_selectors:
                desc_elem = card.select_one(selector)
                if desc_elem:
                    description = desc_elem.get_text(strip=True)
                    if description and len(description) > 10:
                        break
            
            # Extract date/time information - look for the specific date format in library events
            event_date = None
            
            # First, look for the DD.MM.YY pattern specifically
            date_pattern = r'(\d{1,2})\.(\d{1,2})\.(\d{2})'
            date_match = re.search(date_pattern, card_text)
            
            if date_match:
                day, month, year_2digit = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
                year = 2000 + year_2digit
                
                # Look for time in the same text
                time_pattern = r'(\d{1,2}):(\d{2})'
                time_match = re.search(time_pattern, card_text)
                
                if time_match:
                    hour, minute = int(time_match.group(1)), int(time_match.group(2))
                else:
                    hour, minute = 18, 0  # Default time
                    
                try:
                    event_date = datetime(year, month, day, hour, minute)
                except ValueError as e:
                    log_warning("date_parse", f"Invalid date values: {day}/{month}/{year} {hour}:{minute}")
                    event_date = None
            
            # Fallback to other date selectors if direct parsing failed
            if not event_date:
                date_selectors = [
                    '.field-name-field-event-date',
                    '.field-event-date',
                    '.views-field-field-event-date',
                    '.date-display-single',
                    '.date-display-start',
                    'time',
                    '.datetime'
                ]
                
                date_text = ""
                for selector in date_selectors:
                    date_elem = card.select_one(selector)
                    if date_elem:
                        date_text = date_elem.get_text(strip=True)
                        if date_text:
                            break
                
                # If no specific date field, search in all text
                if not date_text:
                    date_text = card_text
                    
                # Parse using the enhanced parser
                event_date = self.parse_norwegian_date(date_text)
            
            # Debug: show date parsing attempts
            if event_date:
                log_info(f"DEBUG: Successfully parsed date: {event_date}")
            else:
                log_info(f"DEBUG: Failed to parse any date from card text")
            
            
            # Extract event link
            event_url = None
            link_elem = card.find('a', href=True)
            if link_elem:
                href = link_elem['href']
                event_url = href if href.startswith('http') else f"{self.base_url}{href}"
            
            # Extract venue/location info
            venue = "Moss Bibliotek"
            venue_selectors = [
                '.field-name-field-venue',
                '.field-venue',
                '.views-field-field-venue',
                '.location'
            ]
            
            for selector in venue_selectors:
                venue_elem = card.select_one(selector)
                if venue_elem:
                    venue_text = venue_elem.get_text(strip=True)
                    if venue_text:
                        venue = venue_text
                        break
            
            # Create event data
            event_data = {
                'title': title.strip(),
                'description': description[:500] if description else "",
                'start': event_date.isoformat() if event_date else None,
                'venue': venue,
                'location': "Moss, Norway", 
                'price': "Gratis",
                'info_url': event_url,
                'ticket_url': event_url,
                'source': "Moss Bibliotekene",
                'category': "Kultur",
                'raw_text': card_text[:300]
            }
            
            return event_data
            
        except Exception as e:
            log_error("bibliotek_extract", f"Failed to extract event: {e}")
            return None
    
    def parse_norwegian_date(self, text: str) -> Optional[datetime]:
        """Parse Norwegian date from text - enhanced for library site"""
        try:
            # Norwegian months mapping
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
            
            # Multiple date patterns to try
            patterns = [
                # "2025-08-30" ISO format
                r'(\d{4})-(\d{1,2})-(\d{1,2})',
                # "30.08.2025" or "30/08/2025" format
                r'(\d{1,2})[./](\d{1,2})[./](\d{4})',
                # "30.08.25" or "30/08/25" format (2-digit year)
                r'(\d{1,2})[./](\d{1,2})[./](\d{2})',
                # "30. august 2025" or "30 august"
                r'(\d{1,2})\.?\s*([a-zA-ZæøåÆØÅ]+)\s*(\d{4})?',
                # "august 30, 2025"
                r'([a-zA-ZæøåÆØÅ]+)\s+(\d{1,2}),?\s*(\d{4})?'
            ]
            
            text_lower = text.lower().strip()
            
            for pattern in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    try:
                        if pattern == patterns[0]:  # ISO format
                            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                        elif pattern == patterns[1]:  # DD.MM.YYYY format
                            day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                        elif pattern == patterns[2]:  # DD.MM.YY format (2-digit year)
                            day, month = int(match.group(1)), int(match.group(2))
                            year_2digit = int(match.group(3))
                            # Convert 2-digit year to 4-digit (25 = 2025)
                            year = 2000 + year_2digit if year_2digit >= 0 else 1900 + year_2digit
                        elif pattern == patterns[3]:  # DD month YYYY
                            day = int(match.group(1))
                            month_name = match.group(2).strip('.')
                            year = int(match.group(3)) if match.group(3) else datetime.now().year
                            month = months.get(month_name)
                            if not month:
                                continue
                        else:  # month DD, YYYY
                            month_name = match.group(1).strip('.')
                            day = int(match.group(2))
                            year = int(match.group(3)) if match.group(3) else datetime.now().year
                            month = months.get(month_name)
                            if not month:
                                continue
                        
                        # Handle year rollover for dates without explicit year
                        if not match.group(3) and month < datetime.now().month - 1:
                            year = datetime.now().year + 1
                        elif not match.group(3):
                            year = datetime.now().year
                        
                        # Look for time in the text
                        time_match = re.search(r'(\d{1,2})[:.:](\d{2})', text)
                        if time_match:
                            hour = int(time_match.group(1))
                            minute = int(time_match.group(2))
                        else:
                            # Default time for library events
                            hour, minute = 18, 0
                        
                        return datetime(year, month, day, hour, minute)
                        
                    except (ValueError, TypeError) as e:
                        log_warning("date_parse", f"Date conversion failed: {e}")
                        continue
                        
            log_warning("date_parse", f"No date pattern matched in: '{text[:100]}'")
            
        except Exception as e:
            log_warning("date_parse", f"Failed to parse date from '{text[:100]}': {e}")
            
        return None
    
    async def scrape_all_events(self, max_pages: int = 5) -> List[Dict[str, Any]]:
        """Scrape all events from multiple pages using Playwright first"""
        all_events = []
        
        for page in range(1, max_pages + 1):
            log_info(f"📚 Scraping Moss Bibliotekene page {page}")
            
            # Try Playwright first for JavaScript rendering
            html = await self.fetch_page_with_playwright(page)
            
            # Fallback to regular HTTP if Playwright fails
            if not html:
                log_info(f"Playwright failed for page {page}, trying regular HTTP")
                html = await self.fetch_page(page)
                
            if not html:
                log_info(f"Failed to fetch page {page}")
                break
                
            events = self.parse_events(html)
            if not events:
                log_info(f"No events found on page {page}, stopping pagination")
                break
                
            all_events.extend(events)
            log_info(f"Successfully extracted {len(events)} events from page {page}")
            
            # Add delay between requests
            await asyncio.sleep(2)
        
        return all_events


async def crawl_moss_bibliotek_events() -> List[Event]:
    """Main function to crawl Moss Bibliotekene events"""
    events = []
    
    try:
        async with MossBibliotekScraper() as scraper:
            event_data_list = await scraper.scrape_all_events(max_pages=3)
            
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
                        venue=event_data.get('venue', 'Moss Bibliotek'),
                        location=event_data.get('location', 'Moss, Norway'),
                        price=event_data.get('price', 'Gratis'),
                        ticket_url=event_data.get('ticket_url', ''),
                        info_url=event_data.get('info_url', ''),
                        source="Moss Bibliotekene",
                        source_type="html",
                        category=event_data.get('category', 'Kultur'),
                        age_restriction="",
                        organizer="Moss Bibliotekene",
                        first_seen=datetime.now(),
                        last_seen=datetime.now()
                    )
                    events.append(event)
                    
                except Exception as e:
                    log_error("bibliotek_convert", f"Failed to convert event: {e}")
        
        log_info(f"📚 Moss Bibliotekene: Successfully scraped {len(events)} events")
        
    except Exception as e:
        log_error("bibliotek_scraper", f"Scraping failed: {e}")
    
    return events


if __name__ == "__main__":
    async def main():
        init_logging()
        events = await crawl_moss_bibliotek_events()
        
        # Save to JSON for debugging
        output_file = Path("/var/www/vhosts/herimoss.no/pythoncrawler/bibliotek_events.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump([{
                'title': e.title,
                'start': e.start.isoformat() if e.start else None,
                'venue': e.venue,
                'price': e.price,
                'description': e.description
            } for e in events], f, ensure_ascii=False, indent=2)
        
        print(f"Scraped {len(events)} Moss Bibliotekene events")
        for event in events[:5]:
            print(f"  {event.start.strftime('%Y-%m-%d %H:%M') if event.start else 'No date'} | {event.title}")
    
    asyncio.run(main())