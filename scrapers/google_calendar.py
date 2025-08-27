"""
Google Calendar scraper for public calendars.
"""
import asyncio
from datetime import datetime, timezone
from typing import List, Optional
import re
from urllib.parse import urlparse, parse_qs
from models import Event
from utils import HttpClient, fetch_ical
from logging_utils import log_info, log_error, log_warning
from scrapers.moss_kommune import ICalScraper


class GoogleCalendarScraper(ICalScraper):
    """Scraper for Google Calendar public calendars."""
    
    def __init__(self, source_name: str = "Google Calendar", tz_name: str = "Europe/Oslo"):
        super().__init__(source_name, tz_name)
    
    def _convert_google_calendar_url(self, url: str) -> Optional[str]:
        """Convert Google Calendar URL to iCal export URL."""
        try:
            # Handle different Google Calendar URL formats
            
            # Format 1: https://calendar.google.com/calendar/embed?src=CALENDAR_ID
            if "calendar.google.com/calendar/embed" in url:
                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                calendar_id = params.get('src', [None])[0]
                if calendar_id:
                    return f"https://calendar.google.com/calendar/ical/{calendar_id}/public/basic.ics"
            
            # Format 2: https://calendar.google.com/calendar/u/0?cid=CALENDAR_ID
            elif "calendar.google.com/calendar/u/" in url and "cid=" in url:
                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                calendar_id = params.get('cid', [None])[0]
                if calendar_id:
                    return f"https://calendar.google.com/calendar/ical/{calendar_id}/public/basic.ics"
            
            # Format 3: Direct iCal URL
            elif url.endswith('.ics') or '/ical/' in url:
                return url
            
            # Format 4: Google Calendar ID directly
            elif '@' in url and not url.startswith('http'):
                # Assume it's a calendar ID like "example@gmail.com" or "calendar_id@group.calendar.google.com"
                return f"https://calendar.google.com/calendar/ical/{url}/public/basic.ics"
            
            log_warning(f"Unknown Google Calendar URL format: {url}", source=self.source_name)
            return None
            
        except Exception as e:
            log_warning(f"Failed to convert Google Calendar URL: {e}", source=self.source_name)
            return None
    
    async def scrape_google_calendar_url(self, url: str, client: HttpClient) -> List[Event]:
        """Scrape events from a Google Calendar URL."""
        ical_url = self._convert_google_calendar_url(url)
        if not ical_url:
            log_error(self.source_name, f"Could not convert URL to iCal format: {url}", url=url)
            return []
        
        log_info(f"Converted Google Calendar URL to iCal: {ical_url}", source=self.source_name)
        return await self.scrape_ical_url(ical_url, client)
    
    def _parse_ical_event(self, ical_event, source_url: str) -> Optional[Event]:
        """Parse Google Calendar iCal event with Google-specific handling."""
        event = super()._parse_ical_event(ical_event, source_url)
        if not event:
            return None
        
        # Google Calendar specific enhancements
        
        # Extract location more intelligently
        location = str(ical_event.get('location', '')) if ical_event.get('location') else None
        if location:
            # Google often includes full addresses
            venue, address = self._parse_google_location(location)
            if venue:
                event.venue = venue
            if address:
                event.address = address
        
        # Extract attendees count if available
        attendees = ical_event.get('attendee')
        if attendees:
            # This could be used for popularity scoring later
            pass
        
        # Google Calendar often has better descriptions
        description = str(ical_event.get('description', '')) if ical_event.get('description') else None
        if description:
            # Clean up Google Calendar specific formatting
            description = self._clean_google_description(description)
            if description:
                event.description = description
        
        return event
    
    def _parse_google_location(self, location: str) -> tuple[Optional[str], Optional[str]]:
        """Parse Google Calendar location field."""
        if not location:
            return None, None
        
        # Google often formats as "Venue Name, Street Address, City"
        parts = [part.strip() for part in location.split(',')]
        
        if len(parts) == 1:
            # Just venue name
            return parts[0], None
        elif len(parts) >= 2:
            # First part is likely venue, rest is address
            venue = parts[0]
            address = ', '.join(parts[1:])
            
            # Check if first part looks like a venue name (not just a street)
            if any(word in venue.lower() for word in ['scene', 'kulturhus', 'teater', 'kino', 'galleri', 'bibliotek']):
                return venue, address
            elif not any(char.isdigit() for char in venue):  # No numbers, likely a venue name
                return venue, address
            else:
                # First part might be street address
                return None, location
        
        return None, location
    
    def _clean_google_description(self, description: str) -> Optional[str]:
        """Clean Google Calendar description."""
        if not description:
            return None
        
        # Remove common Google Calendar artifacts
        description = re.sub(r'View your event at.*?\.', '', description)
        description = re.sub(r'https://calendar\.google\.com/.*?\s*', '', description)
        
        # Remove excessive newlines
        description = re.sub(r'\n\s*\n', '\n', description)
        description = description.strip()
        
        if len(description) < 10:
            return None
        
        return description


async def scrape_google_calendar(config: dict, client: HttpClient) -> List[Event]:
    """Scrape events from Google Calendar sources."""
    scraper = GoogleCalendarScraper("Google Calendar")
    events = []
    
    # Process iCal URLs (including Google Calendar URLs)
    for url in config.get("ical_urls", []):
        if "google" in url.lower() or "calendar" in url.lower():
            events.extend(await scraper.scrape_google_calendar_url(url, client))
        else:
            # Regular iCal URL
            events.extend(await scraper.scrape_ical_url(url, client))
    
    # Process direct Google Calendar IDs
    for calendar_id in config.get("calendar_ids", []):
        ical_url = f"https://calendar.google.com/calendar/ical/{calendar_id}/public/basic.ics"
        events.extend(await scraper.scrape_ical_url(ical_url, client))
    
    return events


# Example usage patterns for Google Calendar:
# 
# 1. Public calendar embed URL:
#    https://calendar.google.com/calendar/embed?src=example%40gmail.com
#
# 2. Direct calendar ID:
#    example@gmail.com
#    or
#    calendar_id@group.calendar.google.com
#
# 3. Direct iCal URL:
#    https://calendar.google.com/calendar/ical/example%40gmail.com/public/basic.ics
