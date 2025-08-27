"""
Utility functions for HTTP requests, rate limiting, and common operations.
"""
import asyncio
import time
from typing import Optional, Dict, Any
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
import logging


class RateLimiter:
    """Per-host rate limiter."""
    
    def __init__(self, requests_per_second: float = 1.0):
        self.requests_per_second = requests_per_second
        self.last_request: Dict[str, float] = {}
        self.lock = asyncio.Lock()
    
    async def wait_if_needed(self, host: str) -> None:
        """Wait if necessary to respect rate limit for host."""
        async with self.lock:
            now = time.time()
            last = self.last_request.get(host, 0)
            min_interval = 1.0 / self.requests_per_second
            
            if now - last < min_interval:
                wait_time = min_interval - (now - last)
                await asyncio.sleep(wait_time)
            
            self.last_request[host] = time.time()


class HttpClient:
    """Async HTTP client with rate limiting and robots.txt respect."""
    
    def __init__(self, 
                 timeout: int = 15,
                 max_concurrency: int = 8,
                 rate_limit_per_sec: float = 1.0,
                 user_agent: str = "MossKulturkalender/1.0 (+https://herimoss.no)"):
        
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.rate_limiter = RateLimiter(rate_limit_per_sec)
        self.user_agent = user_agent
        self.robots_cache: Dict[str, bool] = {}
        
        # Configure httpx client
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": user_agent},
            follow_redirects=True
        )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    def _get_host(self, url: str) -> str:
        """Extract host from URL."""
        return urlparse(url).netloc
    
    async def _check_robots_txt(self, url: str) -> bool:
        """Check if robots.txt allows crawling this URL."""
        host = self._get_host(url)
        
        if host in self.robots_cache:
            return self.robots_cache[host]
        
        try:
            robots_url = urljoin(f"https://{host}", "/robots.txt")
            
            # Simple check - in production, use robotparser
            response = await self.client.get(robots_url, timeout=5)
            if response.status_code == 200:
                robots_content = response.text
                # Basic check for disallow patterns
                if "Disallow: /" in robots_content and self.user_agent not in robots_content:
                    self.robots_cache[host] = False
                    return False
            
            self.robots_cache[host] = True
            return True
            
        except Exception:
            # If we can't check robots.txt, assume allowed but be cautious
            self.robots_cache[host] = True
            return True
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1.2, min=1, max=10)
    )
    async def get(self, url: str, **kwargs) -> httpx.Response:
        """Make GET request with rate limiting and retries."""
        async with self.semaphore:
            host = self._get_host(url)
            
            # Check robots.txt
            if not await self._check_robots_txt(url):
                raise httpx.RequestError(f"Robots.txt disallows crawling {url}")
            
            # Rate limit
            await self.rate_limiter.wait_if_needed(host)
            
            # Make request
            response = await self.client.get(url, **kwargs)
            response.raise_for_status()
            
            return response
    
    async def get_json(self, url: str, **kwargs) -> Dict[str, Any]:
        """Get JSON response."""
        response = await self.get(url, **kwargs)
        return response.json()
    
    async def get_text(self, url: str, **kwargs) -> str:
        """Get text response."""
        response = await self.get(url, **kwargs)
        return response.text


def clean_html_text(html: str) -> str:
    """Remove HTML tags and clean text."""
    import re
    from html import unescape
    
    # Remove script and style elements
    clean = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', clean)
    
    # Unescape HTML entities
    clean = unescape(clean)
    
    # Normalize whitespace
    clean = re.sub(r'\s+', ' ', clean).strip()
    
    return clean


def extract_price_from_text(text: str) -> Optional[str]:
    """Extract price information from text."""
    import re
    
    text = text.lower()
    
    # Check for free indicators
    if any(word in text for word in ["gratis", "free", "fri adgang", "ingen avgift"]):
        return "Gratis"
    
    # Extract Norwegian currency
    price_patterns = [
        r'kr\s*(\d+(?:[.,]\d+)?)',
        r'(\d+(?:[.,]\d+)?)\s*kr',
        r'(\d+(?:[.,]\d+)?)\s*kroner',
        r'pris[:\s]*(\d+)',
    ]
    
    for pattern in price_patterns:
        match = re.search(pattern, text)
        if match:
            price = match.group(1).replace(',', '.')
            try:
                price_num = float(price)
                if price_num == int(price_num):
                    return f"kr {int(price_num)}"
                else:
                    return f"kr {price_num:.2f}"
            except ValueError:
                continue
    
    return None


def normalize_venue_name(venue: str) -> str:
    """Normalize venue names."""
    import re
    
    if not venue:
        return ""
    
    # Remove common prefixes/suffixes
    venue = re.sub(r'^(scene|teater|kulturhus|kino)\s+', '', venue, flags=re.IGNORECASE)
    venue = re.sub(r'\s+(scene|teater|kulturhus|kino)$', '', venue, flags=re.IGNORECASE)
    
    # Capitalize properly
    venue = venue.title()
    
    # Known venue mappings
    venue_mappings = {
        "verket": "Verket Scene",
        "moss kulturhus": "Moss Kulturhus",
        "moss teater": "Moss Teater",
    }
    
    venue_lower = venue.lower()
    for key, value in venue_mappings.items():
        if key in venue_lower:
            return value
    
    return venue.strip()


def categorize_event(title: str, description: str = "", keywords_config: dict = None) -> Optional[str]:
    """Categorize event based on title and description."""
    if not keywords_config:
        keywords_config = {
            "Musikk": ["konsert", "band", "dj", "live", "gig", "musikk", "sang"],
            "Teater": ["teater", "standup", "improv", "forestilling", "drama", "komedie"],
            "Familie": ["familie", "barn", "barne", "familiedag", "lekeplass"],
            "Utstilling": ["utstilling", "vernissage", "galleri", "kunst", "maleri"]
        }
    
    text = f"{title} {description}".lower()
    
    for category, keywords in keywords_config.items():
        if any(keyword in text for keyword in keywords):
            return category
    
    return None


async def fetch_feed(url: str, client: HttpClient) -> dict:
    """Fetch and parse RSS/Atom feed."""
    import feedparser
    
    try:
        response = await client.get(url)
        feed = feedparser.parse(response.text)
        
        return {
            "title": getattr(feed.feed, "title", ""),
            "entries": feed.entries,
            "error": None
        }
    except Exception as e:
        return {
            "title": "",
            "entries": [],
            "error": str(e)
        }


async def fetch_ical(url: str, client: HttpClient) -> dict:
    """Fetch and parse iCal feed."""
    from icalendar import Calendar
    
    try:
        response = await client.get(url)
        calendar = Calendar.from_ical(response.text)
        
        events = []
        for component in calendar.walk():
            if component.name == "VEVENT":
                events.append(component)
        
        return {
            "events": events,
            "error": None
        }
    except Exception as e:
        return {
            "events": [],
            "error": str(e)
        }
