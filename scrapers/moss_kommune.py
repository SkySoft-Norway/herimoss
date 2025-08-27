"""
iCal/RSS scraper for Moss kommune and other calendar sources.
"""
import asyncio
from datetime import datetime, timezone
from typing import List, Optional
import pytz
from icalendar import Calendar, Event as ICalEvent
import feedparser
from models import Event
from utils import HttpClient, fetch_ical, fetch_feed
from logging_utils import log_info, log_error, log_warning


class ICalScraper:
    """Scraper for iCal calendar feeds."""
    
    def __init__(self, source_name: str, tz_name: str = "Europe/Oslo"):
        self.source_name = source_name
        self.tz = pytz.timezone(tz_name)
    
    async def scrape_ical_url(self, url: str, client: HttpClient) -> List[Event]:
        """Scrape events from an iCal URL."""
        events = []
        
        try:
            log_info(f"Fetching iCal from {url}", source=self.source_name, url=url)
            result = await fetch_ical(url, client)
            
            if result["error"]:
                log_error(self.source_name, f"Failed to fetch iCal: {result['error']}", url=url)
                return events
            
            for ical_event in result["events"]:
                try:
                    event = self._parse_ical_event(ical_event, url)
                    if event:
                        events.append(event)
                except Exception as e:
                    log_warning(f"Failed to parse iCal event: {e}", source=self.source_name, url=url)
            
            log_info(f"Parsed {len(events)} events from iCal", source=self.source_name, url=url)
            return events
            
        except Exception as e:
            log_error(self.source_name, f"Error scraping iCal: {e}", url=url)
            return events
    
    def _parse_ical_event(self, ical_event: ICalEvent, source_url: str) -> Optional[Event]:
        """Parse a single iCal event."""
        try:
            # Extract basic fields
            title = str(ical_event.get('summary', 'Uten tittel'))
            description = str(ical_event.get('description', '')) if ical_event.get('description') else None
            
            # Parse start time
            start_dt = ical_event.get('dtstart')
            if not start_dt:
                return None
            
            start = start_dt.dt
            if isinstance(start, datetime):
                if start.tzinfo is None:
                    start = self.tz.localize(start)
                start = start.astimezone(timezone.utc)
            else:
                # Date only - assume start of day in local timezone
                start = self.tz.localize(datetime.combine(start, datetime.min.time()))
                start = start.astimezone(timezone.utc)
            
            # Parse end time
            end = None
            end_dt = ical_event.get('dtend')
            if end_dt:
                end = end_dt.dt
                if isinstance(end, datetime):
                    if end.tzinfo is None:
                        end = self.tz.localize(end)
                    end = end.astimezone(timezone.utc)
                else:
                    # Date only - assume end of day
                    end = self.tz.localize(datetime.combine(end, datetime.max.time().replace(microsecond=0)))
                    end = end.astimezone(timezone.utc)
            
            # Extract location
            location = str(ical_event.get('location', '')) if ical_event.get('location') else None
            venue = None
            address = None
            
            if location:
                # Try to split venue and address
                parts = location.split(',', 1)
                venue = parts[0].strip()
                if len(parts) > 1:
                    address = parts[1].strip()
            
            # Extract URL
            event_url = str(ical_event.get('url', '')) if ical_event.get('url') else None
            
            # Extract categories (Moss kommune often uses this)
            categories = ical_event.get('categories')
            category = None
            if categories:
                if isinstance(categories, list):
                    category = str(categories[0]) if categories else None
                else:
                    category = str(categories)
            
            # Generate ID and timestamps
            now = datetime.now(timezone.utc)
            event_id = Event.generate_id(title, start, venue)
            
            # Create event
            event = Event(
                id=event_id,
                title=title,
                description=description,
                url=event_url,
                venue=venue,
                address=address,
                category=category,
                start=start,
                end=end,
                source=self.source_name,
                source_type="ical",
                source_url=source_url,
                first_seen=now,
                last_seen=now
            )
            
            return event
            
        except Exception as e:
            log_warning(f"Failed to parse iCal event: {e}", source=self.source_name)
            return None


class RSSEventScraper:
    """Scraper for RSS feeds with event information."""
    
    def __init__(self, source_name: str, tz_name: str = "Europe/Oslo"):
        self.source_name = source_name
        self.tz = pytz.timezone(tz_name)
    
    async def scrape_rss_url(self, url: str, client: HttpClient) -> List[Event]:
        """Scrape events from an RSS feed."""
        events = []
        
        try:
            log_info(f"Fetching RSS from {url}", source=self.source_name, url=url)
            result = await fetch_feed(url, client)
            
            if result["error"]:
                log_error(self.source_name, f"Failed to fetch RSS: {result['error']}", url=url)
                return events
            
            for entry in result["entries"]:
                try:
                    event = self._parse_rss_entry(entry, url)
                    if event:
                        events.append(event)
                except Exception as e:
                    log_warning(f"Failed to parse RSS entry: {e}", source=self.source_name, url=url)
            
            log_info(f"Parsed {len(events)} events from RSS", source=self.source_name, url=url)
            return events
            
        except Exception as e:
            log_error(self.source_name, f"Error scraping RSS: {e}", url=url)
            return events
    
    def _parse_rss_entry(self, entry, source_url: str) -> Optional[Event]:
        """Parse a single RSS entry as an event."""
        try:
            title = entry.get('title', 'Uten tittel')
            description = entry.get('summary', '') or entry.get('description', '')
            link = entry.get('link', '')
            
            # Try to extract date from entry
            published = entry.get('published_parsed') or entry.get('updated_parsed')
            if published:
                start = datetime(*published[:6], tzinfo=timezone.utc)
            else:
                # Try to parse from title or description
                import re
                from dateutil import parser as date_parser
                
                text = f"{title} {description}"
                date_patterns = [
                    r'(\d{1,2})\.(\d{1,2})\.(\d{4})',  # DD.MM.YYYY
                    r'(\d{4})-(\d{1,2})-(\d{1,2})',   # YYYY-MM-DD
                ]
                
                start = None
                for pattern in date_patterns:
                    match = re.search(pattern, text)
                    if match:
                        try:
                            if pattern.startswith(r'(\d{4})'):
                                year, month, day = match.groups()
                            else:
                                day, month, year = match.groups()
                            start = datetime(int(year), int(month), int(day), tzinfo=timezone.utc)
                            break
                        except ValueError:
                            continue
                
                if not start:
                    # Fallback to current time - not ideal but prevents loss
                    start = datetime.now(timezone.utc)
            
            # Try to extract venue from description
            venue = None
            if description:
                # Look for common venue patterns
                venue_patterns = [
                    r'(?:på|i|hos)\s+([A-ZÆØÅ][a-zæøå\s]+(?:scene|kulturhus|teater|kino))',
                    r'(Verket\s+Scene|Moss\s+Kulturhus|Moss\s+Teater)',
                ]
                
                for pattern in venue_patterns:
                    match = re.search(pattern, description, re.IGNORECASE)
                    if match:
                        venue = match.group(1).strip()
                        break
            
            # Generate ID and timestamps
            now = datetime.now(timezone.utc)
            event_id = Event.generate_id(title, start, venue)
            
            # Create event
            event = Event(
                id=event_id,
                title=title,
                description=description,
                url=link if link else None,
                venue=venue,
                start=start,
                source=self.source_name,
                source_type="rss",
                source_url=source_url,
                first_seen=now,
                last_seen=now
            )
            
            return event
            
        except Exception as e:
            log_warning(f"Failed to parse RSS entry: {e}", source=self.source_name)
            return None


async def scrape_moss_kommune(config: dict, client: HttpClient) -> List[Event]:
    """Scrape events from Moss kommune."""
    scraper = ICalScraper("Moss kommune")
    rss_scraper = RSSEventScraper("Moss kommune")
    events = []
    
    # Process iCal URLs
    for url in config.get("ical_urls", []):
        events.extend(await scraper.scrape_ical_url(url, client))
    
    # Process RSS URLs
    for url in config.get("rss_urls", []):
        events.extend(await rss_scraper.scrape_rss_url(url, client))
    
    return events
