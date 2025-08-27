"""
HTML scraper with schema.org/JSON-LD support and fallback selectors.
"""
import json
import re
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, urlparse
import asyncio
from bs4 import BeautifulSoup
import extruct
from w3lib.html import get_base_url
from models import Event
from utils import HttpClient, clean_html_text
from logging_utils import log_info, log_error, log_warning, log_debug


class HTMLEventScraper:
    """Scraper for HTML pages with schema.org and fallback parsing."""
    
    def __init__(self, source_name: str, tz_name: str = "Europe/Oslo"):
        self.source_name = source_name
        self.tz_name = tz_name
    
    async def scrape_html_url(self, url: str, client: HttpClient) -> List[Event]:
        """Scrape events from an HTML page."""
        events = []
        
        try:
            log_info(f"Fetching HTML from {url}", source=self.source_name, url=url)
            response = await client.get(url)
            html_content = response.text
            
            # Try structured data first (JSON-LD, schema.org)
            structured_events = self._extract_structured_events(html_content, url)
            events.extend(structured_events)
            
            # If no structured data found, try HTML parsing
            if not structured_events:
                html_events = self._extract_html_events(html_content, url)
                events.extend(html_events)
            
            log_info(f"Extracted {len(events)} events from HTML", source=self.source_name, url=url)
            return events
            
        except Exception as e:
            log_error(self.source_name, f"Error scraping HTML: {e}", url=url)
            return events
    
    def _extract_structured_events(self, html_content: str, base_url: str) -> List[Event]:
        """Extract events from structured data (JSON-LD, microdata)."""
        events = []
        
        try:
            # Use extruct to extract structured data
            base_url_parsed = get_base_url(html_content, base_url)
            data = extruct.extract(html_content, base_url=base_url_parsed)
            
            # Process JSON-LD
            for item in data.get('json-ld', []):
                event = self._parse_jsonld_event(item, base_url)
                if event:
                    events.append(event)
            
            # Process microdata
            for item in data.get('microdata', []):
                if item.get('type') == ['http://schema.org/Event']:
                    event = self._parse_microdata_event(item, base_url)
                    if event:
                        events.append(event)
            
            if events:
                log_debug(f"Found {len(events)} structured data events")
            
        except Exception as e:
            log_warning(f"Failed to extract structured data: {e}", source=self.source_name)
        
        return events
    
    def _parse_jsonld_event(self, json_data: Dict[str, Any], base_url: str) -> Optional[Event]:
        """Parse JSON-LD event data."""
        try:
            # Handle both single events and arrays
            if isinstance(json_data, list):
                json_data = json_data[0] if json_data else {}
            
            event_type = json_data.get('@type', '')
            if event_type not in ['Event', 'schema:Event']:
                return None
            
            # Extract basic fields
            title = json_data.get('name', '')
            if not title:
                return None
            
            description = json_data.get('description', '')
            
            # Parse start time
            start_date = json_data.get('startDate')
            if not start_date:
                return None
            
            start_dt = self._parse_iso_datetime(start_date)
            if not start_dt:
                return None
            
            # Parse end time
            end_dt = None
            end_date = json_data.get('endDate')
            if end_date:
                end_dt = self._parse_iso_datetime(end_date)
            
            # Extract location
            venue = None
            address = None
            location = json_data.get('location', {})
            
            if isinstance(location, dict):
                venue = location.get('name', '')
                address_data = location.get('address', {})
                if isinstance(address_data, dict):
                    address = address_data.get('streetAddress', '')
                elif isinstance(address_data, str):
                    address = address_data
            elif isinstance(location, str):
                venue = location
            
            # Extract URLs
            event_url = json_data.get('url', '')
            if event_url and not event_url.startswith('http'):
                event_url = urljoin(base_url, event_url)
            
            # Extract image
            image_url = None
            image = json_data.get('image')
            if image:
                if isinstance(image, str):
                    image_url = image
                elif isinstance(image, list) and image:
                    image_url = image[0] if isinstance(image[0], str) else image[0].get('url')
                elif isinstance(image, dict):
                    image_url = image.get('url')
                
                if image_url and not image_url.startswith('http'):
                    image_url = urljoin(base_url, image_url)
            
            # Extract price
            price = None
            offers = json_data.get('offers', [])
            if offers:
                if isinstance(offers, dict):
                    offers = [offers]
                for offer in offers:
                    if isinstance(offer, dict):
                        price_val = offer.get('price')
                        currency = offer.get('priceCurrency', 'NOK')
                        if price_val:
                            if price_val == '0' or price_val == 0:
                                price = "Gratis"
                            else:
                                price = f"{currency} {price_val}" if currency != 'NOK' else f"kr {price_val}"
                            break
            
            # Create event
            now = datetime.now(timezone.utc)
            event_id = Event.generate_id(title, start_dt, venue)
            
            event = Event(
                id=event_id,
                title=title,
                description=description if description else None,
                url=event_url if event_url else None,
                image_url=image_url if image_url else None,
                venue=venue if venue else None,
                address=address if address else None,
                start=start_dt,
                end=end_dt,
                price=price,
                source=self.source_name,
                source_type="html",
                source_url=base_url,
                first_seen=now,
                last_seen=now
            )
            
            return event
            
        except Exception as e:
            log_warning(f"Failed to parse JSON-LD event: {e}", source=self.source_name)
            return None
    
    def _parse_microdata_event(self, microdata: Dict[str, Any], base_url: str) -> Optional[Event]:
        """Parse microdata event."""
        try:
            properties = microdata.get('properties', {})
            
            title = self._extract_microdata_value(properties.get('name', []))
            if not title:
                return None
            
            description = self._extract_microdata_value(properties.get('description', []))
            
            # Parse dates
            start_date = self._extract_microdata_value(properties.get('startDate', []))
            if not start_date:
                return None
            
            start_dt = self._parse_iso_datetime(start_date)
            if not start_dt:
                return None
            
            end_date = self._extract_microdata_value(properties.get('endDate', []))
            end_dt = self._parse_iso_datetime(end_date) if end_date else None
            
            # Extract location
            venue = None
            address = None
            location_data = properties.get('location', [])
            if location_data:
                location = location_data[0] if isinstance(location_data, list) else location_data
                if isinstance(location, dict):
                    loc_props = location.get('properties', {})
                    venue = self._extract_microdata_value(loc_props.get('name', []))
                    address = self._extract_microdata_value(loc_props.get('address', []))
                elif isinstance(location, str):
                    venue = location
            
            # Create event
            now = datetime.now(timezone.utc)
            event_id = Event.generate_id(title, start_dt, venue)
            
            event = Event(
                id=event_id,
                title=title,
                description=description,
                venue=venue,
                address=address,
                start=start_dt,
                end=end_dt,
                source=self.source_name,
                source_type="html",
                source_url=base_url,
                first_seen=now,
                last_seen=now
            )
            
            return event
            
        except Exception as e:
            log_warning(f"Failed to parse microdata event: {e}", source=self.source_name)
            return None
    
    def _extract_microdata_value(self, value_list: List[Any]) -> Optional[str]:
        """Extract string value from microdata value list."""
        if not value_list:
            return None
        
        value = value_list[0] if isinstance(value_list, list) else value_list
        return str(value) if value else None
    
    def _extract_html_events(self, html_content: str, base_url: str) -> List[Event]:
        """Extract events using HTML parsing with common selectors."""
        events = []
        
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Remove script and style elements that might interfere
            for element in soup(['script', 'style', 'nav', 'footer', 'header']):
                element.decompose()
            
            # Common event container selectors (order matters - most specific first)
            event_selectors = [
                '.event-item', '.event-card', '.event-listing',
                '.program-item', '.program-event', '.program-card',
                '.calendar-event', '.calendar-item', '.calendar-entry',
                '.forestilling', '.konsert', '.arrangement',
                '[itemtype*="Event"]', '[data-event]',
                '.event', '.events .item',
                'article[class*="event"]', 'div[class*="event"]'
            ]
            
            event_elements = []
            for selector in event_selectors:
                elements = soup.select(selector)
                if elements:
                    log_debug(f"Found {len(elements)} elements with selector '{selector}'")
                    event_elements.extend(elements)
                    break  # Use first successful selector
            
            # If no specific event containers, look for structured content
            if not event_elements:
                # Look for articles or sections that might contain events
                potential_containers = soup.select('article, section, .post, .content-item')
                
                # Filter for containers that likely contain event information
                for container in potential_containers:
                    text = container.get_text().lower()
                    if any(keyword in text for keyword in ['konsert', 'forestilling', 'arrangement', 'event', 'billett', 'dato', 'kl.']):
                        event_elements.append(container)
                
                if event_elements:
                    log_debug(f"Found {len(event_elements)} potential event containers")
            
            # Parse each event element
            for element in event_elements:
                event = self._parse_html_event_element(element, base_url)
                if event:
                    events.append(event)
            
            # If still no events, try table rows (some sites use tables)
            if not events:
                table_rows = soup.select('table tr, .table tr')
                for row in table_rows:
                    if len(row.find_all(['td', 'th'])) >= 3:  # At least 3 columns
                        event = self._parse_table_row_event(row, base_url)
                        if event:
                            events.append(event)
            
            if events:
                log_debug(f"Found {len(events)} HTML-parsed events")
            else:
                log_warning("No events found in HTML", source=self.source_name)
            
        except Exception as e:
            log_warning(f"Failed to parse HTML events: {e}", source=self.source_name)
        
        return events
    
    def _parse_html_event_element(self, element, base_url: str) -> Optional[Event]:
        """Parse a single HTML event element."""
        try:
            # Extract title with multiple strategies
            title = self._extract_title(element)
            if not title or len(title) < 3:
                return None
            
            # Extract description
            description = self._extract_description(element)
            
            # Extract date/time
            start_dt = self._extract_datetime(element)
            if not start_dt:
                # Skip events without dates for now
                return None
            
            # Extract venue
            venue = self._extract_venue(element)
            
            # Extract URLs
            event_url = self._extract_url(element, base_url)
            ticket_url = self._extract_ticket_url(element, base_url)
            
            # Extract image
            image_url = self._extract_image_url(element, base_url)
            
            # Extract price
            price = self._extract_price(element)
            
            # Create event
            now = datetime.now(timezone.utc)
            event_id = Event.generate_id(title, start_dt, venue)
            
            event = Event(
                id=event_id,
                title=title,
                description=description,
                url=event_url,
                ticket_url=ticket_url,
                image_url=image_url,
                venue=venue,
                price=price,
                start=start_dt,
                source=self.source_name,
                source_type="html",
                source_url=base_url,
                first_seen=now,
                last_seen=now
            )
            
            return event
            
        except Exception as e:
            log_warning(f"Failed to parse HTML event element: {e}", source=self.source_name)
            return None
    
    def _extract_title(self, element) -> Optional[str]:
        """Extract event title with multiple strategies."""
        title_selectors = [
            'h1', 'h2', 'h3', 'h4',
            '.title', '.event-title', '.name', '.headline',
            '.program-title', '.forestilling-title',
            '[itemprop="name"]', '[data-title]'
        ]
        
        for selector in title_selectors:
            title_elem = element.select_one(selector)
            if title_elem:
                title = clean_html_text(title_elem.get_text())
                if title and len(title) > 3:
                    return title
        
        # Fallback: look for the first heading or strong text
        for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'strong', 'b']:
            elem = element.find(tag)
            if elem:
                title = clean_html_text(elem.get_text())
                if title and len(title) > 3:
                    return title
        
        return None
    
    def _extract_description(self, element) -> Optional[str]:
        """Extract event description."""
        desc_selectors = [
            '.description', '.summary', '.excerpt', '.content',
            '.event-description', '.program-description',
            '[itemprop="description"]', '.lead'
        ]
        
        for selector in desc_selectors:
            desc_elem = element.select_one(selector)
            if desc_elem:
                description = clean_html_text(desc_elem.get_text())
                if description and len(description) > 20:
                    return description
        
        # Fallback: look for paragraph text
        paragraphs = element.find_all('p')
        for p in paragraphs:
            desc = clean_html_text(p.get_text())
            if desc and len(desc) > 20:
                return desc
        
        return None
    
    def _extract_datetime(self, element) -> Optional[datetime]:
        """Extract event date/time with improved parsing."""
        date_selectors = [
            '.date', '.datetime', '.time', '.when', '.dato',
            '.event-date', '.program-date', '.start-date',
            '[itemprop="startDate"]', '[datetime]', '.timestamp'
        ]
        
        # Try structured datetime first
        for selector in date_selectors:
            date_elem = element.select_one(selector)
            if date_elem:
                # Check for datetime attribute
                datetime_attr = date_elem.get('datetime')
                if datetime_attr:
                    parsed_dt = self._parse_iso_datetime(datetime_attr)
                    if parsed_dt:
                        return parsed_dt
                
                # Parse text content
                date_text = clean_html_text(date_elem.get_text())
                if date_text:
                    parsed_dt = self._parse_norwegian_date_enhanced(date_text)
                    if parsed_dt:
                        return parsed_dt
        
        # Fallback: search in all text for date patterns
        full_text = clean_html_text(element.get_text())
        return self._parse_norwegian_date_enhanced(full_text)
    
    def _extract_venue(self, element) -> Optional[str]:
        """Extract venue with improved selectors."""
        venue_selectors = [
            '.venue', '.location', '.where', '.sted', '.place',
            '.event-venue', '.program-venue',
            '[itemprop="location"]', '.address'
        ]
        
        for selector in venue_selectors:
            venue_elem = element.select_one(selector)
            if venue_elem:
                venue = clean_html_text(venue_elem.get_text())
                if venue and len(venue) > 2:
                    # Clean up common prefixes
                    venue = re.sub(r'^(sted|venue|location):\s*', '', venue, flags=re.IGNORECASE)
                    return venue.strip()
        
        # Look for known venue names in the text
        full_text = element.get_text().lower()
        known_venues = [
            'verket scene', 'moss kulturhus', 'moss teater',
            'galleri f15', 'moss bibliotek', 'moss kino'
        ]
        
        for venue in known_venues:
            if venue in full_text:
                return venue.title()
        
        return None
    
    def _extract_url(self, element, base_url: str) -> Optional[str]:
        """Extract event URL."""
        # Look for main event link
        link_elem = element.select_one('a[href]')
        if link_elem:
            href = link_elem.get('href')
            if href and not href.startswith('#'):
                return urljoin(base_url, href)
        
        return None
    
    def _extract_ticket_url(self, element, base_url: str) -> Optional[str]:
        """Extract ticket URL."""
        ticket_selectors = [
            'a[href*="billett"]', 'a[href*="ticket"]',
            '.ticket-link', '.billett-link', '.buy-ticket',
            'a[href*="ticketco"]', 'a[href*="eventim"]'
        ]
        
        for selector in ticket_selectors:
            ticket_elem = element.select_one(selector)
            if ticket_elem:
                href = ticket_elem.get('href')
                if href:
                    return urljoin(base_url, href)
        
        return None
    
    def _extract_image_url(self, element, base_url: str) -> Optional[str]:
        """Extract event image URL."""
        img_elem = element.select_one('img[src]')
        if img_elem:
            src = img_elem.get('src')
            if src and not src.startswith('data:'):  # Skip data URLs
                return urljoin(base_url, src)
        
        return None
    
    def _extract_price(self, element) -> Optional[str]:
        """Extract price information."""
        price_selectors = [
            '.price', '.pris', '.cost', '.fee',
            '[itemprop="price"]', '.ticket-price'
        ]
        
        for selector in price_selectors:
            price_elem = element.select_one(selector)
            if price_elem:
                price_text = clean_html_text(price_elem.get_text())
                if price_text:
                    from utils import extract_price_from_text
                    return extract_price_from_text(price_text)
        
        # Look for price in full text
        full_text = element.get_text()
        from utils import extract_price_from_text
        return extract_price_from_text(full_text)
    
    def _parse_table_row_event(self, row, base_url: str) -> Optional[Event]:
        """Parse event from table row."""
        try:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 2:
                return None
            
            # Common table patterns: Date | Title | Venue or Title | Date | Price
            title = None
            date_text = None
            venue = None
            
            for cell in cells:
                cell_text = clean_html_text(cell.get_text())
                if not cell_text:
                    continue
                
                # Try to identify what this cell contains
                if self._parse_norwegian_date_enhanced(cell_text):
                    date_text = cell_text
                elif len(cell_text) > 20 and not title:
                    title = cell_text
                elif any(word in cell_text.lower() for word in ['scene', 'kulturhus', 'teater']):
                    venue = cell_text
            
            if not title or not date_text:
                return None
            
            start_dt = self._parse_norwegian_date_enhanced(date_text)
            if not start_dt:
                return None
            
            # Look for links in the row
            event_url = None
            link_elem = row.select_one('a[href]')
            if link_elem:
                href = link_elem.get('href')
                if href:
                    event_url = urljoin(base_url, href)
            
            now = datetime.now(timezone.utc)
            event_id = Event.generate_id(title, start_dt, venue)
            
            event = Event(
                id=event_id,
                title=title,
                url=event_url,
                venue=venue,
                start=start_dt,
                source=self.source_name,
                source_type="html",
                source_url=base_url,
                first_seen=now,
                last_seen=now
            )
            
            return event
            
        except Exception as e:
            log_warning(f"Failed to parse table row event: {e}", source=self.source_name)
            return None
    
    def _parse_norwegian_date_enhanced(self, date_string: str) -> Optional[datetime]:
        """Enhanced Norwegian date parsing."""
        if not date_string:
            return None
        
        import re
        from dateutil import parser as date_parser
        
        # Norwegian month names
        norwegian_months = {
            'jan': 'jan', 'januar': 'january',
            'feb': 'feb', 'februar': 'february',
            'mar': 'mar', 'mars': 'march',
            'apr': 'apr', 'april': 'april',
            'mai': 'may', 'may': 'may',
            'jun': 'jun', 'juni': 'june',
            'jul': 'jul', 'juli': 'july',
            'aug': 'aug', 'august': 'august',
            'sep': 'sep', 'september': 'september',
            'okt': 'oct', 'oktober': 'october',
            'nov': 'nov', 'november': 'november',
            'des': 'dec', 'desember': 'december'
        }
        
        # Norwegian day names  
        norwegian_days = {
            'mandag': 'monday', 'tirsdag': 'tuesday', 'onsdag': 'wednesday',
            'torsdag': 'thursday', 'fredag': 'friday', 'lørdag': 'saturday', 'søndag': 'sunday',
            'man': 'mon', 'tir': 'tue', 'ons': 'wed', 'tor': 'thu', 'fre': 'fri', 'lør': 'sat', 'søn': 'sun'
        }
        
        # Comprehensive Norwegian date patterns
        patterns = [
            # DD.MM.YYYY kl HH:MM
            r'(\d{1,2})\.(\d{1,2})\.(\d{4})\s+kl\.?\s*(\d{1,2})[:\.](\d{2})',
            # DD.MM.YYYY HH:MM
            r'(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2})[:\.](\d{2})',
            # DD.MM.YYYY
            r'(\d{1,2})\.(\d{1,2})\.(\d{4})',
            # DD/MM/YYYY HH:MM
            r'(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2})',
            # DD month YYYY
            r'(\d{1,2})\.\s*(\w+)\s+(\d{4})',
            # Month DD, YYYY
            r'(\w+)\s+(\d{1,2}),?\s+(\d{4})',
        ]
        
        # Clean up the string
        text = date_string.lower().strip()
        
        # Replace Norwegian words
        for no, en in {**norwegian_months, **norwegian_days}.items():
            text = re.sub(r'\b' + no + r'\b', en, text)
        
        # Try Norwegian patterns first
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    groups = match.groups()
                    if len(groups) == 5:  # Date + time
                        day, month, year, hour, minute = groups
                        return datetime(int(year), int(month), int(day), int(hour), int(minute), tzinfo=timezone.utc)
                    elif len(groups) == 3:
                        if groups[0].isdigit():  # DD.MM.YYYY or DD/MM/YYYY
                            day, month, year = groups
                            return datetime(int(year), int(month), int(day), tzinfo=timezone.utc)
                        else:  # Month DD, YYYY
                            month_name, day, year = groups
                            month_num = list(norwegian_months.keys()).index(month_name.lower()) + 1 if month_name.lower() in norwegian_months else None
                            if month_num:
                                return datetime(int(year), month_num, int(day), tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    continue
        
        # Try dateutil parser as fallback
        try:
            return date_parser.parse(text, fuzzy=True).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            pass
        
        return None
    
    def _parse_iso_datetime(self, date_string: str) -> Optional[datetime]:
        """Parse ISO datetime string."""
        if not date_string:
            return None
        
        try:
            # Handle various ISO formats
            dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
            return dt.astimezone(timezone.utc)
        except ValueError:
            return None
    
    def _parse_norwegian_date(self, date_string: str) -> Optional[datetime]:
        """Parse Norwegian date formats."""
        if not date_string:
            return None
        
        # Norwegian date patterns
        patterns = [
            r'(\d{1,2})\.(\d{1,2})\.(\d{4})',  # 25.12.2025
            r'(\d{1,2})/(\d{1,2})/(\d{4})',   # 25/12/2025
            r'(\d{4})-(\d{1,2})-(\d{1,2})',   # 2025-12-25
        ]
        
        for pattern in patterns:
            match = re.search(pattern, date_string)
            if match:
                try:
                    if pattern.startswith(r'(\d{4})'):  # YYYY-MM-DD
                        year, month, day = match.groups()
                    else:  # DD.MM.YYYY or DD/MM/YYYY
                        day, month, year = match.groups()
                    
                    return datetime(int(year), int(month), int(day), tzinfo=timezone.utc)
                except ValueError:
                    continue
        
        return None


async def scrape_moss_kulturhus(config: dict, client: HttpClient) -> List[Event]:
    """Scrape events from Moss Kulturhus."""
    scraper = HTMLEventScraper("Moss Kulturhus")
    events = []
    
    # Process HTML URLs
    for url in config.get("html_urls", []):
        events.extend(await scraper.scrape_html_url(url, client))
    
    return events


async def scrape_verket_scene(config: dict, client: HttpClient) -> List[Event]:
    """Scrape events from Verket Scene."""
    scraper = HTMLEventScraper("Verket Scene")
    events = []
    
    # Process HTML URLs
    for url in config.get("html_urls", []):
        events.extend(await scraper.scrape_html_url(url, client))
    
    return events
