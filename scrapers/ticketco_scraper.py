"""
TicketCo scraper for Norwegian event ticketing platform.
Handles TicketCo's event listings with respect for ToS and rate limiting.
"""
import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, urlparse
import pytz
from bs4 import BeautifulSoup
from models import Event
from utils import HttpClient
from normalize import EventNormalizer
from logging_utils import log_info, log_warning, log_error


class TicketCoScraper:
    """Scraper for TicketCo ticket platform."""
    
    def __init__(self):
        self.base_url = "https://ticketco.events"
        self.oslo_tz = pytz.timezone('Europe/Oslo')
        self.normalizer = EventNormalizer()
        
        # Common Norwegian venues that use TicketCo
        self.norwegian_venues = [
            'oslo-spektrum', 'telenor-arena', 'sentrum-scene', 
            'rockefeller', 'parkteatret', 'gamla', 'vulkan-arena',
            'oslo-konserthus', 'operaen', 'nationaltheatret',
            'moss-kulturhus', 'verket-scene'
        ]
    
    async def scrape_events(self, client: HttpClient, venue_slug: str = None, 
                          days_ahead: int = 90) -> List[Event]:
        """Scrape events from TicketCo."""
        all_events = []
        
        if venue_slug:
            # Scrape specific venue
            venue_events = await self._scrape_venue(client, venue_slug, days_ahead)
            all_events.extend(venue_events)
        else:
            # Scrape multiple Norwegian venues
            for venue in self.norwegian_venues:
                try:
                    venue_events = await self._scrape_venue(client, venue, days_ahead)
                    all_events.extend(venue_events)
                    
                    # Rate limiting - be respectful
                    await asyncio.sleep(2.0)
                    
                except Exception as e:
                    log_warning(f"Failed to scrape TicketCo venue {venue}: {e}")
                    continue
        
        # Remove duplicates
        seen_ids = set()
        unique_events = []
        for event in all_events:
            if event.id not in seen_ids:
                seen_ids.add(event.id)
                unique_events.append(event)
        
        log_info(f"TicketCo scraper found {len(unique_events)} unique events")
        return unique_events
    
    async def _scrape_venue(self, client: HttpClient, venue_slug: str, 
                          days_ahead: int) -> List[Event]:
        """Scrape events for a specific venue."""
        try:
            # Try multiple URL patterns for TicketCo venues
            possible_urls = [
                f"{self.base_url}/no/{venue_slug}",
                f"{self.base_url}/venue/{venue_slug}",
                f"{self.base_url}/organizer/{venue_slug}",
                f"{self.base_url}/search?venue={venue_slug}"
            ]
            
            for url in possible_urls:
                try:
                    events = await self._scrape_venue_url(client, url, venue_slug)
                    if events:
                        log_info(f"Found {len(events)} events for {venue_slug} at {url}")
                        return events
                    
                    # Try next URL pattern
                    await asyncio.sleep(1.0)
                    
                except Exception as e:
                    log_warning(f"Failed to scrape {url}: {e}")
                    continue
            
            log_warning(f"No events found for venue {venue_slug} in any URL pattern")
            return []
            
        except Exception as e:
            log_error(f"Failed to scrape venue {venue_slug}: {e}")
            return []
    
    async def _scrape_venue_url(self, client: HttpClient, url: str, 
                              venue_slug: str) -> List[Event]:
        """Scrape events from a specific venue URL."""
        try:
            headers = {
                'User-Agent': 'MossKulturkalender/1.0 (Culture Event Aggregator)',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'no,en-US;q=0.7,en;q=0.3',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive'
            }
            
            response = await client.get(url, headers=headers)
            
            if response.status_code == 404:
                return []
            elif response.status_code != 200:
                log_warning(f"TicketCo returned status {response.status_code} for {url}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try multiple parsing strategies
            events = []
            
            # Strategy 1: Look for JSON-LD structured data
            json_ld_events = await self._parse_json_ld(soup, url)
            events.extend(json_ld_events)
            
            # Strategy 2: Parse event cards/listings
            html_events = await self._parse_event_cards(soup, url, venue_slug)
            events.extend(html_events)
            
            # Strategy 3: Look for ticket links and follow them
            ticket_events = await self._parse_ticket_links(client, soup, url, venue_slug)
            events.extend(ticket_events)
            
            return events
            
        except Exception as e:
            log_error(f"Failed to scrape TicketCo URL {url}: {e}")
            return []
    
    async def _parse_json_ld(self, soup: BeautifulSoup, source_url: str) -> List[Event]:
        """Parse JSON-LD structured data for events."""
        events = []
        
        try:
            json_scripts = soup.find_all('script', type='application/ld+json')
            
            for script in json_scripts:
                try:
                    data = json.loads(script.string)
                    
                    # Handle both single events and arrays
                    if isinstance(data, list):
                        items = data
                    else:
                        items = [data] if data.get('@type') == 'Event' else []
                    
                    for item in items:
                        if item.get('@type') == 'Event':
                            event = await self._parse_json_ld_event(item, source_url)
                            if event:
                                events.append(event)
                                
                except (json.JSONDecodeError, KeyError) as e:
                    log_warning(f"Failed to parse JSON-LD: {e}")
                    continue
            
            return events
            
        except Exception as e:
            log_warning(f"Failed to parse JSON-LD from {source_url}: {e}")
            return []
    
    async def _parse_json_ld_event(self, data: Dict[str, Any], source_url: str) -> Optional[Event]:
        """Parse a single event from JSON-LD data."""
        try:
            title = data.get('name', '').strip()
            if not title:
                return None
            
            description = data.get('description', '')
            event_url = data.get('url', source_url)
            
            # Parse start date
            start_date_str = data.get('startDate')
            if not start_date_str:
                return None
            
            start_time = self.normalizer.normalize_datetime(start_date_str)
            if not start_time:
                return None
            
            # Parse end date (optional)
            end_time = None
            end_date_str = data.get('endDate')
            if end_date_str:
                end_time = self.normalizer.normalize_datetime(end_date_str)
            
            # Venue information
            location_data = data.get('location', {})
            venue_name = location_data.get('name', '') if isinstance(location_data, dict) else str(location_data)
            
            address = None
            if isinstance(location_data, dict) and 'address' in location_data:
                addr_data = location_data['address']
                if isinstance(addr_data, dict):
                    address_parts = []
                    if addr_data.get('streetAddress'):
                        address_parts.append(addr_data['streetAddress'])
                    if addr_data.get('addressLocality'):
                        address_parts.append(addr_data['addressLocality'])
                    address = ', '.join(address_parts) if address_parts else None
                else:
                    address = str(addr_data)
            
            # Price information
            offers = data.get('offers', {})
            price = None
            if isinstance(offers, dict):
                price_value = offers.get('price')
                currency = offers.get('priceCurrency', 'NOK')
                if price_value:
                    price = f"{currency} {price_value}"
            
            # Image
            image_url = data.get('image')
            if isinstance(image_url, list) and image_url:
                image_url = image_url[0]
            
            # Generate event ID
            event_id = Event.generate_id(title, start_time, venue_name)
            now = datetime.now(pytz.UTC)
            
            # Create Event object
            event = Event(
                id=event_id,
                title=title,
                description=description[:1000] if description else None,
                url=event_url,
                image_url=image_url,
                venue=venue_name,
                address=address,
                start=start_time,
                end=end_time,
                price=price,
                source="ticketco",
                source_type="html",
                source_url=source_url,
                first_seen=now,
                last_seen=now
            )
            
            return event
            
        except Exception as e:
            log_warning(f"Failed to parse JSON-LD event: {e}")
            return None
    
    async def _parse_event_cards(self, soup: BeautifulSoup, source_url: str, 
                                venue_slug: str) -> List[Event]:
        """Parse event cards from HTML."""
        events = []
        
        try:
            # Common selectors for event cards on TicketCo
            card_selectors = [
                '.event-card',
                '.event-item',
                '.event-listing',
                '[data-event]',
                '.card.event',
                '.tc-event'
            ]
            
            event_cards = []
            for selector in card_selectors:
                cards = soup.select(selector)
                if cards:
                    event_cards = cards
                    log_info(f"Found {len(cards)} event cards with selector '{selector}'")
                    break
            
            if not event_cards:
                # Fallback: look for elements containing event-like text
                event_cards = soup.find_all(attrs={'class': re.compile(r'event|ticket|show')})
            
            for card in event_cards[:20]:  # Limit to avoid too many requests
                try:
                    event = await self._parse_event_card(card, source_url, venue_slug)
                    if event:
                        events.append(event)
                except Exception as e:
                    log_warning(f"Failed to parse event card: {e}")
                    continue
            
            return events
            
        except Exception as e:
            log_warning(f"Failed to parse event cards: {e}")
            return []
    
    async def _parse_event_card(self, card, source_url: str, venue_slug: str) -> Optional[Event]:
        """Parse a single event card element."""
        try:
            # Extract title
            title_selectors = ['h1', 'h2', 'h3', '.title', '.event-title', '[data-title]']
            title = None
            for selector in title_selectors:
                title_elem = card.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    break
            
            if not title:
                return None
            
            # Extract date/time
            date_selectors = ['.date', '.datetime', '.time', '[data-date]', '.event-date']
            date_text = None
            for selector in date_selectors:
                date_elem = card.select_one(selector)
                if date_elem:
                    date_text = date_elem.get_text(strip=True)
                    break
            
            if not date_text:
                # Try to find date in title or other text
                text_content = card.get_text()
                date_patterns = [
                    r'\d{1,2}\.\s*\w+\s*\d{4}',  # Norwegian date format
                    r'\d{4}-\d{2}-\d{2}',        # ISO date
                    r'\d{1,2}/\d{1,2}/\d{4}'     # US date format
                ]
                for pattern in date_patterns:
                    match = re.search(pattern, text_content)
                    if match:
                        date_text = match.group()
                        break
            
            if not date_text:
                return None
            
            start_time = self.normalizer.normalize_datetime(date_text)
            if not start_time:
                return None
            
            # Extract event URL
            event_url = source_url
            link_elem = card.find('a', href=True)
            if link_elem:
                event_url = urljoin(source_url, link_elem['href'])
            
            # Extract venue (use venue_slug as fallback)
            venue_name = venue_slug.replace('-', ' ').title()
            venue_selectors = ['.venue', '.location', '[data-venue]']
            for selector in venue_selectors:
                venue_elem = card.select_one(selector)
                if venue_elem:
                    venue_name = venue_elem.get_text(strip=True)
                    break
            
            # Extract description
            description = None
            desc_selectors = ['.description', '.summary', '.event-desc']
            for selector in desc_selectors:
                desc_elem = card.select_one(selector)
                if desc_elem:
                    description = desc_elem.get_text(strip=True)
                    break
            
            # Extract price
            price = None
            price_selectors = ['.price', '.cost', '[data-price]']
            for selector in price_selectors:
                price_elem = card.select_one(selector)
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    price = self.normalizer.normalize_price(price_text)
                    break
            
            # Generate event ID
            event_id = Event.generate_id(title, start_time, venue_name)
            now = datetime.now(pytz.UTC)
            
            # Create Event object
            event = Event(
                id=event_id,
                title=title,
                description=description,
                url=event_url,
                venue=venue_name,
                start=start_time,
                price=price,
                source="ticketco",
                source_type="html",
                source_url=source_url,
                first_seen=now,
                last_seen=now
            )
            
            return event
            
        except Exception as e:
            log_warning(f"Failed to parse event card: {e}")
            return None
    
    async def _parse_ticket_links(self, client: HttpClient, soup: BeautifulSoup, 
                                source_url: str, venue_slug: str) -> List[Event]:
        """Find and follow ticket purchase links to get event details."""
        events = []
        
        try:
            # Find ticket/buy links
            ticket_links = soup.find_all('a', href=re.compile(r'ticket|buy|event|show'))
            
            for link in ticket_links[:5]:  # Limit to avoid too many requests
                try:
                    href = link.get('href')
                    if not href:
                        continue
                    
                    full_url = urljoin(source_url, href)
                    
                    # Skip external links
                    if not full_url.startswith(self.base_url):
                        continue
                    
                    # Get link text as potential event title
                    link_text = link.get_text(strip=True)
                    if len(link_text) < 3:
                        continue
                    
                    # Simple event creation from link
                    # (In production, you might want to follow the link and parse the detail page)
                    venue_name = venue_slug.replace('-', ' ').title()
                    
                    # Try to extract date from link text or URL
                    date_match = re.search(r'\d{4}-\d{2}-\d{2}', href)
                    if date_match:
                        date_str = date_match.group()
                        start_time = self.normalizer.normalize_datetime(date_str)
                        
                        if start_time:
                            event_id = Event.generate_id(link_text, start_time, venue_name)
                            now = datetime.now(pytz.UTC)
                            
                            event = Event(
                                id=event_id,
                                title=link_text,
                                url=full_url,
                                venue=venue_name,
                                start=start_time,
                                source="ticketco",
                                source_type="html",
                                source_url=source_url,
                                first_seen=now,
                                last_seen=now
                            )
                            
                            events.append(event)
                
                except Exception as e:
                    log_warning(f"Failed to parse ticket link: {e}")
                    continue
            
            return events
            
        except Exception as e:
            log_warning(f"Failed to parse ticket links: {e}")
            return []


async def scrape_ticketco_events(config: dict, client: HttpClient) -> List[Event]:
    """Main entry point for TicketCo scraping."""
    try:
        venue_slug = config.get('venue_slug')
        days_ahead = config.get('days_ahead', 90)
        
        scraper = TicketCoScraper()
        events = await scraper.scrape_events(
            client=client,
            venue_slug=venue_slug,
            days_ahead=days_ahead
        )
        
        log_info(f"TicketCo scraper completed: {len(events)} events found")
        return events
        
    except Exception as e:
        log_error(f"TicketCo scraping failed: {e}")
        return []


# For backwards compatibility
async def scrape_ticketco(config: dict, client: HttpClient) -> List[Event]:
    """Alias for scrape_ticketco_events."""
    return await scrape_ticketco_events(config, client)
