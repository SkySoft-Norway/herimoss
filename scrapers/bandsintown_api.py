"""
Bandsintown API scraper for music events and concerts.
Handles Bandsintown Events API integration for Norwegian artists and venues.
"""
import os
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import pytz
from models import Event
from utils import HttpClient
from logging_utils import log_info, log_warning, log_error


class BandsintownAPIScraper:
    """Scraper for Bandsintown Events API."""
    
    def __init__(self, app_id: Optional[str] = None):
        self.app_id = app_id or os.getenv('BANDSINTOWN_APP_ID', 'MossKulturkalender')
        self.base_url = "https://rest.bandsintown.com"
        self.oslo_tz = pytz.timezone('Europe/Oslo')
        
        # Norwegian and international artists popular in Norway
        self.norwegian_artists = [
            'aurora', 'kygo', 'alan-walker', 'sigrid', 'madcon', 'karpe',
            'postgirobygget', 'dumdum-boys', 'kaizers-orchestra', 'motorpsycho',
            'turboneger', 'kvelertak', 'satyricon', 'mayhem', 'dimmu-borgir'
        ]
        
        # Major venues in and around Moss/Oslo area
        self.norwegian_venues = [
            'oslo spektrum', 'telenor arena', 'sentrum scene', 'rockefeller',
            'parkteatret', 'gamla', 'vulkan arena', 'salt', 'operaen oslo',
            'konserthuset oslo', 'moss kulturhus', 'verket kulturhus'
        ]
    
    async def search_events(self, client: HttpClient, days_ahead: int = 90) -> List[Event]:
        """Search for events by Norwegian artists and venues."""
        all_events = []
        
        # Search by artists
        artist_events = await self._search_by_artists(client, days_ahead)
        all_events.extend(artist_events)
        
        # Search by location/venues
        location_events = await self._search_by_location(client, days_ahead)
        all_events.extend(location_events)
        
        # Remove duplicates based on event ID
        seen_ids = set()
        unique_events = []
        for event in all_events:
            if event.id not in seen_ids:
                seen_ids.add(event.id)
                unique_events.append(event)
        
        log_info(f"Bandsintown scraper found {len(unique_events)} unique events")
        return unique_events
    
    async def _search_by_artists(self, client: HttpClient, days_ahead: int) -> List[Event]:
        """Search for events by specific Norwegian artists."""
        events = []
        
        for artist in self.norwegian_artists:
            try:
                artist_events = await self._get_artist_events(client, artist, days_ahead)
                events.extend(artist_events)
                
                # Rate limiting - be nice to the API
                await asyncio.sleep(0.5)
                
            except Exception as e:
                log_warning(f"Failed to fetch events for artist {artist}: {e}")
                continue
        
        return events
    
    async def _search_by_location(self, client: HttpClient, days_ahead: int) -> List[Event]:
        """Search for events by location (Norway/Oslo area)."""
        try:
            # Search for events near Oslo/Moss area
            url = f"{self.base_url}/events/search"
            
            # Calculate date range
            start_date = datetime.now(self.oslo_tz).strftime('%Y-%m-%d')
            end_date = (datetime.now(self.oslo_tz) + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
            
            params = {
                'app_id': self.app_id,
                'location': 'Oslo,Norway',
                'radius': '50',  # 50km radius from Oslo
                'date': f"{start_date},{end_date}",
                'per_page': '100'
            }
            
            headers = {
                'Accept': 'application/json',
                'User-Agent': 'MossKulturkalender/1.0'
            }
            
            log_info(f"Fetching Bandsintown events by location")
            response = await client.get(url, params=params, headers=headers)
            
            if response.status_code != 200:
                log_warning(f"Bandsintown location search returned status {response.status_code}")
                return []
            
            events_data = response.json()
            if not isinstance(events_data, list):
                return []
            
            events = []
            for event_data in events_data:
                event = await self._parse_bandsintown_event(event_data)
                if event:
                    events.append(event)
            
            return events
            
        except Exception as e:
            log_error(f"Failed to search Bandsintown by location: {e}")
            return []
    
    async def _get_artist_events(self, client: HttpClient, artist: str, days_ahead: int) -> List[Event]:
        """Get events for a specific artist."""
        try:
            url = f"{self.base_url}/artists/{artist}/events"
            
            # Calculate date range
            start_date = datetime.now(self.oslo_tz).strftime('%Y-%m-%d')
            end_date = (datetime.now(self.oslo_tz) + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
            
            params = {
                'app_id': self.app_id,
                'date': f"{start_date},{end_date}"
            }
            
            headers = {
                'Accept': 'application/json',
                'User-Agent': 'MossKulturkalender/1.0'
            }
            
            response = await client.get(url, params=params, headers=headers)
            
            if response.status_code == 404:
                # Artist not found, not an error
                return []
            elif response.status_code != 200:
                log_warning(f"Bandsintown artist search for {artist} returned status {response.status_code}")
                return []
            
            events_data = response.json()
            if not isinstance(events_data, list):
                return []
            
            events = []
            for event_data in events_data:
                # Only include events in Norway or nearby
                if self._is_relevant_location(event_data):
                    event = await self._parse_bandsintown_event(event_data)
                    if event:
                        events.append(event)
            
            return events
            
        except Exception as e:
            log_warning(f"Failed to get events for artist {artist}: {e}")
            return []
    
    def _is_relevant_location(self, event_data: Dict[str, Any]) -> bool:
        """Check if event is in Norway or relevant area."""
        venue = event_data.get('venue', {})
        country = venue.get('country', '').lower()
        city = venue.get('city', '').lower()
        
        # Include events in Norway
        if country in ['norway', 'no']:
            return True
            
        # Include events in major Nordic cities (some Norwegian artists tour there)
        relevant_cities = ['stockholm', 'copenhagen', 'helsinki', 'gothenburg', 'malmö']
        if city in relevant_cities:
            return True
            
        return False
    
    async def _parse_bandsintown_event(self, event_data: Dict[str, Any]) -> Optional[Event]:
        """Parse a single Bandsintown event from API response."""
        try:
            # Extract basic info
            title = event_data.get('title', '').strip()
            if not title:
                # Fallback to artist lineup
                lineup = event_data.get('lineup', [])
                if lineup:
                    title = ' + '.join(lineup[:3])  # Max 3 artists in title
                    if len(lineup) > 3:
                        title += f" + {len(lineup)-3} flere"
                else:
                    return None
            
            description = event_data.get('description', '')
            event_url = event_data.get('url', '')
            
            # Parse datetime
            datetime_str = event_data.get('datetime')
            if not datetime_str:
                return None
            
            # Bandsintown uses ISO format
            start_time = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
            # Convert to Oslo timezone
            start_time = start_time.astimezone(self.oslo_tz)
            
            # Venue information
            venue_data = event_data.get('venue', {})
            venue_name = venue_data.get('name', '')
            venue_city = venue_data.get('city', '')
            venue_country = venue_data.get('country', '')
            
            # Format address
            address_parts = []
            if venue_data.get('street_address'):
                address_parts.append(venue_data['street_address'])
            if venue_city:
                address_parts.append(venue_city)
            if venue_country:
                address_parts.append(venue_country)
            
            address = ', '.join(address_parts) if address_parts else None
            
            # Category - always music for Bandsintown
            category = "Musikk"
            
            # Artist info for description
            lineup = event_data.get('lineup', [])
            if lineup and not description:
                description = f"Konsert med {', '.join(lineup)}"
            
            # Generate event ID
            event_id = Event.generate_id(title, start_time, venue_name)
            now = datetime.now(pytz.UTC)
            
            # Create Event object
            event = Event(
                id=event_id,
                title=title,
                description=description[:1000] if description else None,
                url=event_url,
                venue=venue_name,
                address=address,
                category=category,
                start=start_time,
                source="bandsintown",
                source_type="api",
                source_url=event_url,
                first_seen=now,
                last_seen=now
            )
            
            return event
            
        except Exception as e:
            log_warning(f"Failed to parse Bandsintown event: {e}")
            return None


async def scrape_bandsintown_events(config: dict, client: HttpClient) -> List[Event]:
    """Main entry point for Bandsintown API scraping."""
    try:
        app_id = config.get('app_id') or os.getenv('BANDSINTOWN_APP_ID')
        days_ahead = config.get('days_ahead', 90)
        
        scraper = BandsintownAPIScraper(app_id=app_id)
        events = await scraper.search_events(
            client=client,
            days_ahead=days_ahead
        )
        
        log_info(f"Bandsintown scraper completed: {len(events)} events found")
        return events
        
    except Exception as e:
        log_error(f"Bandsintown scraping failed: {e}")
        return []


# For backwards compatibility
async def scrape_bandsintown(config: dict, client: HttpClient) -> List[Event]:
    """Alias for scrape_bandsintown_events."""
    return await scrape_bandsintown_events(config, client)
