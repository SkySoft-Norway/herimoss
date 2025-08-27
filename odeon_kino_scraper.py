#!/usr/bin/env python3
"""
Odeon Kino Events Scraper
Extracts movie showtimes from https://www.odeonkino.no/moss/
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from pathlib import Path
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
import re
from playwright.async_api import async_playwright

from logging_utils import init_logging, log_info, log_error, log_warning
from models import Event
from uuid import uuid4


class OdeonKinoScraper:
    """Scraper for Odeon Kino movie showtimes"""
    
    def __init__(self):
        self.base_url = "https://www.odeonkino.no"
        self.moss_url = f"{self.base_url}/moss/"
        # Focus on premieres only as requested
        self.premieres_only = True
        # Try RSS feeds first (often less restricted)
        self.rss_feeds = [
            f"{self.base_url}/rss/",
            f"{self.base_url}/feed/",
            f"{self.base_url}/moss/rss/",
            f"{self.base_url}/moss/feed/"
        ]
        self.api_endpoints = [
            f"{self.base_url}/api/showtimes",
            f"{self.base_url}/api/cinema/moss",
            f"{self.base_url}/moss/api/showtimes"
        ]
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        # Use more realistic browser headers to avoid 403
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'no-NO,no;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def fetch_with_playwright(self) -> Optional[str]:
        """Use Playwright to bypass 403 restrictions and fetch movie data"""
        try:
            log_info(f"Using Playwright to fetch cinema data from: {self.moss_url}")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='no-NO'
                )
                page = await context.new_page()
                
                # Try different URLs for movie listings
                urls_to_try = [
                    self.moss_url,
                    f"{self.base_url}/moss/program/",
                    f"{self.base_url}/moss/filmer/",
                    f"{self.base_url}/kino/moss/",
                    f"{self.base_url}/moss/premierer/",
                    f"{self.base_url}/premierer/"
                ]
                
                for url in urls_to_try:
                    try:
                        log_info(f"Playwright: Trying {url}")
                        await page.goto(url, wait_until='networkidle', timeout=30000)
                        
                        # Wait for movie content to load
                        try:
                            await page.wait_for_selector('.movie, .film, .showtime, .screening', timeout=10000)
                            log_info(f"Movie content loaded from: {url}")
                        except:
                            log_info(f"Using generic wait for: {url}")
                            await page.wait_for_timeout(3000)
                        
                        # Get the page content
                        html_content = await page.content()
                        
                        # Check if we got meaningful content (not just a redirect page)
                        if len(html_content) > 5000:  # Reasonable minimum size
                            await browser.close()
                            log_info(f"Successfully retrieved cinema page ({len(html_content)} chars)")
                            return html_content
                        
                    except Exception as e:
                        log_warning("playwright_url", f"Failed to fetch {url}: {e}")
                        continue
                
                await browser.close()
                log_error("playwright_all", "All URLs failed with Playwright")
                return None
                
        except Exception as e:
            log_error("playwright_cinema", f"Playwright failed: {e}")
            return None
    
    async def try_rss_feeds(self) -> Optional[List[Dict[str, Any]]]:
        """Try to fetch movie data from RSS feeds (often less restricted)"""
        for rss_url in self.rss_feeds:
            try:
                log_info(f"Trying RSS feed: {rss_url}")
                
                async with self.session.get(rss_url) as response:
                    if response.status == 200:
                        rss_content = await response.text()
                        
                        # Parse RSS/XML content
                        try:
                            soup = BeautifulSoup(rss_content, 'xml')
                            items = soup.find_all('item')
                            
                            if not items:
                                # Try HTML parsing if XML parsing fails
                                soup = BeautifulSoup(rss_content, 'html.parser')
                                items = soup.find_all('item')
                            
                            if items:
                                log_info(f"Found {len(items)} RSS items from {rss_url}")
                                return self.parse_rss_items(items)
                                
                        except Exception as e:
                            log_warning("rss_parse", f"Failed to parse RSS from {rss_url}: {e}")
                            continue
                    
            except Exception as e:
                log_warning("rss_request", f"RSS request failed for {rss_url}: {e}")
                continue
        
        return None
    
    def parse_rss_items(self, items) -> List[Dict[str, Any]]:
        """Parse RSS items into movie events"""
        events = []
        
        for item in items:
            try:
                # Extract title
                title_elem = item.find('title')
                title = title_elem.get_text(strip=True) if title_elem else ""
                
                # Extract description
                desc_elem = item.find('description') or item.find('content:encoded')
                description = ""
                if desc_elem:
                    description = desc_elem.get_text(strip=True)
                    # Clean HTML tags if present
                    description = BeautifulSoup(description, 'html.parser').get_text()
                
                # Extract link
                link_elem = item.find('link')
                event_url = link_elem.get_text(strip=True) if link_elem else None
                
                # Extract date
                pub_date_elem = item.find('pubDate') or item.find('dc:date')
                event_date = None
                if pub_date_elem:
                    try:
                        # Try to parse RSS date format
                        from datetime import datetime
                        import email.utils
                        
                        date_str = pub_date_elem.get_text(strip=True)
                        # Parse RFC 2822 date format (common in RSS)
                        date_tuple = email.utils.parsedate_tz(date_str)
                        if date_tuple:
                            event_date = datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))
                    except:
                        pass
                
                if not title or len(title) < 3:
                    continue
                
                # Check if this looks like a movie
                all_text = f"{title} {description}".lower()
                movie_indicators = ['film', 'movie', 'kino', 'premiere', 'visning']
                if not any(indicator in all_text for indicator in movie_indicators):
                    continue
                
                event_data = {
                    'title': title,
                    'description': description[:500] if description else "",
                    'start': event_date.isoformat() if event_date else None,
                    'venue': "Odeon Kino Moss",
                    'location': "Moss, Norway",
                    'price': "Se kino for billetpriser",
                    'info_url': event_url,
                    'ticket_url': event_url,
                    'source': "Odeon Kino",
                    'category': "Film"
                }
                
                events.append(event_data)
                
            except Exception as e:
                log_warning("rss_item_parse", f"Failed to parse RSS item: {e}")
                continue
        
        return events
    
    async def try_api_endpoints(self) -> Optional[List[Dict]]:
        """Try to find API endpoints for movie data"""
        for endpoint in self.api_endpoints:
            try:
                log_info(f"Trying cinema API endpoint: {endpoint}")
                
                # Try different parameters
                params_list = [
                    {'cinema': 'moss', 'days': 7},
                    {'location': 'moss'},
                    {'cinema_id': 'moss'},
                    {}  # No params
                ]
                
                for params in params_list:
                    async with self.session.get(endpoint, params=params) as response:
                        if response.status == 200:
                            try:
                                data = await response.json()
                                if isinstance(data, list) and len(data) > 0:
                                    log_info(f"Found {len(data)} showtimes via API: {endpoint}")
                                    return data
                                elif isinstance(data, dict) and ('showtimes' in data or 'movies' in data):
                                    events = data.get('showtimes', data.get('movies', []))
                                    log_info(f"Found {len(events)} showtimes via API: {endpoint}")
                                    return events
                                    
                            except Exception as e:
                                log_warning("api_parse", f"Cinema API response not JSON: {e}")
                                continue
                        elif response.status == 403:
                            log_warning("api_request", f"Access denied for {endpoint}")
                        
            except Exception as e:
                log_warning("api_request", f"Cinema API request failed for {endpoint}: {e}")
                continue
        
        return None
    
    async def fetch_html_page(self) -> Optional[str]:
        """Try to fetch HTML page with different strategies"""
        urls_to_try = [
            self.moss_url,
            f"{self.base_url}/moss/program/",
            f"{self.base_url}/moss/filmer/",
            f"{self.base_url}/kino/moss/"
        ]
        
        for url in urls_to_try:
            try:
                log_info(f"Trying to fetch: {url}")
                
                # Add small delay to be respectful
                await asyncio.sleep(1)
                
                async with self.session.get(url) as response:
                    if response.status == 200:
                        log_info(f"Successfully fetched: {url}")
                        return await response.text()
                    elif response.status == 403:
                        log_warning("kino_scraper", f"Access denied for {url}")
                    else:
                        log_warning("kino_scraper", f"HTTP {response.status} for {url}")
                        
            except Exception as e:
                log_warning("kino_scraper", f"Failed to fetch {url}: {e}")
                continue
        
        return None
    
    def parse_api_showtimes(self, showtimes_data: List[Dict]) -> List[Dict[str, Any]]:
        """Parse movie showtimes from API response"""
        parsed_events = []
        
        for showtime_data in showtimes_data:
            try:
                # Movie title
                title = showtime_data.get('title') or showtime_data.get('movie_title', '')
                if not title:
                    title = showtime_data.get('film', {}).get('title', 'Unknown Movie')
                
                # Description/genre
                description = showtime_data.get('description', '') or showtime_data.get('synopsis', '')
                genre = showtime_data.get('genre', '')
                if genre and not description:
                    description = f"Genre: {genre}"
                
                # Parse showtime
                start_date = self.parse_api_date(
                    showtime_data.get('showtime') or 
                    showtime_data.get('start_time') or 
                    showtime_data.get('datetime')
                )
                
                # Duration
                duration = showtime_data.get('duration') or showtime_data.get('runtime')
                end_date = None
                if start_date and duration:
                    try:
                        if isinstance(duration, str):
                            # Parse "120 min" or "2h 30min"
                            minutes = self.parse_duration_minutes(duration)
                        else:
                            minutes = int(duration)
                        
                        if minutes:
                            end_date = start_date + timedelta(minutes=minutes)
                    except:
                        pass
                
                # Price information
                price = showtime_data.get('price', '')
                if not price:
                    price = "Se kino for billetpriser"
                
                # URLs
                booking_url = showtime_data.get('booking_url') or showtime_data.get('ticket_url')
                info_url = showtime_data.get('movie_url') or booking_url
                
                parsed_event = {
                    'title': title,
                    'description': description[:500] if description else "",
                    'start': start_date.isoformat() if start_date else None,
                    'end': end_date.isoformat() if end_date else None,
                    'venue': "Odeon Kino Moss",
                    'location': "Moss, Norway",
                    'price': price,
                    'info_url': info_url,
                    'ticket_url': booking_url or info_url,
                    'source': "Odeon Kino",
                    'category': "Film"
                }
                
                if parsed_event['start']:  # Only include showtimes with valid times
                    parsed_events.append(parsed_event)
                    
            except Exception as e:
                log_warning("api_parse", f"Failed to parse showtime: {e}")
                continue
        
        return parsed_events
    
    def parse_html_showtimes(self, html: str) -> List[Dict[str, Any]]:
        """Parse movie showtimes from HTML - focus on premieres only"""
        events = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Look for movie/showtime containers with enhanced selectors
            showtime_selectors = [
                '.showtime', '.movie-showtime', '.screening',
                '.film-item', '.movie-item', '.program-item',
                '.premiere', '.movie-premiere',  # Premier-specific
                '[class*="showtime"]', '[class*="movie"]', '[class*="film"]',
                '[class*="premiere"]',  # Premier-specific
                '.event-item', 'article', '.card', '.item'
            ]
            
            showtime_elements = []
            for selector in showtime_selectors:
                elements = soup.select(selector)
                if elements:
                    showtime_elements.extend(elements)
            
            # Remove duplicates while preserving order
            seen_elements = set()
            unique_elements = []
            for elem in showtime_elements:
                elem_str = str(elem)
                if elem_str not in seen_elements:
                    seen_elements.add(elem_str)
                    unique_elements.append(elem)
            
            showtime_elements = unique_elements
            
            # Fallback: look for any content that might contain movies
            if not showtime_elements:
                log_info("Using fallback search for movie content")
                main_content = soup.find('main') or soup.find('body')
                if main_content:
                    # Look for any div/article that might contain movie info
                    all_elements = main_content.find_all(['div', 'article', 'section'])
                    for elem in all_elements:
                        elem_text = elem.get_text().lower()
                        # Check for movie/cinema indicators
                        if any(word in elem_text for word in ['film', 'movie', 'kino', 'premiere', 'visning', 'forestilling']):
                            showtime_elements.append(elem)
            
            log_info(f"Found {len(showtime_elements)} potential movie elements")
            
            for i, elem in enumerate(showtime_elements):
                try:
                    event = self.extract_html_showtime_data(elem)
                    if event:
                        # Filter for premieres only if requested
                        if self.premieres_only and not self.is_premiere(event, elem):
                            continue
                        events.append(event)
                        log_info(f"Successfully extracted movie {i+1}: {event['title'][:50]}...")
                except Exception as e:
                    log_warning("html_parse", f"Failed to parse HTML showtime {i+1}: {e}")
                    continue
        
        except Exception as e:
            log_error("html_parse", f"Failed to parse HTML: {e}")
        
        return events
    
    def is_premiere(self, event: Dict[str, Any], elem) -> bool:
        """Check if this is a movie premiere"""
        elem_text = elem.get_text().lower()
        title = event.get('title', '').lower()
        description = event.get('description', '').lower()
        
        # Keywords that indicate a premiere
        premiere_keywords = [
            'premiere', 'premiär', 'ny film', 'new movie',
            'åpning', 'opening', 'første visning', 'first showing',
            'sniktitt', 'preview', 'førpremiere'
        ]
        
        # Check if any premiere keywords are present
        all_text = f"{elem_text} {title} {description}"
        has_premiere_keywords = any(keyword in all_text for keyword in premiere_keywords)
        
        # Also consider new releases (movies from last few weeks)
        # This is a rough heuristic since we don't have exact release dates
        if event.get('start'):
            try:
                event_date = datetime.fromisoformat(event['start'])
                # Consider movies in the near future as potential premieres
                days_from_now = (event_date - datetime.now()).days
                is_upcoming = 0 <= days_from_now <= 14  # Next 2 weeks
                
                if is_upcoming:
                    return True
            except:
                pass
        
        return has_premiere_keywords
    
    def extract_html_showtime_data(self, elem) -> Optional[Dict[str, Any]]:
        """Extract showtime data from HTML element"""
        try:
            # Extract movie title
            title_elem = elem.find(['h1', 'h2', 'h3', 'h4', 'h5'])
            if not title_elem:
                title_elem = elem.find('a') or elem.find('[class*="title"]')
                
            title = title_elem.get_text(strip=True) if title_elem else ""
            
            if not title or len(title) < 3:
                return None
            
            # Extract description/genre
            desc_elem = elem.find(['p', 'div'], class_=re.compile(r'desc|content|summary|genre'))
            description = desc_elem.get_text(strip=True) if desc_elem else ""
            
            # Extract link
            link_elem = elem.find('a', href=True)
            event_url = None
            if link_elem:
                href = link_elem['href']
                event_url = href if href.startswith('http') else f"{self.base_url}{href}"
            
            # Parse showtime from text content
            elem_text = elem.get_text()
            showtime = self.parse_showtime_from_text(elem_text)
            
            # Check if this looks like a movie
            elem_text_lower = elem_text.lower()
            movie_keywords = [
                'film', 'kino', 'movie', 'visning', 'forestilling', 
                'premiere', 'time', 'minutter', 'drama', 'komedie'
            ]
            
            has_movie_indicators = any(keyword in elem_text_lower for keyword in movie_keywords)
            
            if not showtime and not has_movie_indicators:
                return None
            
            event_data = {
                'title': title,
                'description': description[:500] if description else "",
                'start': showtime.isoformat() if showtime else None,
                'venue': "Odeon Kino Moss",
                'location': "Moss, Norway",
                'price': "Se kino for billetpriser",
                'info_url': event_url,
                'ticket_url': event_url,
                'source': "Odeon Kino",
                'category': "Film"
            }
            
            return event_data
            
        except Exception as e:
            log_error("html_extract", f"Failed to extract HTML showtime: {e}")
            return None
    
    def parse_api_date(self, date_str: Any) -> Optional[datetime]:
        """Parse date from API response"""
        if not date_str:
            return None
            
        try:
            if isinstance(date_str, str):
                # ISO format
                if 'T' in date_str:
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                # Date only
                elif '-' in date_str:
                    return datetime.fromisoformat(f"{date_str}T19:30:00")
            
            # Unix timestamp
            elif isinstance(date_str, (int, float)):
                return datetime.fromtimestamp(date_str)
                
        except Exception as e:
            log_warning("date_parse", f"Failed to parse API date '{date_str}': {e}")
        
        return None
    
    def parse_showtime_from_text(self, text: str) -> Optional[datetime]:
        """Parse movie showtime from text"""
        try:
            # Look for time patterns like "19:30" or "kl. 20:15"
            time_pattern = r'(?:kl\.?\s*)?(\d{1,2}):(\d{2})'
            time_match = re.search(time_pattern, text)
            
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2))
                
                # Look for date patterns
                months = {
                    'januar': 1, 'jan': 1, 'februar': 2, 'feb': 2,
                    'mars': 3, 'mar': 3, 'april': 4, 'apr': 4,
                    'mai': 5, 'juni': 6, 'jun': 6, 'juli': 7, 'jul': 7,
                    'august': 8, 'aug': 8, 'september': 9, 'sep': 9,
                    'oktober': 10, 'okt': 10, 'november': 11, 'nov': 11,
                    'desember': 12, 'des': 12
                }
                
                date_pattern = r'(\d{1,2})\.?\s*([a-zA-ZæøåÆØÅ]+)'
                date_match = re.search(date_pattern, text.lower())
                
                if date_match:
                    day = int(date_match.group(1))
                    month_name = date_match.group(2).strip('.')
                    month = months.get(month_name) or months.get(month_name[:3])
                    
                    if month:
                        year = datetime.now().year
                        # Handle year rollover
                        if month < datetime.now().month - 1:
                            year += 1
                        
                        return datetime(year, month, day, hour, minute)
                
                # If no date found, assume today or tomorrow based on time
                now = datetime.now()
                target_date = now.date()
                
                # If showtime is earlier than current time, assume tomorrow
                showtime_today = datetime.combine(target_date, datetime.min.time().replace(hour=hour, minute=minute))
                if showtime_today < now:
                    target_date = target_date + timedelta(days=1)
                
                return datetime.combine(target_date, datetime.min.time().replace(hour=hour, minute=minute))
                    
        except Exception as e:
            log_warning("time_parse", f"Failed to parse showtime from '{text[:100]}': {e}")
            
        return None
    
    def parse_duration_minutes(self, duration_str: str) -> Optional[int]:
        """Parse duration string to minutes"""
        try:
            # Match patterns like "120 min", "2h 30min", "90"
            if 'h' in duration_str:
                # Format: "2h 30min"
                match = re.search(r'(\d+)h\s*(\d+)?', duration_str)
                if match:
                    hours = int(match.group(1))
                    minutes = int(match.group(2)) if match.group(2) else 0
                    return hours * 60 + minutes
            else:
                # Format: "120 min" or "120"
                match = re.search(r'(\d+)', duration_str)
                if match:
                    return int(match.group(1))
        except:
            pass
        
        return None
    
    async def scrape_all_showtimes(self) -> List[Dict[str, Any]]:
        """Main scraping method - try RSS first, then other methods"""
        # Try RSS feeds first (often less restricted than main site)
        log_info("Trying RSS feeds first (premieres focus)")
        rss_events = await self.try_rss_feeds()
        if rss_events:
            log_info(f"Successfully found {len(rss_events)} events from RSS feeds")
            return rss_events
        
        # Try API endpoints
        log_info("RSS feeds not available, trying API endpoints")
        api_data = await self.try_api_endpoints()
        if api_data:
            events = self.parse_api_showtimes(api_data)
            if events:
                log_info(f"Successfully found {len(events)} events from API")
                return events
        
        # Try Playwright to bypass 403 restrictions
        log_info("API not available, using Playwright to bypass access restrictions")
        playwright_html = await self.fetch_with_playwright()
        if playwright_html:
            events = self.parse_html_showtimes(playwright_html)
            if events and not any('blocked' in event.get('title', '').lower() for event in events):
                log_info(f"Successfully found {len(events)} movie events with Playwright")
                return events
            else:
                log_info("Playwright HTML parsing found no valid movie events or was blocked")
        
        # Final fallback to HTML scraping with session
        log_info("Playwright blocked, falling back to session-based HTML scraping")
        html = await self.fetch_html_page()
        if html:
            return self.parse_html_showtimes(html)
        
        # If all fails, return empty list (this cinema may not have public data)
        log_warning("odeon_scraper", "Odeon Kino appears to block automated access - no movie data available")
        return []


async def crawl_odeon_kino_events() -> List[Event]:
    """Main function to crawl Odeon Kino showtimes"""
    events = []
    
    try:
        async with OdeonKinoScraper() as scraper:
            event_data_list = await scraper.scrape_all_showtimes()
            
            # Convert to Event objects
            for event_data in event_data_list:
                try:
                    if not event_data.get('start'):
                        continue
                        
                    start_time = datetime.fromisoformat(event_data['start'])
                    end_time = None
                    if event_data.get('end'):
                        end_time = datetime.fromisoformat(event_data['end'])
                    
                    event = Event(
                        id=str(uuid4()),
                        title=event_data.get('title', 'Unknown Movie'),
                        description=event_data.get('description', ''),
                        start=start_time,
                        end=end_time,
                        venue=event_data.get('venue', 'Odeon Kino Moss'),
                        location=event_data.get('location', 'Moss, Norway'),
                        price=event_data.get('price', ''),
                        ticket_url=event_data.get('ticket_url', ''),
                        info_url=event_data.get('info_url', ''),
                        source="Odeon Kino",
                        source_type="html",
                        category=event_data.get('category', 'Film'),
                        age_restriction="",
                        organizer="Odeon Kino",
                        first_seen=datetime.now(),
                        last_seen=datetime.now()
                    )
                    events.append(event)
                    
                except Exception as e:
                    log_error("odeon_convert", f"Failed to convert showtime: {e}")
        
        log_info(f"🎬 Odeon Kino: Successfully scraped {len(events)} showtimes")
        
    except Exception as e:
        log_error("odeon_scraper", f"Scraping failed: {e}")
    
    return events


if __name__ == "__main__":
    async def main():
        init_logging()
        events = await crawl_odeon_kino_events()
        
        # Save to JSON for debugging
        output_file = Path("/var/www/vhosts/herimoss.no/pythoncrawler/odeon_kino_events.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump([{
                'title': e.title,
                'start': e.start.isoformat() if e.start else None,
                'end': e.end.isoformat() if e.end else None,
                'venue': e.venue,
                'price': e.price,
                'description': e.description
            } for e in events], f, ensure_ascii=False, indent=2)
        
        print(f"Scraped {len(events)} Odeon Kino showtimes")
        for event in events[:5]:
            print(f"  {event.start.strftime('%Y-%m-%d %H:%M') if event.start else 'No date'} | {event.title}")
    
    asyncio.run(main())