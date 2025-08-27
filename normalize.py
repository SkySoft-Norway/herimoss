"""
Event normalization functions for dates, categories, venues, and other data.
"""
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
import pytz
from dateutil import parser as date_parser
from slugify import slugify
from models import Event
from utils import clean_html_text, extract_price_from_text, normalize_venue_name, categorize_event


class EventNormalizer:
    """Normalizes event data from various sources."""
    
    def __init__(self, tz_name: str = "Europe/Oslo", rules_config: Dict[str, Any] = None):
        self.tz = pytz.timezone(tz_name)
        self.rules = rules_config or {}
        self.category_keywords = self.rules.get("category_keywords", {})
        self.default_city = self.rules.get("default_city", "Moss")
    
    def normalize_datetime(self, dt_input: Any, is_end: bool = False) -> Optional[datetime]:
        """Normalize various datetime inputs to UTC datetime."""
        if not dt_input:
            return None
        
        try:
            # If already datetime
            if isinstance(dt_input, datetime):
                dt = dt_input
            # If string, try to parse
            elif isinstance(dt_input, str):
                dt = self._parse_datetime_string(dt_input)
            else:
                # Try conversion to string first
                dt = self._parse_datetime_string(str(dt_input))
            
            if not dt:
                return None
            
            # Ensure timezone awareness
            if dt.tzinfo is None:
                # Assume local timezone
                dt = self.tz.localize(dt)
            
            # Convert to UTC
            dt_utc = dt.astimezone(timezone.utc)
            
            return dt_utc
            
        except Exception:
            return None
    
    def _parse_datetime_string(self, dt_string: str) -> Optional[datetime]:
        """Parse various datetime string formats."""
        if not dt_string or not dt_string.strip():
            return None
        
        dt_string = dt_string.strip()
        
        # Common Norwegian date patterns
        norwegian_patterns = [
            r'(\d{1,2})\.(\d{1,2})\.(\d{4})\s+kl\.?\s*(\d{1,2})[:\.](\d{2})',  # 25.12.2025 kl. 19:30
            r'(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2})[:\.](\d{2})',          # 25.12.2025 19:30
            r'(\d{1,2})\.(\d{1,2})\.(\d{4})',                                   # 25.12.2025
            r'(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2})',               # 25/12/2025 19:30
        ]
        
        # Try Norwegian patterns first
        for pattern in norwegian_patterns:
            match = re.search(pattern, dt_string)
            if match:
                try:
                    if len(match.groups()) == 5:  # Date + time
                        day, month, year, hour, minute = match.groups()
                        return datetime(int(year), int(month), int(day), int(hour), int(minute))
                    elif len(match.groups()) == 3:  # Date only
                        day, month, year = match.groups()
                        return datetime(int(year), int(month), int(day))
                except (ValueError, TypeError):
                    continue
        
        # Try dateutil parser as fallback
        try:
            # Replace Norwegian month names
            norwegian_months = {
                'januar': 'january', 'februar': 'february', 'mars': 'march',
                'april': 'april', 'mai': 'may', 'juni': 'june',
                'juli': 'july', 'august': 'august', 'september': 'september',
                'oktober': 'october', 'november': 'november', 'desember': 'december'
            }
            
            dt_string_en = dt_string.lower()
            for no, en in norwegian_months.items():
                dt_string_en = dt_string_en.replace(no, en)
            
            return date_parser.parse(dt_string_en, fuzzy=True)
        except (ValueError, TypeError):
            pass
        
        return None
    
    def normalize_title(self, title: str) -> str:
        """Clean and normalize event title."""
        if not title:
            return "Uten tittel"
        
        # Clean HTML
        title = clean_html_text(title)
        
        # Remove excessive whitespace
        title = re.sub(r'\s+', ' ', title).strip()
        
        # Remove common prefixes that add no value
        prefixes_to_remove = [
            r'^event:\s*',
            r'^arrangement:\s*',
            r'^forestilling:\s*',
            r'^konsert:\s*',
        ]
        
        for prefix in prefixes_to_remove:
            title = re.sub(prefix, '', title, flags=re.IGNORECASE)
        
        # Capitalize properly
        title = title.strip()
        if title and not title[0].isupper():
            title = title[0].upper() + title[1:]
        
        return title[:200]  # Limit length
    
    def normalize_description(self, description: str) -> Optional[str]:
        """Clean and normalize event description."""
        if not description:
            return None
        
        # Clean HTML
        description = clean_html_text(description)
        
        # Remove excessive whitespace
        description = re.sub(r'\s+', ' ', description).strip()
        
        # Remove empty lines and normalize
        lines = [line.strip() for line in description.split('\n') if line.strip()]
        description = ' '.join(lines)
        
        if len(description) < 10:  # Too short to be useful
            return None
        
        return description[:1000]  # Limit length
    
    def normalize_venue(self, venue: str, address: str = None) -> tuple[Optional[str], Optional[str]]:
        """Normalize venue name and address."""
        if not venue:
            return None, address
        
        venue = clean_html_text(venue).strip()
        venue = normalize_venue_name(venue)
        
        # If venue contains address info, try to split
        if ',' in venue and not address:
            parts = venue.split(',', 1)
            venue = parts[0].strip()
            address = parts[1].strip()
        
        # Clean address
        if address:
            address = clean_html_text(address).strip()
            if len(address) < 5:  # Too short to be useful
                address = None
        
        return venue if venue else None, address
    
    def normalize_price(self, price_text: str = None, description: str = None) -> Optional[str]:
        """Extract and normalize price information."""
        # Try explicit price field first
        if price_text:
            price = extract_price_from_text(price_text)
            if price:
                return price
        
        # Try description
        if description:
            price = extract_price_from_text(description)
            if price:
                return price
        
        return None
    
    def categorize(self, title: str, description: str = None, venue: str = None) -> Optional[str]:
        """Categorize event based on content."""
        return categorize_event(title, description or "", self.category_keywords)
    
    def normalize_city(self, city: str = None, address: str = None, venue: str = None) -> str:
        """Normalize city name."""
        # Check explicit city first
        if city:
            city = clean_html_text(city).strip().title()
            if city:
                return city
        
        # Try to extract from address
        if address:
            # Look for Norwegian postal codes and cities
            postal_match = re.search(r'\b(\d{4})\s+([A-ZÆØÅ][a-zæøå\s]+)', address)
            if postal_match:
                return postal_match.group(2).strip()
            
            # Look for city names in address
            norwegian_cities = ['Oslo', 'Bergen', 'Trondheim', 'Stavanger', 'Moss', 'Fredrikstad', 'Sarpsborg']
            address_upper = address.upper()
            for city_name in norwegian_cities:
                if city_name.upper() in address_upper:
                    return city_name
        
        return self.default_city
    
    def normalize_event(self, event: Event) -> Event:
        """Apply full normalization to an event."""
        # Normalize title
        event.title = self.normalize_title(event.title)
        
        # Normalize description
        event.description = self.normalize_description(event.description)
        
        # Normalize venue and address
        venue, address = self.normalize_venue(event.venue, event.address)
        event.venue = venue
        event.address = address
        
        # Normalize city
        event.city = self.normalize_city(event.city, event.address, event.venue)
        
        # Normalize dates
        if event.start:
            event.start = self.normalize_datetime(event.start) or event.start
        if event.end:
            event.end = self.normalize_datetime(event.end, is_end=True)
        
        # Extract/normalize price
        event.price = self.normalize_price(event.price, event.description)
        
        # Categorize if not already set
        if not event.category:
            event.category = self.categorize(event.title, event.description, event.venue)
        
        # Regenerate ID with normalized data
        event.id = Event.generate_id(event.title, event.start, event.venue)
        
        return event


def normalize_events(events: List[Event], rules_config: Dict[str, Any] = None) -> List[Event]:
    """Normalize a list of events."""
    normalizer = EventNormalizer(rules_config=rules_config)
    
    normalized = []
    for event in events:
        try:
            normalized_event = normalizer.normalize_event(event)
            normalized.append(normalized_event)
        except Exception as e:
            # Log error but don't fail entire batch
            from logging_utils import log_warning
            log_warning(f"Failed to normalize event '{event.title}': {e}", source="normalizer")
            # Add original event as fallback
            normalized.append(event)
    
    return normalized


def should_archive_event(event: Event, archive_hours: int = 1) -> bool:
    """Determine if an event should be archived."""
    if event.status == "archived":
        return True
    
    now = datetime.now(timezone.utc)
    
    # Use end time if available, otherwise start time
    event_end = event.end or event.start
    
    # Archive if event ended more than specified hours ago
    if event_end < now - timedelta(hours=archive_hours):
        return True
    
    return False
