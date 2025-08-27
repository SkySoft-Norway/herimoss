#!/usr/bin/env python3
"""
Enhanced Ticketmaster API Client for Moss Kulturkalender
Provides comprehensive event data with Norwegian locale support
"""

import asyncio
import aiohttp
import os
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from decimal import Decimal

from models import Event
from logging_utils import log_info, log_error, log_warning


@dataclass
class TicketmasterPricing:
    """Detailed pricing information from Ticketmaster"""
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    currency: str = "NOK"
    availability: Optional[str] = None
    on_sale_start: Optional[datetime] = None
    on_sale_end: Optional[datetime] = None
    presale_start: Optional[datetime] = None
    presale_end: Optional[datetime] = None
    tickets_available: Optional[bool] = None
    sold_out: bool = False


@dataclass
class TicketmasterVenue:
    """Enhanced venue information from Ticketmaster"""
    id: str
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: str = "NO"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    capacity: Optional[int] = None
    venue_type: Optional[str] = None
    accessibility: Optional[Dict[str, bool]] = None


@dataclass
class TicketmasterEvent:
    """Full Ticketmaster event data"""
    id: str
    name: str
    description: Optional[str] = None
    url: str = ""
    images: List[Dict[str, str]] = None
    start_date: Optional[datetime] = None
    start_time: Optional[str] = None
    end_date: Optional[datetime] = None
    venue: Optional[TicketmasterVenue] = None
    pricing: Optional[TicketmasterPricing] = None
    categories: List[str] = None
    genres: List[str] = None
    keywords: List[str] = None
    age_restriction: Optional[str] = None
    status: str = "onsale"
    source_id: str = ""
    last_updated: Optional[datetime] = None


class TicketmasterAPIClient:
    """Enhanced Ticketmaster API client with full Norwegian support"""
    
    def __init__(self, api_key: Optional[str] = None):
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        self.api_key = api_key or os.getenv('TICKETMASTER_API_KEY')
        self.base_url = "https://app.ticketmaster.com/discovery/v2"
        self.session: Optional[aiohttp.ClientSession] = None
        
        if not self.api_key:
            raise ValueError("Ticketmaster API key is required")
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make API request with error handling and rate limiting"""
        if not self.session:
            raise RuntimeError("Client must be used in async context manager")
        
        # Add API key and Norwegian locale
        params.update({
            'apikey': self.api_key,
            'locale': 'no-no'  # Critical for Norwegian events
        })
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 429:
                    # Rate limit exceeded
                    retry_after = int(response.headers.get('Retry-After', 5))
                    log_warning(f"Ticketmaster rate limit exceeded, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    # Retry once
                    async with self.session.get(url, params=params) as retry_response:
                        retry_response.raise_for_status()
                        return await retry_response.json()
                
                response.raise_for_status()
                return await response.json()
                
        except aiohttp.ClientError as e:
            log_error("ticketmaster_api", f"API request failed: {e}", url=url)
            raise
        except Exception as e:
            log_error("ticketmaster_api", f"Unexpected error: {e}", url=url)
            raise
    
    async def get_moss_events(self, radius_km: int = 20, max_events: int = 100) -> List[TicketmasterEvent]:
        """Get all events in and around Moss with comprehensive data"""
        log_info(f"Fetching Ticketmaster events for Moss (radius: {radius_km}km)")
        
        all_events = []
        
        # Search strategies for maximum coverage
        search_params = [
            # Direct city search
            {
                'city': 'Moss',
                'countryCode': 'NO',
                'size': max_events
            },
            # Geographic radius search
            {
                'geoPoint': '59.4369,10.6567',  # Moss coordinates
                'radius': str(radius_km),
                'unit': 'km',
                'size': max_events
            },
            # Venue-specific searches for known venues
            {
                'venueId': 'Z698xZb_Za7Ia',  # Verket Scene
                'size': max_events
            },
            {
                'venueId': 'Z698xZb_ZaAE-',  # Rabben - Verket Moss
                'size': max_events
            }
        ]
        
        seen_event_ids = set()
        
        for params in search_params:
            try:
                data = await self._make_request('/events.json', params)
                
                events = data.get('_embedded', {}).get('events', [])
                for event_data in events:
                    event_id = event_data.get('id')
                    if event_id and event_id not in seen_event_ids:
                        try:
                            event = await self._parse_event(event_data)
                            if event:
                                all_events.append(event)
                                seen_event_ids.add(event_id)
                        except Exception as e:
                            log_error("ticketmaster_api", f"Failed to parse event {event_id}: {e}")
                
                log_info(f"Found {len(events)} events with params: {params}")
                
            except Exception as e:
                log_error("ticketmaster_api", f"Search failed for params {params}: {e}")
        
        log_info(f"Total unique Ticketmaster events found: {len(all_events)}")
        return all_events
    
    async def _parse_event(self, event_data: Dict[str, Any]) -> Optional[TicketmasterEvent]:
        """Parse Ticketmaster event data into structured format"""
        try:
            # Basic event info
            event_id = event_data.get('id', '')
            name = event_data.get('name', '').strip()
            if not name:
                return None
            
            # Dates and times
            dates = event_data.get('dates', {})
            start_info = dates.get('start', {})
            
            start_date = None
            start_time = None
            if start_info.get('localDate'):
                start_date_str = start_info.get('localDate')
                start_time = start_info.get('localTime', '')
                
                if start_time:
                    start_date = datetime.fromisoformat(f"{start_date_str}T{start_time}")
                else:
                    start_date = datetime.fromisoformat(f"{start_date_str}T00:00:00")
            
            # Venue information
            venue = None
            venues = event_data.get('_embedded', {}).get('venues', [])
            if venues:
                venue_data = venues[0]
                venue = TicketmasterVenue(
                    id=venue_data.get('id', ''),
                    name=venue_data.get('name', ''),
                    address=venue_data.get('address', {}).get('line1'),
                    city=venue_data.get('city', {}).get('name'),
                    postal_code=venue_data.get('postalCode'),
                    country=venue_data.get('country', {}).get('countryCode', 'NO'),
                    latitude=self._safe_float(venue_data.get('location', {}).get('latitude')),
                    longitude=self._safe_float(venue_data.get('location', {}).get('longitude'))
                )
            
            # Pricing information
            pricing = await self._parse_pricing(event_data)
            
            # Categories and genres
            classifications = event_data.get('classifications', [])
            categories = []
            genres = []
            
            for classification in classifications:
                if classification.get('segment', {}).get('name'):
                    categories.append(classification['segment']['name'])
                if classification.get('genre', {}).get('name'):
                    genres.append(classification['genre']['name'])
            
            # Images
            images = event_data.get('images', [])
            
            # Create event
            event = TicketmasterEvent(
                id=event_id,
                name=name,
                description=self._extract_description(event_data),
                url=event_data.get('url', ''),
                images=images,
                start_date=start_date,
                start_time=start_time,
                venue=venue,
                pricing=pricing,
                categories=categories,
                genres=genres,
                status=event_data.get('dates', {}).get('status', {}).get('code', 'onsale'),
                source_id=event_id,
                last_updated=datetime.now()
            )
            
            return event
            
        except Exception as e:
            log_error("ticketmaster_api", f"Failed to parse event: {e}")
            return None
    
    async def _parse_pricing(self, event_data: Dict[str, Any]) -> Optional[TicketmasterPricing]:
        """Parse pricing information from event data"""
        try:
            pricing_data = event_data.get('priceRanges', [])
            sales_data = event_data.get('sales', {})
            
            if not pricing_data and not sales_data:
                return None
            
            pricing = TicketmasterPricing()
            
            # Price ranges
            if pricing_data:
                price_range = pricing_data[0]
                pricing.min_price = self._safe_decimal(price_range.get('min'))
                pricing.max_price = self._safe_decimal(price_range.get('max'))
                pricing.currency = price_range.get('currency', 'NOK')
            
            # Sales information
            if sales_data:
                public_sale = sales_data.get('public', {})
                presale = sales_data.get('presales', [])
                
                if public_sale.get('startDateTime'):
                    pricing.on_sale_start = datetime.fromisoformat(
                        public_sale['startDateTime'].replace('Z', '+00:00')
                    )
                if public_sale.get('endDateTime'):
                    pricing.on_sale_end = datetime.fromisoformat(
                        public_sale['endDateTime'].replace('Z', '+00:00')
                    )
                
                if presale:
                    first_presale = presale[0]
                    if first_presale.get('startDateTime'):
                        pricing.presale_start = datetime.fromisoformat(
                            first_presale['startDateTime'].replace('Z', '+00:00')
                        )
            
            # Availability status
            status = event_data.get('dates', {}).get('status', {}).get('code', '')
            pricing.sold_out = status == 'soldout'
            pricing.tickets_available = status in ['onsale', 'presale']
            
            return pricing
            
        except Exception as e:
            log_error("ticketmaster_api", f"Failed to parse pricing: {e}")
            return None
    
    def _extract_description(self, event_data: Dict[str, Any]) -> Optional[str]:
        """Extract description from various fields"""
        # Try different fields for description
        description = (
            event_data.get('info') or
            event_data.get('pleaseNote') or
            event_data.get('additionalInfo')
        )
        
        if description and len(description.strip()) > 10:
            return description.strip()[:1000]  # Limit length
        
        return None
    
    def _safe_float(self, value: Any) -> Optional[float]:
        """Safely convert value to float"""
        try:
            return float(value) if value is not None else None
        except (ValueError, TypeError):
            return None
    
    def _safe_decimal(self, value: Any) -> Optional[Decimal]:
        """Safely convert value to Decimal"""
        try:
            return Decimal(str(value)) if value is not None else None
        except (ValueError, TypeError):
            return None
    
    async def get_venue_details(self, venue_id: str) -> Optional[TicketmasterVenue]:
        """Get detailed venue information"""
        try:
            data = await self._make_request(f'/venues/{venue_id}.json', {})
            
            venue_data = data
            return TicketmasterVenue(
                id=venue_data.get('id', ''),
                name=venue_data.get('name', ''),
                address=venue_data.get('address', {}).get('line1'),
                city=venue_data.get('city', {}).get('name'),
                postal_code=venue_data.get('postalCode'),
                country=venue_data.get('country', {}).get('countryCode', 'NO'),
                latitude=self._safe_float(venue_data.get('location', {}).get('latitude')),
                longitude=self._safe_float(venue_data.get('location', {}).get('longitude')),
                capacity=venue_data.get('boxOfficeInfo', {}).get('capacity'),
                venue_type=venue_data.get('type'),
                accessibility=venue_data.get('accessibility')
            )
            
        except Exception as e:
            log_error("ticketmaster_api", f"Failed to get venue details for {venue_id}: {e}")
            return None


def convert_ticketmaster_to_event(tm_event: TicketmasterEvent) -> Event:
    """Convert TicketmasterEvent to standard Event model"""
    
    # Generate stable ID
    event_id = Event.generate_id(
        tm_event.name,
        tm_event.start_date or datetime.now(),
        tm_event.venue.name if tm_event.venue else None
    )
    
    # Format price information
    price = None
    if tm_event.pricing:
        if tm_event.pricing.sold_out:
            price = "Utsolgt"
        elif tm_event.pricing.min_price and tm_event.pricing.max_price:
            if tm_event.pricing.min_price == tm_event.pricing.max_price:
                price = f"kr {tm_event.pricing.min_price}"
            else:
                price = f"kr {tm_event.pricing.min_price}-{tm_event.pricing.max_price}"
        elif tm_event.pricing.min_price:
            price = f"fra kr {tm_event.pricing.min_price}"
    
    # Select best image
    image_url = None
    if tm_event.images:
        # Prefer larger images
        sorted_images = sorted(tm_event.images, key=lambda x: x.get('width', 0), reverse=True)
        image_url = sorted_images[0].get('url')
    
    # Primary category from first classification
    category = None
    if tm_event.categories:
        category = tm_event.categories[0]
    elif tm_event.genres:
        category = tm_event.genres[0]
    
    # Map Norwegian categories
    category_mapping = {
        'Musikk': 'Musikk',
        'Music': 'Musikk', 
        'Kultur & Teater': 'Teater',
        'Theater': 'Teater',
        'Sport': 'Sport',
        'Sports': 'Sport',
        'Andre': 'Annet'
    }
    category = category_mapping.get(category, category)
    
    event = Event(
        id=event_id,
        title=tm_event.name,
        description=tm_event.description,
        url=tm_event.url if tm_event.url else None,
        ticket_url=tm_event.url if tm_event.url else None,
        image_url=image_url,
        venue=tm_event.venue.name if tm_event.venue else None,
        address=tm_event.venue.address if tm_event.venue else None,
        city=tm_event.venue.city if tm_event.venue else "Moss",
        lat=tm_event.venue.latitude if tm_event.venue else None,
        lon=tm_event.venue.longitude if tm_event.venue else None,
        category=category,
        start=tm_event.start_date or datetime.now(),
        end=tm_event.end_date,
        price=price,
        source="Ticketmaster",
        source_type="api",
        source_url="https://www.ticketmaster.no",
        first_seen=datetime.now(),
        last_seen=datetime.now(),
        status="upcoming"
    )
    
    # Attach Ticketmaster-specific data
    event._ticketmaster_data = {
        'event_id': tm_event.id,
        'venue_id': tm_event.venue.id if tm_event.venue else None,
        'min_price': float(tm_event.pricing.min_price) if tm_event.pricing and tm_event.pricing.min_price else None,
        'max_price': float(tm_event.pricing.max_price) if tm_event.pricing and tm_event.pricing.max_price else None,
        'on_sale_start': tm_event.pricing.on_sale_start.isoformat() if tm_event.pricing and tm_event.pricing.on_sale_start else None,
        'on_sale_end': tm_event.pricing.on_sale_end.isoformat() if tm_event.pricing and tm_event.pricing.on_sale_end else None,
        'presale_start': tm_event.pricing.presale_start.isoformat() if tm_event.pricing and tm_event.pricing.presale_start else None,
        'presale_end': tm_event.pricing.presale_end.isoformat() if tm_event.pricing and tm_event.pricing.presale_end else None,
        'sold_out': tm_event.pricing.sold_out if tm_event.pricing else False,
        'tickets_available': tm_event.pricing.tickets_available if tm_event.pricing else None,
        'age_restriction': tm_event.age_restriction,
        'genres': tm_event.genres or [],
        'status': tm_event.status,
        'last_updated': tm_event.last_updated.isoformat() if tm_event.last_updated else None
    }
    
    return event


async def fetch_ticketmaster_events(radius_km: int = 20) -> List[Event]:
    """Main function to fetch and convert Ticketmaster events"""
    log_info("Starting Ticketmaster API integration for Moss events")
    
    try:
        async with TicketmasterAPIClient() as client:
            # Fetch Ticketmaster events
            tm_events = await client.get_moss_events(radius_km=radius_km)
            
            # Convert to standard Event format
            events = []
            for tm_event in tm_events:
                try:
                    event = convert_ticketmaster_to_event(tm_event)
                    events.append(event)
                except Exception as e:
                    log_error("ticketmaster_conversion", f"Failed to convert event {tm_event.name}: {e}")
            
            log_info(f"Successfully converted {len(events)} Ticketmaster events")
            return events
            
    except Exception as e:
        log_error("ticketmaster_integration", f"Failed to fetch Ticketmaster events: {e}")
        return []


if __name__ == "__main__":
    """Test the Ticketmaster integration"""
    async def test():
        from logging_utils import init_logging
        init_logging()
        
        events = await fetch_ticketmaster_events()
        print(f"Found {len(events)} events")
        for event in events[:5]:
            print(f"- {event.title} at {event.venue} on {event.start}")
            print(f"  Price: {event.price}")
            print(f"  URL: {event.ticket_url}")
            print()
    
    asyncio.run(test())