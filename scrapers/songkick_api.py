"""
Songkick API scraper for music events and concerts.
Handles Songkick API integration for Norwegian venues and artists.
"""
import os
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import pytz
from models import Event
from utils import HttpClient
from logging_utils import log_info, log_warning, log_error


class SongkickAPIScraper:
    """Scraper for Songkick API."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('SONGKICK_API_KEY')
        self.base_url = "https://api.songkick.com/api/3.0"
        self.oslo_tz = pytz.timezone('Europe/Oslo')
        
        # Major Norwegian cities and their Songkick location IDs
        self.norwegian_locations = {
            'Oslo': 'sk:28043',  # Songkick location ID for Oslo
            'Bergen': 'sk:28140',  # Bergen
            'Trondheim': 'sk:32252',  # Trondheim
            'Stavanger': 'sk:32546',  # Stavanger
            'Kristiansand': 'sk:32418',  # Kristiansand
        }
        
        # Search for Moss events by proximity to Oslo
        self.moss_coords = {
            'lat': 59.4389,
            'lng': 10.6603
        }
    
    async def search_events(self, client: HttpClient, days_ahead: int = 90) -> List[Event]:
        """Search for events in Norwegian cities."""
        if not self.api_key:
            log_warning("Songkick API key not configured, skipping Songkick scraping")
            return []
        
        all_events = []
        
        # Search by major Norwegian cities
        for city_name, location_id in self.norwegian_locations.items():
            try:
                city_events = await self._get_location_events(client, location_id, city_name, days_ahead)
                all_events.extend(city_events)
                
                # Rate limiting
                await asyncio.sleep(1.0)
                
            except Exception as e:
                log_warning(f"Failed to fetch Songkick events for {city_name}: {e}")
                continue
        
        # Search by coordinates (for Moss area)
        try:
            coord_events = await self._get_events_by_coordinates(client, days_ahead)
            all_events.extend(coord_events)
        except Exception as e:
            log_warning(f"Failed to fetch Songkick events by coordinates: {e}")
        
        # Remove duplicates
        seen_ids = set()
        unique_events = []
        for event in all_events:
            if event.id not in seen_ids:
                seen_ids.add(event.id)
                unique_events.append(event)
        
        log_info(f"Songkick scraper found {len(unique_events)} unique events")
        return unique_events
    
    async def _get_location_events(self, client: HttpClient, location_id: str, 
                                 city_name: str, days_ahead: int) -> List[Event]:
        """Get events for a specific Songkick location."""
        try:
            url = f"{self.base_url}/metro_areas/{location_id}/calendar.json"
            
            # Calculate date range
            start_date = datetime.now(self.oslo_tz)
            end_date = start_date + timedelta(days=days_ahead)
            
            params = {
                'apikey': self.api_key,
                'min_date': start_date.strftime('%Y-%m-%d'),
                'max_date': end_date.strftime('%Y-%m-%d'),
                'per_page': '50'  # Max events per page
            }
            
            headers = {
                'Accept': 'application/json',
                'User-Agent': 'MossKulturkalender/1.0'
            }
            
            log_info(f"Fetching Songkick events for {city_name}")
            response = await client.get(url, params=params, headers=headers)
            
            if response.status_code != 200:
                log_warning(f"Songkick API for {city_name} returned status {response.status_code}")
                return []
            
            data = response.json()
            results_page = data.get('resultsPage', {})
            events_data = results_page.get('results', {}).get('event', [])
            
            if not isinstance(events_data, list):
                events_data = [events_data] if events_data else []
            
            events = []
            for event_data in events_data:
                event = await self._parse_songkick_event(event_data)
                if event:
                    events.append(event)
            
            log_info(f"Found {len(events)} events in {city_name}")
            return events
            
        except Exception as e:
            log_error(f"Failed to get Songkick events for {city_name}: {e}")
            return []
    
    async def _get_events_by_coordinates(self, client: HttpClient, days_ahead: int) -> List[Event]:
        """Get events near Moss using coordinates."""
        try:
            url = f"{self.base_url}/events.json"
            
            # Calculate date range
            start_date = datetime.now(self.oslo_tz)
            end_date = start_date + timedelta(days=days_ahead)
            
            params = {
                'apikey': self.api_key,
                'location': f"geo:{self.moss_coords['lat']},{self.moss_coords['lng']}",
                'min_date': start_date.strftime('%Y-%m-%d'),
                'max_date': end_date.strftime('%Y-%m-%d'),
                'per_page': '50'
            }
            
            headers = {
                'Accept': 'application/json',
                'User-Agent': 'MossKulturkalender/1.0'
            }
            
            log_info(f"Fetching Songkick events near Moss coordinates")
            response = await client.get(url, params=params, headers=headers)
            
            if response.status_code != 200:
                log_warning(f"Songkick coordinate search returned status {response.status_code}")
                return []
            
            data = response.json()
            results_page = data.get('resultsPage', {})
            events_data = results_page.get('results', {}).get('event', [])
            
            if not isinstance(events_data, list):
                events_data = [events_data] if events_data else []
            
            events = []
            for event_data in events_data:
                event = await self._parse_songkick_event(event_data)
                if event:
                    events.append(event)
            
            return events
            
        except Exception as e:
            log_error(f"Failed to get Songkick events by coordinates: {e}")
            return []
    
    async def _parse_songkick_event(self, event_data: Dict[str, Any]) -> Optional[Event]:
        """Parse a single Songkick event from API response."""
        try:
            # Extract basic info
            display_name = event_data.get('displayName', '').strip()
            if not display_name:
                return None
            
            # Clean up the title (remove " at venue" part for cleaner titles)
            title = display_name
            if ' at ' in title:
                title = title.split(' at ')[0].strip()
            
            event_url = event_data.get('uri', '')
            event_id_songkick = event_data.get('id')
            
            # Parse datetime
            start_data = event_data.get('start', {})
            date_str = start_data.get('date')
            time_str = start_data.get('time')
            
            if not date_str:
                return None
            
            # Parse date and time
            if time_str:
                datetime_str = f"{date_str} {time_str}"
                start_time = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
            else:
                # If no time specified, assume evening start
                start_time = datetime.strptime(f"{date_str} 20:00:00", '%Y-%m-%d %H:%M:%S')
            
            # Convert to Oslo timezone
            start_time = self.oslo_tz.localize(start_time)
            
            # Venue information
            venue_data = event_data.get('venue', {})
            venue_name = venue_data.get('displayName', '')
            
            # Location data
            location_data = event_data.get('location', {})
            city = location_data.get('city', '')
            
            # Format address
            address = None
            if city:
                address = city
            
            # Performance/artist information
            performances = event_data.get('performance', [])
            if not isinstance(performances, list):
                performances = [performances] if performances else []
            
            # Extract artist names
            artists = []
            for perf in performances:
                artist_data = perf.get('artist', {})
                artist_name = artist_data.get('displayName', '')
                if artist_name:
                    artists.append(artist_name)
            
            # Create description from artists
            description = None
            if artists:
                description = f"Konsert med {', '.join(artists[:5])}"
                if len(artists) > 5:
                    description += f" og {len(artists)-5} flere artister"
            
            # Category is always music for Songkick
            category = "Musikk"
            
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
                address=address,
                category=category,
                start=start_time,
                source="songkick",
                source_type="api",
                source_url=event_url,
                first_seen=now,
                last_seen=now
            )
            
            return event
            
        except Exception as e:
            log_warning(f"Failed to parse Songkick event: {e}")
            return None


async def scrape_songkick_events(config: dict, client: HttpClient) -> List[Event]:
    """Main entry point for Songkick API scraping."""
    try:
        api_key = config.get('api_key') or os.getenv('SONGKICK_API_KEY')
        days_ahead = config.get('days_ahead', 90)
        
        scraper = SongkickAPIScraper(api_key=api_key)
        events = await scraper.search_events(
            client=client,
            days_ahead=days_ahead
        )
        
        log_info(f"Songkick scraper completed: {len(events)} events found")
        return events
        
    except Exception as e:
        log_error(f"Songkick scraping failed: {e}")
        return []


# For backwards compatibility
async def scrape_songkick(config: dict, client: HttpClient) -> List[Event]:
    """Alias for scrape_songkick_events."""
    return await scrape_songkick_events(config, client)
