"""
Meetup API scraper for event discovery.
Handles Meetup.com API v3 integration with proper authentication and rate limiting.
"""
import os
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import pytz
from models import Event
from utils import HttpClient
from logging_utils import log_info, log_warning, log_error


class MeetupAPIScraper:
    """Scraper for Meetup.com API v3."""
    
    def __init__(self, api_key: Optional[str] = None, location: str = "Moss,NO"):
        self.api_key = api_key or os.getenv('MEETUP_API_KEY')
        self.location = location
        self.base_url = "https://api.meetup.com"
        self.oslo_tz = pytz.timezone('Europe/Oslo')
        
    async def search_events(self, client: HttpClient, 
                          radius: float = 25.0,
                          days_ahead: int = 90) -> List[Event]:
        """Search for events near the specified location."""
        if not self.api_key:
            log_warning("Meetup API key not configured, skipping Meetup scraping")
            return []
            
        try:
            # Calculate date range
            start_date = datetime.now(self.oslo_tz)
            end_date = start_date + timedelta(days=days_ahead)
            
            # Meetup API endpoint for finding events
            url = f"{self.base_url}/find/upcoming_events"
            
            params = {
                'key': self.api_key,
                'text': 'kultur music teater utstilling konsert',  # Norwegian culture keywords
                'lat': '59.4389',  # Moss coordinates
                'lon': '10.6603',
                'radius': str(radius),
                'page': '200',  # Max events per request
                'fields': 'group_topics,featured_photo,event_hosts,plain_text_description'
            }
            
            headers = {
                'Accept': 'application/json',
                'User-Agent': 'MossKulturkalender/1.0'
            }
            
            log_info(f"Fetching Meetup events from API for {self.location}")
            response = await client.get(url, params=params, headers=headers)
            
            if response.status_code != 200:
                log_error(f"Meetup API returned status {response.status_code}")
                return []
                
            data = response.json()
            events_data = data.get('events', [])
            
            log_info(f"Found {len(events_data)} events from Meetup API")
            
            events = []
            for event_data in events_data:
                event = await self._parse_meetup_event(event_data)
                if event:
                    events.append(event)
                    
            return events
            
        except Exception as e:
            log_error(f"Failed to fetch Meetup events: {e}")
            return []
    
    async def _parse_meetup_event(self, event_data: Dict[str, Any]) -> Optional[Event]:
        """Parse a single Meetup event from API response."""
        try:
            # Extract basic info
            title = event_data.get('name', '').strip()
            if not title:
                return None
                
            description = event_data.get('description', '') or event_data.get('plain_text_description', '')
            event_url = event_data.get('link', '')
            
            # Parse datetime
            time_ms = event_data.get('time')
            if not time_ms:
                return None
                
            start_time = datetime.fromtimestamp(time_ms / 1000, tz=self.oslo_tz)
            
            # Duration (if available)
            duration_ms = event_data.get('duration')
            end_time = None
            if duration_ms:
                end_time = start_time + timedelta(milliseconds=duration_ms)
            
            # Venue information
            venue_data = event_data.get('venue', {})
            venue_name = venue_data.get('name', '')
            address = self._format_address(venue_data)
            
            # Group information
            group_data = event_data.get('group', {})
            group_name = group_data.get('name', '')
            
            # If no specific venue, use group name
            if not venue_name and group_name:
                venue_name = f"{group_name} (Meetup Group)"
            
            # Image URL
            image_url = None
            if 'featured_photo' in event_data:
                image_url = event_data['featured_photo'].get('photo_link')
            
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
                source="meetup",
                source_type="api",
                source_url=event_url,
                first_seen=now,
                last_seen=now
            )
            
            return event
            
        except Exception as e:
            log_warning(f"Failed to parse Meetup event: {e}")
            return None
    
    def _format_address(self, venue_data: Dict[str, Any]) -> Optional[str]:
        """Format venue address from Meetup venue data."""
        if not venue_data:
            return None
            
        parts = []
        
        # Address line 1
        if venue_data.get('address_1'):
            parts.append(venue_data['address_1'])
            
        # City and country
        city = venue_data.get('city', '')
        country = venue_data.get('localized_country_name', '')
        
        if city and country:
            parts.append(f"{city}, {country}")
        elif city:
            parts.append(city)
        elif country:
            parts.append(country)
            
        return ', '.join(parts) if parts else None


async def scrape_meetup_events(config: dict, client: HttpClient) -> List[Event]:
    """Main entry point for Meetup API scraping."""
    try:
        api_key = config.get('api_key') or os.getenv('MEETUP_API_KEY')
        location = config.get('location', 'Moss,NO')
        radius = config.get('radius', 25.0)
        days_ahead = config.get('days_ahead', 90)
        
        scraper = MeetupAPIScraper(api_key=api_key, location=location)
        events = await scraper.search_events(
            client=client,
            radius=radius,
            days_ahead=days_ahead
        )
        
        log_info(f"Meetup scraper completed: {len(events)} events found")
        return events
        
    except Exception as e:
        log_error(f"Meetup scraping failed: {e}")
        return []


# For backwards compatibility
async def scrape_meetup(config: dict, client: HttpClient) -> List[Event]:
    """Alias for scrape_meetup_events."""
    return await scrape_meetup_events(config, client)
