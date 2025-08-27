"""
Booking widget JSON endpoint scraper.
Handles various JSON-based booking systems and event APIs.
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union
from urllib.parse import urljoin, urlparse
import pytz
from models import Event
from utils import HttpClient
from normalize import EventNormalizer
from logging_utils import log_info, log_warning, log_error


class BookingWidgetScraper:
    """Scraper for JSON-based booking widgets and event APIs."""
    
    def __init__(self):
        self.oslo_tz = pytz.timezone('Europe/Oslo')
        self.normalizer = EventNormalizer()
        
        # Common JSON endpoint patterns
        self.common_endpoints = [
            '/api/events',
            '/api/calendar',
            '/events.json',
            '/calendar.json',
            '/api/v1/events',
            '/wp-json/wp/v2/events',
            '/api/bookings',
            '/widget/events'
        ]
        
        # Known booking widget systems
        self.widget_systems = {
            'artifax': {
                'endpoints': ['/api/events', '/events.json'],
                'date_formats': ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S']
            },
            'eventbrite': {
                'endpoints': ['/events/', '/api/events/'],
                'date_formats': ['%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ']
            },
            'ticketmaster': {
                'endpoints': ['/discovery/v2/events.json'],
                'date_formats': ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%SZ']
            },
            'custom': {
                'endpoints': ['/api/events', '/calendar/events'],
                'date_formats': ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S']
            }
        }
    
    async def scrape_json_endpoints(self, client: HttpClient, base_url: str,
                                   endpoints: List[str] = None,
                                   widget_type: str = 'custom') -> List[Event]:
        """Scrape events from JSON endpoints."""
        all_events = []
        
        # Use provided endpoints or try common ones
        if not endpoints:
            if widget_type in self.widget_systems:
                endpoints = self.widget_systems[widget_type]['endpoints']
            else:
                endpoints = self.common_endpoints
        
        for endpoint in endpoints:
            try:
                url = urljoin(base_url, endpoint)
                endpoint_events = await self._scrape_json_endpoint(client, url, widget_type)
                all_events.extend(endpoint_events)
                
                # Rate limiting
                await asyncio.sleep(1.0)
                
            except Exception as e:
                log_warning(f"Failed to scrape JSON endpoint {endpoint}: {e}")
                continue
        
        # Remove duplicates
        seen_ids = set()
        unique_events = []
        for event in all_events:
            if event.id not in seen_ids:
                seen_ids.add(event.id)
                unique_events.append(event)
        
        log_info(f"JSON widget scraper found {len(unique_events)} unique events")
        return unique_events
    
    async def _scrape_json_endpoint(self, client: HttpClient, url: str, 
                                  widget_type: str) -> List[Event]:
        """Scrape events from a single JSON endpoint."""
        try:
            headers = {
                'Accept': 'application/json, text/json, */*',
                'User-Agent': 'MossKulturkalender/1.0 (Culture Event Aggregator)',
                'Content-Type': 'application/json'
            }
            
            response = await client.get(url, headers=headers)
            
            if response.status_code == 404:
                return []
            elif response.status_code != 200:
                log_warning(f"JSON endpoint {url} returned status {response.status_code}")
                return []
            
            # Try to parse JSON
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                log_warning(f"Failed to parse JSON from {url}: {e}")
                return []
            
            # Parse events based on widget type and data structure
            events = await self._parse_json_data(data, url, widget_type)
            
            return events
            
        except Exception as e:
            log_error(f"Failed to scrape JSON endpoint {url}: {e}")
            return []
    
    async def _parse_json_data(self, data: Any, source_url: str, 
                             widget_type: str) -> List[Event]:
        """Parse events from JSON data with flexible structure handling."""
        events = []
        
        try:
            # Handle different JSON structures
            if isinstance(data, dict):
                # Check for common event array keys
                event_keys = ['events', 'data', 'items', 'results', 'entries', '_embedded']
                events_data = None
                
                for key in event_keys:
                    if key in data:
                        events_data = data[key]
                        break
                
                # Handle _embedded structure (HAL format)
                if key == '_embedded' and isinstance(events_data, dict):
                    for embedded_key in ['events', 'items']:
                        if embedded_key in events_data:
                            events_data = events_data[embedded_key]
                            break
                
                # If no array found, treat the whole object as a single event
                if events_data is None:
                    if self._looks_like_event(data):
                        events_data = [data]
                    else:
                        return []
                        
            elif isinstance(data, list):
                events_data = data
            else:
                return []
            
            # Parse individual events
            for event_data in events_data:
                if isinstance(event_data, dict):
                    event = await self._parse_json_event(event_data, source_url, widget_type)
                    if event:
                        events.append(event)
            
            return events
            
        except Exception as e:
            log_warning(f"Failed to parse JSON data: {e}")
            return []
    
    def _looks_like_event(self, data: dict) -> bool:
        """Check if a JSON object looks like an event."""
        event_indicators = [
            'title', 'name', 'event_name',
            'date', 'start_date', 'start_time', 'datetime',
            'venue', 'location', 'place'
        ]
        
        return any(key in data for key in event_indicators)
    
    async def _parse_json_event(self, data: dict, source_url: str, 
                              widget_type: str) -> Optional[Event]:
        """Parse a single event from JSON data."""
        try:
            # Extract title (try multiple possible keys)
            title_keys = ['title', 'name', 'event_name', 'headline', 'summary']
            title = None
            for key in title_keys:
                if key in data and data[key]:
                    title = str(data[key]).strip()
                    break
            
            if not title:
                return None
            
            # Extract description
            desc_keys = ['description', 'summary', 'content', 'details', 'body']
            description = None
            for key in desc_keys:
                if key in data and data[key]:
                    description = str(data[key]).strip()
                    break
            
            # Extract start date/time
            start_time = await self._parse_event_datetime(data, widget_type, is_start=True)
            if not start_time:
                return None
            
            # Extract end date/time (optional)
            end_time = await self._parse_event_datetime(data, widget_type, is_start=False)
            
            # Extract venue information
            venue_name, address = await self._parse_venue_info(data)
            
            # Extract URL
            url_keys = ['url', 'link', 'event_url', 'permalink', 'booking_url']
            event_url = source_url
            for key in url_keys:
                if key in data and data[key]:
                    url_value = data[key]
                    if isinstance(url_value, str) and url_value.startswith('http'):
                        event_url = url_value
                        break
                    elif isinstance(url_value, str):
                        event_url = urljoin(source_url, url_value)
                        break
            
            # Extract price information
            price = await self._parse_price_info(data)
            
            # Extract image URL
            image_url = await self._parse_image_url(data, source_url)
            
            # Extract category
            category = await self._parse_category(data)
            
            # Generate event ID
            event_id = Event.generate_id(title, start_time, venue_name or 'Unknown')
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
                category=category,
                start=start_time,
                end=end_time,
                price=price,
                source="booking_widget",
                source_type="api",
                source_url=source_url,
                first_seen=now,
                last_seen=now
            )
            
            return event
            
        except Exception as e:
            log_warning(f"Failed to parse JSON event: {e}")
            return None
    
    async def _parse_event_datetime(self, data: dict, widget_type: str, 
                                  is_start: bool = True) -> Optional[datetime]:
        """Parse start or end datetime from event data."""
        try:
            # Determine which datetime keys to look for
            if is_start:
                datetime_keys = [
                    'start_date', 'start_time', 'start', 'datetime', 'date',
                    'event_date', 'event_start', 'startDate', 'startDateTime'
                ]
            else:
                datetime_keys = [
                    'end_date', 'end_time', 'end', 'end_datetime',
                    'event_end', 'endDate', 'endDateTime'
                ]
            
            # Find datetime value
            datetime_value = None
            for key in datetime_keys:
                if key in data and data[key]:
                    datetime_value = data[key]
                    break
            
            if not datetime_value:
                return None
            
            # Handle different datetime formats
            if isinstance(datetime_value, (int, float)):
                # Unix timestamp
                return datetime.fromtimestamp(datetime_value, tz=self.oslo_tz)
            elif isinstance(datetime_value, str):
                # Try to parse string datetime
                return self.normalizer.normalize_datetime(datetime_value)
            elif isinstance(datetime_value, dict):
                # Handle object with date/time components
                if 'date' in datetime_value and 'time' in datetime_value:
                    date_str = f"{datetime_value['date']} {datetime_value['time']}"
                    return self.normalizer.normalize_datetime(date_str)
                elif 'year' in datetime_value and 'month' in datetime_value and 'day' in datetime_value:
                    year = datetime_value['year']
                    month = datetime_value['month']
                    day = datetime_value['day']
                    hour = datetime_value.get('hour', 0)
                    minute = datetime_value.get('minute', 0)
                    
                    return self.oslo_tz.localize(datetime(year, month, day, hour, minute))
            
            return None
            
        except Exception as e:
            log_warning(f"Failed to parse datetime: {e}")
            return None
    
    async def _parse_venue_info(self, data: dict) -> tuple[Optional[str], Optional[str]]:
        """Parse venue name and address from event data."""
        venue_name = None
        address = None
        
        try:
            # Extract venue name
            venue_keys = ['venue', 'location', 'place', 'venue_name', 'location_name']
            for key in venue_keys:
                if key in data and data[key]:
                    value = data[key]
                    if isinstance(value, str):
                        venue_name = value.strip()
                        break
                    elif isinstance(value, dict) and 'name' in value:
                        venue_name = str(value['name']).strip()
                        # Also extract address if available
                        if 'address' in value:
                            address = str(value['address']).strip()
                        break
            
            # Extract address if not already found
            if not address:
                address_keys = ['address', 'venue_address', 'location_address', 'street']
                for key in address_keys:
                    if key in data and data[key]:
                        address = str(data[key]).strip()
                        break
            
            return venue_name, address
            
        except Exception as e:
            log_warning(f"Failed to parse venue info: {e}")
            return None, None
    
    async def _parse_price_info(self, data: dict) -> Optional[str]:
        """Parse price information from event data."""
        try:
            price_keys = ['price', 'cost', 'ticket_price', 'amount', 'fee']
            
            for key in price_keys:
                if key in data and data[key] is not None:
                    price_value = data[key]
                    
                    if isinstance(price_value, (int, float)):
                        return f"kr {price_value}"
                    elif isinstance(price_value, str):
                        return self.normalizer.normalize_price(price_value)
                    elif isinstance(price_value, dict):
                        # Handle price object
                        if 'amount' in price_value:
                            amount = price_value['amount']
                            currency = price_value.get('currency', 'NOK')
                            return f"{currency} {amount}"
            
            # Check for free events
            if data.get('free', False) or data.get('is_free', False):
                return "Gratis"
            
            return None
            
        except Exception as e:
            log_warning(f"Failed to parse price info: {e}")
            return None
    
    async def _parse_image_url(self, data: dict, source_url: str) -> Optional[str]:
        """Parse image URL from event data."""
        try:
            image_keys = ['image', 'image_url', 'photo', 'thumbnail', 'picture']
            
            for key in image_keys:
                if key in data and data[key]:
                    image_value = data[key]
                    
                    if isinstance(image_value, str):
                        if image_value.startswith('http'):
                            return image_value
                        else:
                            return urljoin(source_url, image_value)
                    elif isinstance(image_value, dict) and 'url' in image_value:
                        url = image_value['url']
                        if url.startswith('http'):
                            return url
                        else:
                            return urljoin(source_url, url)
            
            return None
            
        except Exception as e:
            log_warning(f"Failed to parse image URL: {e}")
            return None
    
    async def _parse_category(self, data: dict) -> Optional[str]:
        """Parse category from event data."""
        try:
            category_keys = ['category', 'type', 'genre', 'tag', 'classification']
            
            for key in category_keys:
                if key in data and data[key]:
                    category_value = data[key]
                    
                    if isinstance(category_value, str):
                        # Normalize Norwegian categories
                        category_lower = category_value.lower()
                        if any(word in category_lower for word in ['music', 'konsert', 'concert']):
                            return 'Musikk'
                        elif any(word in category_lower for word in ['theater', 'teater', 'theatre']):
                            return 'Teater'
                        elif any(word in category_lower for word in ['family', 'familie', 'barn']):
                            return 'Familie'
                        elif any(word in category_lower for word in ['art', 'kunst', 'exhibition']):
                            return 'Utstilling'
                        else:
                            return category_value.title()
                    elif isinstance(category_value, list) and category_value:
                        return str(category_value[0]).title()
            
            return None
            
        except Exception as e:
            log_warning(f"Failed to parse category: {e}")
            return None


async def scrape_booking_widget_events(config: dict, client: HttpClient) -> List[Event]:
    """Main entry point for booking widget scraping."""
    try:
        base_url = config.get('base_url')
        if not base_url:
            log_error("No base_url provided for booking widget")
            return []
        
        endpoints = config.get('endpoints', [])
        widget_type = config.get('widget_type', 'custom')
        
        scraper = BookingWidgetScraper()
        events = await scraper.scrape_json_endpoints(
            client=client,
            base_url=base_url,
            endpoints=endpoints,
            widget_type=widget_type
        )
        
        log_info(f"Booking widget scraper completed: {len(events)} events found")
        return events
        
    except Exception as e:
        log_error(f"Booking widget scraping failed: {e}")
        return []


# For backwards compatibility
async def scrape_booking_widget(config: dict, client: HttpClient) -> List[Event]:
    """Alias for scrape_booking_widget_events."""
    return await scrape_booking_widget_events(config, client)
