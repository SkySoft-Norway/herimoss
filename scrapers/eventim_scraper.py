"""
Eventim scraper for Norwegian events.
Handles Eventim.no with respect for ToS and robust parsing strategies.
"""
import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, urlparse, quote
import pytz
from bs4 import BeautifulSoup
from models import Event
from utils import HttpClient
from normalize import EventNormalizer
from logging_utils import log_info, log_warning, log_error


class EventimScraper:
    """Scraper for Eventim.no ticket platform."""
    
    def __init__(self):
        self.base_url = "https://www.eventim.no"
        self.oslo_tz = pytz.timezone('Europe/Oslo')
        self.normalizer = EventNormalizer()
        
        # Norwegian cities with active Eventim events
        self.norwegian_cities = [
            'oslo', 'bergen', 'trondheim', 'stavanger', 'kristiansand',
            'moss', 'drammen', 'sarpsborg', 'fredrikstad', 'tønsberg'
        ]
        
        # Categories relevant to Norwegian cultural events
        self.categories = [
            'concerts', 'theatre', 'comedy', 'festivals', 'family',
            'sports', 'arts-culture', 'shows'
        ]
    
    async def scrape_events(self, client: HttpClient, city: str = 'oslo', 
                          category: str = None, days_ahead: int = 90) -> List[Event]:
        """Scrape events from Eventim.no."""
        all_events = []
        
        try:
            # Strategy 1: Search by city
            city_events = await self._search_by_city(client, city, days_ahead)
            all_events.extend(city_events)
            
            # Strategy 2: Search by categories
            if category:
                categories = [category]
            else:
                categories = self.categories
            
            for cat in categories:
                try:
                    cat_events = await self._search_by_category(client, cat, city, days_ahead)
                    all_events.extend(cat_events)
                    
                    # Rate limiting
                    await asyncio.sleep(1.5)
                    
                except Exception as e:
                    log_warning(f"Failed to scrape Eventim category {cat}: {e}")
                    continue
            
            # Remove duplicates
            seen_ids = set()
            unique_events = []
            for event in all_events:
                if event.id not in seen_ids:
                    seen_ids.add(event.id)
                    unique_events.append(event)
            
            log_info(f"Eventim scraper found {len(unique_events)} unique events")
            return unique_events
            
        except Exception as e:
            log_error(f"Eventim scraping failed: {e}")
            return []
    
    async def _search_by_city(self, client: HttpClient, city: str, days_ahead: int) -> List[Event]:
        """Search for events in a specific city."""
        try:
            # Eventim.no search URL patterns
            search_urls = [
                f"{self.base_url}/no/billett/byar/{city}",
                f"{self.base_url}/no/tickets/cities/{city}",
                f"{self.base_url}/search?city={quote(city)}&country=no"
            ]
            
            for url in search_urls:
                try:
                    events = await self._scrape_search_results(client, url)
                    if events:
                        log_info(f"Found {len(events)} events for {city} at {url}")
                        return events
                    
                    await asyncio.sleep(1.0)
                    
                except Exception as e:
                    log_warning(f"Failed to scrape {url}: {e}")
                    continue
            
            return []
            
        except Exception as e:
            log_error(f"Failed to search by city {city}: {e}")
            return []
    
    async def _search_by_category(self, client: HttpClient, category: str, 
                                city: str, days_ahead: int) -> List[Event]:
        """Search for events in a specific category."""
        try:
            # Category-based search URLs
            search_urls = [
                f"{self.base_url}/no/billett/{category}",
                f"{self.base_url}/no/tickets/{category}",
                f"{self.base_url}/search?category={quote(category)}&city={quote(city)}"
            ]
            
            events = []
            for url in search_urls:
                try:
                    url_events = await self._scrape_search_results(client, url)
                    events.extend(url_events)
                    
                    await asyncio.sleep(1.0)
                    
                except Exception as e:
                    log_warning(f"Failed to scrape category URL {url}: {e}")
                    continue
            
            return events
            
        except Exception as e:
            log_error(f"Failed to search by category {category}: {e}")
            return []
    
    async def _scrape_search_results(self, client: HttpClient, url: str) -> List[Event]:
        """Scrape events from a search results page."""
        try:
            headers = {
                'User-Agent': 'MossKulturkalender/1.0 (Culture Event Aggregator)',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'no,en-US;q=0.7,en;q=0.3',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Cache-Control': 'max-age=0'
            }
            
            response = await client.get(url, headers=headers)
            
            if response.status_code == 404:
                return []
            elif response.status_code != 200:
                log_warning(f"Eventim returned status {response.status_code} for {url}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try multiple parsing strategies
            events = []
            
            # Strategy 1: JSON-LD structured data
            json_ld_events = await self._parse_json_ld(soup, url)
            events.extend(json_ld_events)
            
            # Strategy 2: Event list items
            list_events = await self._parse_event_listings(soup, url)
            events.extend(list_events)
            
            # Strategy 3: Product/ticket cards
            card_events = await self._parse_product_cards(soup, url)
            events.extend(card_events)
            
            return events
            
        except Exception as e:
            log_error(f"Failed to scrape search results from {url}: {e}")
            return []
    
    async def _parse_json_ld(self, soup: BeautifulSoup, source_url: str) -> List[Event]:
        """Parse JSON-LD structured data."""
        events = []
        
        try:
            json_scripts = soup.find_all('script', type='application/ld+json')
            
            for script in json_scripts:
                try:
                    if not script.string:
                        continue
                        
                    data = json.loads(script.string)
                    
                    # Handle both single events and arrays
                    if isinstance(data, list):
                        items = data
                    elif isinstance(data, dict):
                        if data.get('@type') == 'Event':
                            items = [data]
                        elif 'mainEntity' in data:
                            main_entity = data['mainEntity']
                            items = main_entity if isinstance(main_entity, list) else [main_entity]
                        else:
                            items = []
                    else:
                        items = []
                    
                    for item in items:
                        if isinstance(item, dict) and item.get('@type') == 'Event':
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
            if not event_url.startswith('http'):
                event_url = urljoin(self.base_url, event_url)
            
            # Parse start date
            start_date_str = data.get('startDate')
            if not start_date_str:
                return None
            
            start_time = self.normalizer.normalize_datetime(start_date_str)
            if not start_time:
                return None
            
            # Parse end date
            end_time = None
            end_date_str = data.get('endDate')
            if end_date_str:
                end_time = self.normalizer.normalize_datetime(end_date_str)
            
            # Venue information
            location_data = data.get('location', {})
            venue_name = ''
            address = None
            
            if isinstance(location_data, dict):
                venue_name = location_data.get('name', '')
                
                addr_data = location_data.get('address', {})
                if isinstance(addr_data, dict):
                    address_parts = []
                    if addr_data.get('streetAddress'):
                        address_parts.append(addr_data['streetAddress'])
                    if addr_data.get('addressLocality'):
                        address_parts.append(addr_data['addressLocality'])
                    if addr_data.get('addressCountry'):
                        address_parts.append(addr_data['addressCountry'])
                    address = ', '.join(address_parts) if address_parts else None
                elif isinstance(addr_data, str):
                    address = addr_data
            elif isinstance(location_data, str):
                venue_name = location_data
            
            # Price information
            offers = data.get('offers', {})
            price = None
            if isinstance(offers, dict):
                price_value = offers.get('price') or offers.get('lowPrice')
                currency = offers.get('priceCurrency', 'NOK')
                if price_value:
                    price = f"{currency} {price_value}"
            elif isinstance(offers, list) and offers:
                offer = offers[0]
                price_value = offer.get('price')
                currency = offer.get('priceCurrency', 'NOK')
                if price_value:
                    price = f"{currency} {price_value}"
            
            # Image
            image_url = data.get('image')
            if isinstance(image_url, list) and image_url:
                image_url = image_url[0]
            if isinstance(image_url, dict):
                image_url = image_url.get('url')
            
            # Performer/artist information
            performers = data.get('performer', [])
            if performers and not description:
                if isinstance(performers, list):
                    artist_names = [p.get('name', '') for p in performers if isinstance(p, dict)]
                    if artist_names:
                        description = f"Opptreden med {', '.join(artist_names[:3])}"
                elif isinstance(performers, dict):
                    artist_name = performers.get('name', '')
                    if artist_name:
                        description = f"Opptreden med {artist_name}"
            
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
                source="eventim",
                source_type="html",
                source_url=source_url,
                first_seen=now,
                last_seen=now
            )
            
            return event
            
        except Exception as e:
            log_warning(f"Failed to parse JSON-LD event: {e}")
            return None
    
    async def _parse_event_listings(self, soup: BeautifulSoup, source_url: str) -> List[Event]:
        """Parse event listings from HTML."""
        events = []
        
        try:
            # Common selectors for Eventim event listings
            listing_selectors = [
                '.event-item',
                '.product-item',
                '.ticket-item',
                '.search-result-item',
                '[data-event-id]',
                '.event-card',
                '.teaser-event'
            ]
            
            event_items = []
            for selector in listing_selectors:
                items = soup.select(selector)
                if items:
                    event_items = items
                    log_info(f"Found {len(items)} event items with selector '{selector}'")
                    break
            
            if not event_items:
                # Fallback: look for list items with event-like content
                all_items = soup.find_all(['li', 'div', 'article'])
                event_items = [item for item in all_items 
                             if any(keyword in item.get_text().lower() 
                                   for keyword in ['billett', 'konsert', 'forestilling', 'show'])]
            
            for item in event_items[:25]:  # Limit to avoid too many
                try:
                    event = await self._parse_event_item(item, source_url)
                    if event:
                        events.append(event)
                except Exception as e:
                    log_warning(f"Failed to parse event item: {e}")
                    continue
            
            return events
            
        except Exception as e:
            log_warning(f"Failed to parse event listings: {e}")
            return []
    
    async def _parse_event_item(self, item, source_url: str) -> Optional[Event]:
        """Parse a single event item element."""
        try:
            # Extract title
            title_selectors = [
                'h1', 'h2', 'h3', 'h4',
                '.title', '.event-title', '.product-title',
                '.headline', '[data-title]', 'a[title]'
            ]
            
            title = None
            for selector in title_selectors:
                title_elem = item.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    if len(title) > 3:  # Valid title length
                        break
            
            # Fallback: use link text
            if not title:
                link = item.find('a')
                if link:
                    title = link.get_text(strip=True)
            
            if not title or len(title) < 3:
                return None
            
            # Extract date/time
            date_selectors = [
                '.date', '.datetime', '.time', '.when',
                '[data-date]', '.event-date', '.product-date'
            ]
            
            date_text = None
            for selector in date_selectors:
                date_elem = item.select_one(selector)
                if date_elem:
                    date_text = date_elem.get_text(strip=True)
                    break
            
            # Fallback: search for date patterns in text
            if not date_text:
                text_content = item.get_text()
                date_patterns = [
                    r'\d{1,2}\.\s*\w+\s*\d{4}',     # "25. august 2025"
                    r'\d{4}-\d{2}-\d{2}',           # "2025-08-25"
                    r'\d{1,2}/\d{1,2}/\d{4}',       # "25/08/2025"
                    r'\w+\s+\d{1,2},?\s+\d{4}'      # "August 25, 2025"
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
            link_elem = item.find('a', href=True)
            if link_elem:
                href = link_elem['href']
                event_url = urljoin(self.base_url, href)
            
            # Extract venue
            venue_selectors = [
                '.venue', '.location', '.where', 
                '[data-venue]', '.event-location'
            ]
            
            venue_name = None
            for selector in venue_selectors:
                venue_elem = item.select_one(selector)
                if venue_elem:
                    venue_name = venue_elem.get_text(strip=True)
                    break
            
            # Extract price
            price_selectors = [
                '.price', '.cost', '.amount',
                '[data-price]', '.product-price'
            ]
            
            price = None
            for selector in price_selectors:
                price_elem = item.select_one(selector)
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    price = self.normalizer.normalize_price(price_text)
                    break
            
            # Generate event ID
            event_id = Event.generate_id(title, start_time, venue_name or 'Unknown')
            now = datetime.now(pytz.UTC)
            
            # Create Event object
            event = Event(
                id=event_id,
                title=title,
                url=event_url,
                venue=venue_name,
                start=start_time,
                price=price,
                source="eventim",
                source_type="html",
                source_url=source_url,
                first_seen=now,
                last_seen=now
            )
            
            return event
            
        except Exception as e:
            log_warning(f"Failed to parse event item: {e}")
            return None
    
    async def _parse_product_cards(self, soup: BeautifulSoup, source_url: str) -> List[Event]:
        """Parse product/ticket cards."""
        # Similar to _parse_event_listings but with different selectors
        # This is a simplified version - in production you might want more sophisticated parsing
        return []


async def scrape_eventim_events(config: dict, client: HttpClient) -> List[Event]:
    """Main entry point for Eventim scraping."""
    try:
        city = config.get('city', 'oslo')
        category = config.get('category')
        days_ahead = config.get('days_ahead', 90)
        
        scraper = EventimScraper()
        events = await scraper.scrape_events(
            client=client,
            city=city,
            category=category,
            days_ahead=days_ahead
        )
        
        log_info(f"Eventim scraper completed: {len(events)} events found")
        return events
        
    except Exception as e:
        log_error(f"Eventim scraping failed: {e}")
        return []


# For backwards compatibility
async def scrape_eventim(config: dict, client: HttpClient) -> List[Event]:
    """Alias for scrape_eventim_events."""
    return await scrape_eventim_events(config, client)
