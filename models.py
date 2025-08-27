"""
Pydantic models for the event crawler system.
"""
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, HttpUrl, field_validator
from slugify import slugify
import hashlib


class Event(BaseModel):
    """Main event model with normalization and validation."""
    
    id: str
    title: str
    description: Optional[str] = None
    url: Optional[HttpUrl] = None
    ticket_url: Optional[HttpUrl] = None
    image_url: Optional[HttpUrl] = None
    venue: Optional[str] = None
    address: Optional[str] = None
    city: str = "Moss"
    lat: Optional[float] = None
    lon: Optional[float] = None
    category: Optional[str] = None
    start: datetime
    end: Optional[datetime] = None
    price: Optional[str] = None
    source: str
    source_type: Literal["ical", "rss", "html", "api", "email", "manual"]
    source_url: Optional[HttpUrl] = None
    first_seen: datetime
    last_seen: datetime
    status: Literal["upcoming", "archived"] = "upcoming"
    
    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Clean and validate title."""
        return v.strip()[:200] if v else "Uten tittel"
    
    @field_validator("description")
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        """Clean description, strip HTML tags."""
        if not v:
            return None
        # Basic HTML stripping - will be enhanced later
        import re
        clean = re.sub(r'<[^>]+>', '', v)
        return clean.strip()[:1000] if clean.strip() else None
    
    @field_validator("price")
    @classmethod
    def validate_price(cls, v: Optional[str]) -> Optional[str]:
        """Normalize price text."""
        if not v:
            return None
        v = v.strip().lower()
        if any(word in v for word in ["gratis", "free", "fri adgang"]):
            return "Gratis"
        # Extract Norwegian price format
        import re
        price_match = re.search(r'kr\s*(\d+)', v)
        if price_match:
            return f"kr {price_match.group(1)}"
        return v[:50]
    
    @classmethod
    def generate_id(cls, title: str, start: datetime, venue: Optional[str] = None) -> str:
        """Generate stable ID from title + start date + venue."""
        date_str = start.strftime("%Y-%m-%d")
        venue_str = slugify(venue) if venue else "unknown"
        title_str = slugify(title)
        
        id_string = f"{title_str}|{date_str}|{venue_str}"
        return hashlib.sha1(id_string.encode("utf-8")).hexdigest()[:16]
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "url": str(self.url) if self.url else None,
            "ticket_url": str(self.ticket_url) if self.ticket_url else None,
            "image_url": str(self.image_url) if self.image_url else None,
            "venue": self.venue,
            "address": self.address,
            "city": self.city,
            "lat": self.lat,
            "lon": self.lon,
            "category": self.category,
            "start": self.start.isoformat(),
            "end": self.end.isoformat() if self.end else None,
            "price": self.price,
            "source": self.source,
            "source_type": self.source_type,
            "source_url": str(self.source_url) if self.source_url else None,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "status": self.status
        }


class SourceConfig(BaseModel):
    """Configuration for a single event source."""
    
    enabled: bool = True
    ical_urls: list[str] = []
    html_urls: list[str] = []
    rss_urls: list[str] = []


class HttpConfig(BaseModel):
    """HTTP client configuration."""
    
    timeout_sec: int = 15
    max_concurrency: int = 8
    rate_limit_per_host_per_sec: float = 1.0
    retry: dict = {"tries": 3, "backoff_sec": 1.2}


class HtmlConfig(BaseModel):
    """HTML output configuration."""
    
    site_title: str = "Moss Kulturkalender"
    show_archive: bool = True
    max_archive_on_front: int = 12


class RulesConfig(BaseModel):
    """Processing rules configuration."""
    
    archive_if_ended_before_hours: int = 1
    default_city: str = "Moss"
    category_keywords: dict[str, list[str]] = {
        "Musikk": ["konsert", "band", "dj", "live", "gig"],
        "Teater": ["teater", "standup", "improv", "forestilling"],
        "Familie": ["familie", "barn", "barne", "familiedag"],
        "Utstilling": ["utstilling", "vernissage", "galleri"]
    }


class Config(BaseModel):
    """Main configuration model."""
    
    timezone: str = "Europe/Oslo"
    output_html: str = "/var/www/vhosts/herimoss.no/httpdocs/index.html"
    sources: dict[str, SourceConfig] = {}
    http: HttpConfig = HttpConfig()
    html: HtmlConfig = HtmlConfig()
    rules: RulesConfig = RulesConfig()


class LogEntry(BaseModel):
    """Structured log entry."""
    
    ts: datetime
    level: Literal["DEBUG", "INFO", "WARN", "ERROR"]
    message: str
    source: Optional[str] = None
    url: Optional[str] = None


class ErrorEntry(BaseModel):
    """Structured error entry."""
    
    ts: datetime
    source: str
    severity: Literal["WARN", "ERROR", "CRITICAL"]
    message: str
    url: Optional[str] = None
    stack: Optional[str] = None


class Statistics(BaseModel):
    """Run statistics."""
    
    start_time: datetime
    end_time: Optional[datetime] = None
    sources_attempted: int = 0
    sources_succeeded: int = 0
    sources_failed: int = 0
    events_fetched: int = 0
    events_new: int = 0
    events_updated: int = 0
    events_archived: int = 0
    events_total: int = 0
