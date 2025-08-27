"""
Event deduplication system using hash-based primary matching and fuzzy fallback.
"""
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Set, Tuple, Optional
from rapidfuzz import fuzz
from slugify import slugify
from models import Event
from logging_utils import log_info, log_warning, log_debug


class EventDeduplicator:
    """Handles event deduplication with hash primary and fuzzy fallback."""
    
    def __init__(self, fuzzy_threshold: int = 90, time_window_minutes: int = 60):
        self.fuzzy_threshold = fuzzy_threshold
        self.time_window_minutes = time_window_minutes
        self.seen_hashes: Set[str] = set()
        self.events_by_hash: Dict[str, Event] = {}
    
    def load_seen_hashes(self, seen_hashes: Set[str]):
        """Load previously seen hashes."""
        self.seen_hashes = seen_hashes.copy()
        log_debug(f"Loaded {len(self.seen_hashes)} seen hashes")
    
    def generate_event_hash(self, event: Event) -> str:
        """Generate stable hash for event."""
        return Event.generate_id(event.title, event.start, event.venue)
    
    def generate_fuzzy_key(self, event: Event) -> str:
        """Generate fuzzy matching key (title + date + venue)."""
        title_slug = slugify(event.title)
        date_str = event.start.strftime("%Y-%m-%d")
        venue_slug = slugify(event.venue) if event.venue else "unknown"
        
        return f"{title_slug}|{date_str}|{venue_slug}"
    
    def is_time_match(self, time1: datetime, time2: datetime) -> bool:
        """Check if two times are within the acceptable window."""
        diff = abs((time1 - time2).total_seconds() / 60)
        return diff <= self.time_window_minutes
    
    def calculate_event_similarity(self, event1: Event, event2: Event) -> float:
        """Calculate similarity score between two events."""
        # Title similarity (most important)
        title_sim = fuzz.ratio(event1.title.lower(), event2.title.lower())
        
        # Time similarity
        time_match = self.is_time_match(event1.start, event2.start)
        time_sim = 100 if time_match else 0
        
        # Venue similarity
        venue1 = event1.venue or ""
        venue2 = event2.venue or ""
        venue_sim = fuzz.ratio(venue1.lower(), venue2.lower()) if venue1 and venue2 else 50
        
        # Weighted average
        similarity = (title_sim * 0.5 + time_sim * 0.3 + venue_sim * 0.2)
        
        return similarity
    
    def find_fuzzy_duplicates(self, new_event: Event, existing_events: List[Event]) -> List[Tuple[Event, float]]:
        """Find potential fuzzy duplicates with similarity scores."""
        candidates = []
        
        for existing_event in existing_events:
            # Skip if dates are too far apart (optimization)
            date_diff = abs((new_event.start - existing_event.start).days)
            if date_diff > 1:  # More than 1 day difference
                continue
            
            similarity = self.calculate_event_similarity(new_event, existing_event)
            
            if similarity >= self.fuzzy_threshold:
                candidates.append((existing_event, similarity))
        
        # Sort by similarity (highest first)
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        return candidates
    
    def merge_events(self, existing_event: Event, new_event: Event) -> Event:
        """Merge two duplicate events, keeping the best information."""
        merged = existing_event.model_copy()
        
        # Update last_seen
        merged.last_seen = datetime.now().replace(tzinfo=None)
        
        # Keep the most complete information
        if not merged.description and new_event.description:
            merged.description = new_event.description
        
        if not merged.url and new_event.url:
            merged.url = new_event.url
        
        if not merged.ticket_url and new_event.ticket_url:
            merged.ticket_url = new_event.ticket_url
        
        if not merged.image_url and new_event.image_url:
            merged.image_url = new_event.image_url
        
        if not merged.venue and new_event.venue:
            merged.venue = new_event.venue
        
        if not merged.address and new_event.address:
            merged.address = new_event.address
        
        if not merged.price and new_event.price:
            merged.price = new_event.price
        
        if not merged.category and new_event.category:
            merged.category = new_event.category
        
        # Prefer more specific end time
        if not merged.end and new_event.end:
            merged.end = new_event.end
        
        # Prefer official/primary sources for URLs
        source_priority = {
            "ical": 1, "api": 2, "html": 3, "rss": 4, "email": 5, "manual": 6
        }
        
        new_priority = source_priority.get(new_event.source_type, 10)
        existing_priority = source_priority.get(merged.source_type, 10)
        
        if new_priority < existing_priority:
            if new_event.url:
                merged.url = new_event.url
            if new_event.ticket_url:
                merged.ticket_url = new_event.ticket_url
        
        return merged
    
    def deduplicate_events(self, events: List[Event]) -> Tuple[List[Event], Dict[str, str]]:
        """
        Deduplicate a list of events.
        Returns: (unique_events, duplicate_mappings)
        """
        unique_events = []
        duplicate_mappings = {}  # original_id -> kept_id
        
        # Build lookup for existing events
        events_by_fuzzy_key = {}
        
        for event in events:
            event_hash = self.generate_event_hash(event)
            
            # Check exact hash match first
            if event_hash in self.seen_hashes:
                # This is a known event, find it and merge
                for existing in unique_events:
                    if self.generate_event_hash(existing) == event_hash:
                        merged = self.merge_events(existing, event)
                        # Replace in unique_events
                        idx = unique_events.index(existing)
                        unique_events[idx] = merged
                        duplicate_mappings[event.id] = merged.id
                        log_debug(f"Hash match: merged '{event.title}' into existing event")
                        break
                continue
            
            # Check fuzzy matches
            fuzzy_key = self.generate_fuzzy_key(event)
            similar_events = events_by_fuzzy_key.get(fuzzy_key, [])
            
            duplicate_found = False
            for similar_event in similar_events:
                similarity = self.calculate_event_similarity(event, similar_event)
                
                if similarity >= self.fuzzy_threshold:
                    # Found fuzzy duplicate
                    merged = self.merge_events(similar_event, event)
                    
                    # Replace in unique_events
                    idx = unique_events.index(similar_event)
                    unique_events[idx] = merged
                    
                    duplicate_mappings[event.id] = merged.id
                    
                    log_debug(f"Fuzzy match ({similarity:.1f}%): merged '{event.title}' into existing event")
                    duplicate_found = True
                    break
            
            if not duplicate_found:
                # This is a new unique event
                unique_events.append(event)
                self.seen_hashes.add(event_hash)
                
                # Add to fuzzy lookup
                if fuzzy_key not in events_by_fuzzy_key:
                    events_by_fuzzy_key[fuzzy_key] = []
                events_by_fuzzy_key[fuzzy_key].append(event)
        
        log_info(f"Deduplication: {len(events)} -> {len(unique_events)} unique events ({len(duplicate_mappings)} duplicates removed)")
        
        return unique_events, duplicate_mappings
    
    def get_seen_hashes(self) -> Set[str]:
        """Get current set of seen hashes."""
        return self.seen_hashes.copy()


def deduplicate_event_list(events: List[Event], 
                          existing_hashes: Set[str] = None,
                          fuzzy_threshold: int = 90,
                          time_window_minutes: int = 60) -> Tuple[List[Event], Set[str], Dict[str, str]]:
    """
    Convenience function to deduplicate a list of events.
    
    Returns:
        - unique_events: List of deduplicated events
        - seen_hashes: Updated set of seen hashes
        - duplicate_mappings: Mapping of duplicate IDs to kept IDs
    """
    deduplicator = EventDeduplicator(fuzzy_threshold, time_window_minutes)
    
    if existing_hashes:
        deduplicator.load_seen_hashes(existing_hashes)
    
    unique_events, duplicate_mappings = deduplicator.deduplicate_events(events)
    seen_hashes = deduplicator.get_seen_hashes()
    
    return unique_events, seen_hashes, duplicate_mappings


def create_similarity_report(events: List[Event], threshold: int = 80) -> List[Dict]:
    """Create a report of potentially similar events for manual review."""
    report = []
    
    for i, event1 in enumerate(events):
        for j, event2 in enumerate(events[i+1:], start=i+1):
            deduplicator = EventDeduplicator()
            similarity = deduplicator.calculate_event_similarity(event1, event2)
            
            if similarity >= threshold:
                report.append({
                    "event1_id": event1.id,
                    "event1_title": event1.title,
                    "event1_start": event1.start.isoformat(),
                    "event1_venue": event1.venue,
                    "event2_id": event2.id,
                    "event2_title": event2.title,
                    "event2_start": event2.start.isoformat(),
                    "event2_venue": event2.venue,
                    "similarity": similarity
                })
    
    return sorted(report, key=lambda x: x["similarity"], reverse=True)
