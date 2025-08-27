"""
Local news scraper for Norwegian cultural events.
Handles local newspapers with strict ToS respect and robots.txt compliance.
"""
import asyncio
import re
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
import pytz
from bs4 import BeautifulSoup
from models import Event
from utils import HttpClient
from normalize import EventNormalizer
from logging_utils import log_info, log_warning, log_error


class LocalNewsScraper:
    """Scraper for local Norwegian newspapers with ToS compliance."""
    
    def __init__(self):
        self.oslo_tz = pytz.timezone('Europe/Oslo')
        self.normalizer = EventNormalizer()
        self.user_agent = 'MossKulturkalender/1.0 (Culture Event Aggregator; +https://herimoss.no/contact)'
        
        # Robots.txt cache
        self.robots_cache = {}
        
        # Norwegian local news sources with event sections
        self.news_sources = {
            'moss_avis': {
                'base_url': 'https://www.moss-avis.no',
                'event_paths': ['/kultur/', '/arrangementer/', '/hva-skjer/'],
                'rate_limit': 2.0  # seconds between requests
            },
            'ostlendingen': {
                'base_url': 'https://www.ostlendingen.no',
                'event_paths': ['/kultur/', '/lokale-nyheter/', '/arrangementer/'],
                'rate_limit': 2.0
            },
            'fredrikstad_blad': {
                'base_url': 'https://www.f-b.no',
                'event_paths': ['/kultur/', '/nyheter/'],
                'rate_limit': 3.0
            },
            'sarpsborg_arbeiderblad': {
                'base_url': 'https://www.sa.no',
                'event_paths': ['/kultur/', '/lokalt/'],
                'rate_limit': 3.0
            }
        }
        
        # Common Norwegian cultural event keywords
        self.event_keywords = [
            'konsert', 'forestilling', 'utstilling', 'festival', 'show',
            'teater', 'standup', 'kino', 'kultur', 'arrangement',
            'opptreden', 'premiere', 'gallery', 'museum', 'bibliotek'
        ]
    
    async def check_robots_txt(self, client: HttpClient, base_url: str) -> bool:
        """Check if we're allowed to scrape according to robots.txt."""
        try:
            if base_url in self.robots_cache:
                return self.robots_cache[base_url]
            
            robots_url = urljoin(base_url, '/robots.txt')
            
            try:
                response = await client.get(robots_url, timeout=5)
                if response.status_code == 200:
                    rp = RobotFileParser()
                    rp.set_url(robots_url)
                    rp.read()
                    
                    # Check if our user agent is allowed
                    allowed = rp.can_fetch(self.user_agent, base_url)
                    self.robots_cache[base_url] = allowed
                    
                    if not allowed:
                        log_warning(f"Robots.txt disallows scraping {base_url}")
                    else:
                        log_info(f"Robots.txt allows scraping {base_url}")
                    
                    return allowed
                else:
                    # If robots.txt doesn't exist, assume we can scrape
                    self.robots_cache[base_url] = True
                    return True
                    
            except Exception as e:
                log_warning(f"Failed to check robots.txt for {base_url}: {e}")
                # Err on the side of caution
                self.robots_cache[base_url] = False
                return False
                
        except Exception as e:
            log_error(f"Error checking robots.txt for {base_url}: {e}")
            return False
    
    async def scrape_news_source(self, client: HttpClient, source_name: str,
                                source_config: Dict[str, Any]) -> List[Event]:
        """Scrape events from a single news source."""
        base_url = source_config['base_url']
        event_paths = source_config['event_paths']
        rate_limit = source_config['rate_limit']
        
        # Check robots.txt compliance
        if not await self.check_robots_txt(client, base_url):
            log_warning(f"Skipping {source_name} due to robots.txt restrictions")
            return []
        
        all_events = []
        
        for path in event_paths:
            try:
                url = urljoin(base_url, path)
                path_events = await self._scrape_event_section(client, url, source_name)
                all_events.extend(path_events)
                
                # Respect rate limiting
                await asyncio.sleep(rate_limit)
                
            except Exception as e:
                log_warning(f"Failed to scrape {url}: {e}")
                continue
        
        # Remove duplicates
        seen_ids = set()
        unique_events = []
        for event in all_events:
            if event.id not in seen_ids:
                seen_ids.add(event.id)
                unique_events.append(event)
        
        log_info(f"Local news {source_name} found {len(unique_events)} unique events")
        return unique_events
    
    async def _scrape_event_section(self, client: HttpClient, url: str, 
                                  source_name: str) -> List[Event]:
        """Scrape events from a news section page."""
        try:
            headers = {
                'User-Agent': self.user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'no,nb,en-US;q=0.7,en;q=0.3',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Cache-Control': 'max-age=0'
            }
            
            response = await client.get(url, headers=headers)
            
            if response.status_code != 200:
                log_warning(f"News site {url} returned status {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try multiple strategies to find event articles
            events = []
            
            # Strategy 1: Look for articles with event keywords
            article_events = await self._parse_article_links(soup, url, source_name)
            events.extend(article_events)
            
            # Strategy 2: Look for structured event listings
            listing_events = await self._parse_event_listings(soup, url, source_name)
            events.extend(listing_events)
            
            # Strategy 3: Parse calendar/agenda sections
            calendar_events = await self._parse_calendar_section(soup, url, source_name)
            events.extend(calendar_events)
            
            return events
            
        except Exception as e:
            log_error(f"Failed to scrape news section {url}: {e}")
            return []
    
    async def _parse_article_links(self, soup: BeautifulSoup, source_url: str,
                                 source_name: str) -> List[Event]:
        """Parse links to articles that might contain event information."""
        events = []
        
        try:
            # Find article links with event-related keywords
            article_links = soup.find_all('a', href=True)
            
            event_links = []
            for link in article_links:
                link_text = link.get_text(strip=True).lower()
                href = link.get('href', '')
                
                # Check if link text or URL contains event keywords
                if any(keyword in link_text for keyword in self.event_keywords):
                    event_links.append((link, link_text))
                elif any(keyword in href.lower() for keyword in self.event_keywords):
                    event_links.append((link, link_text))
            
            # Process event links (limit to avoid overwhelming the server)
            for link, link_text in event_links[:10]:
                try:
                    href = link.get('href')
                    if not href:
                        continue
                    
                    article_url = urljoin(source_url, href)
                    
                    # Skip external links
                    if not article_url.startswith(urlparse(source_url).scheme + '://' + urlparse(source_url).netloc):
                        continue
                    
                    # Extract date from link text or URL
                    event = await self._create_event_from_link(link_text, article_url, source_name)
                    if event:
                        events.append(event)
                        
                except Exception as e:
                    log_warning(f"Failed to process article link: {e}")
                    continue
            
            return events
            
        except Exception as e:
            log_warning(f"Failed to parse article links: {e}")
            return []
    
    async def _create_event_from_link(self, link_text: str, article_url: str,
                                    source_name: str) -> Optional[Event]:
        """Create an event from article link information."""
        try:
            # Extract title from link text
            title = link_text.strip()
            if len(title) < 5:
                return None
            
            # Try to extract date from link text
            date_patterns = [
                r'\d{1,2}\.\s*\w+',                    # "25. august"
                r'\d{1,2}\.\s*\w+\s*\d{4}',           # "25. august 2025"
                r'\w+\s+\d{1,2}',                     # "august 25"
                r'\d{4}-\d{2}-\d{2}',                 # "2025-08-25"
                r'\d{1,2}/\d{1,2}'                    # "25/8"
            ]
            
            date_text = None
            for pattern in date_patterns:
                match = re.search(pattern, link_text, re.IGNORECASE)
                if match:
                    date_text = match.group()
                    break
            
            # Try to extract date from URL
            if not date_text:
                url_date_patterns = [
                    r'/(\d{4})/(\d{2})/(\d{2})/',      # /2025/08/25/
                    r'(\d{4}-\d{2}-\d{2})',           # 2025-08-25
                ]
                for pattern in url_date_patterns:
                    match = re.search(pattern, article_url)
                    if match:
                        if '/' in pattern:
                            year, month, day = match.groups()
                            date_text = f"{year}-{month}-{day}"
                        else:
                            date_text = match.group(1)
                        break
            
            # If no date found, assume it's a current/upcoming event
            if not date_text:
                # Use current date as fallback
                start_time = datetime.now(self.oslo_tz).replace(hour=19, minute=0, second=0, microsecond=0)
            else:
                start_time = self.normalizer.normalize_datetime(date_text)
                if not start_time:
                    return None
            
            # Categorize based on keywords
            category = None
            title_lower = title.lower()
            if any(word in title_lower for word in ['konsert', 'band', 'musikk']):
                category = 'Musikk'
            elif any(word in title_lower for word in ['teater', 'forestilling', 'standup']):
                category = 'Teater'
            elif any(word in title_lower for word in ['utstilling', 'galleri', 'kunst']):
                category = 'Utstilling'
            elif any(word in title_lower for word in ['familie', 'barn']):
                category = 'Familie'
            
            # Generate event ID
            event_id = Event.generate_id(title, start_time, source_name)
            now = datetime.now(pytz.UTC)
            
            # Create Event object
            event = Event(
                id=event_id,
                title=title,
                url=article_url,
                category=category,
                start=start_time,
                source=f"news_{source_name}",
                source_type="html",
                source_url=article_url,
                first_seen=now,
                last_seen=now
            )
            
            return event
            
        except Exception as e:
            log_warning(f"Failed to create event from link: {e}")
            return None
    
    async def _parse_event_listings(self, soup: BeautifulSoup, source_url: str,
                                  source_name: str) -> List[Event]:
        """Parse structured event listings if they exist."""
        events = []
        
        try:
            # Look for common event listing structures
            listing_selectors = [
                '.event-list', '.events', '.calendar', '.agenda',
                '.kultur-kalender', '.arrangementer-liste',
                '[class*="event"]', '[class*="arrangement"]'
            ]
            
            for selector in listing_selectors:
                listings = soup.select(selector)
                if listings:
                    log_info(f"Found event listings with selector '{selector}'")
                    for listing in listings:
                        listing_events = await self._parse_listing_items(listing, source_url, source_name)
                        events.extend(listing_events)
                    break
            
            return events
            
        except Exception as e:
            log_warning(f"Failed to parse event listings: {e}")
            return []
    
    async def _parse_listing_items(self, listing, source_url: str, 
                                 source_name: str) -> List[Event]:
        """Parse individual items from an event listing."""
        events = []
        
        try:
            # Look for list items or event cards
            items = listing.find_all(['li', 'div', 'article'])
            
            for item in items[:15]:  # Limit to avoid too many
                try:
                    # Extract title
                    title_elem = item.find(['h1', 'h2', 'h3', 'h4', 'a'])
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    if len(title) < 5:
                        continue
                    
                    # Extract date
                    item_text = item.get_text()
                    date_text = None
                    
                    date_patterns = [
                        r'\d{1,2}\.\s*\w+\s*\d{4}',
                        r'\d{4}-\d{2}-\d{2}',
                        r'\d{1,2}/\d{1,2}/\d{4}'
                    ]
                    
                    for pattern in date_patterns:
                        match = re.search(pattern, item_text)
                        if match:
                            date_text = match.group()
                            break
                    
                    if not date_text:
                        continue
                    
                    start_time = self.normalizer.normalize_datetime(date_text)
                    if not start_time:
                        continue
                    
                    # Extract URL
                    link_elem = item.find('a', href=True)
                    event_url = source_url
                    if link_elem:
                        event_url = urljoin(source_url, link_elem['href'])
                    
                    # Generate event ID
                    event_id = Event.generate_id(title, start_time, source_name)
                    now = datetime.now(pytz.UTC)
                    
                    # Create Event object
                    event = Event(
                        id=event_id,
                        title=title,
                        url=event_url,
                        start=start_time,
                        source=f"news_{source_name}",
                        source_type="html",
                        source_url=source_url,
                        first_seen=now,
                        last_seen=now
                    )
                    
                    events.append(event)
                    
                except Exception as e:
                    log_warning(f"Failed to parse listing item: {e}")
                    continue
            
            return events
            
        except Exception as e:
            log_warning(f"Failed to parse listing items: {e}")
            return []
    
    async def _parse_calendar_section(self, soup: BeautifulSoup, source_url: str,
                                    source_name: str) -> List[Event]:
        """Parse calendar or agenda sections."""
        # Simplified implementation - could be expanded
        return []


async def scrape_local_news_events(config: dict, client: HttpClient) -> List[Event]:
    """Main entry point for local news scraping."""
    try:
        source_name = config.get('source_name', 'unknown')
        
        scraper = LocalNewsScraper()
        
        # Get the specific news source config
        if source_name in scraper.news_sources:
            source_config = scraper.news_sources[source_name]
            events = await scraper.scrape_news_source(client, source_name, source_config)
        else:
            # Custom source configuration
            base_url = config.get('base_url')
            event_paths = config.get('event_paths', ['/'])
            rate_limit = config.get('rate_limit', 2.0)
            
            if not base_url:
                log_error("No base_url provided for local news source")
                return []
            
            source_config = {
                'base_url': base_url,
                'event_paths': event_paths,
                'rate_limit': rate_limit
            }
            
            events = await scraper.scrape_news_source(client, source_name, source_config)
        
        log_info(f"Local news scraper completed: {len(events)} events found")
        return events
        
    except Exception as e:
        log_error(f"Local news scraping failed: {e}")
        return []


# For backwards compatibility
async def scrape_local_news(config: dict, client: HttpClient) -> List[Event]:
    """Alias for scrape_local_news_events."""
    return await scrape_local_news_events(config, client)
