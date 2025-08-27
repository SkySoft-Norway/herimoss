"""
Event Deduplication Module for Moss Kulturkalender
Advanced duplicate detection using multiple strategies and machine learning approaches
"""

import asyncio
import difflib
import re
from datetime import datetime, timedelta
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict

from models import Event
from logging_utils import log_info, log_warning, log_error


@dataclass
class DuplicationMatch:
    """Represents a potential duplicate match between events"""
    event1: Event
    event2: Event
    similarity_score: float
    matching_fields: List[str]
    confidence: str  # 'high', 'medium', 'low'
    reason: str


class EventDeduplicator:
    """Advanced event deduplication with multiple detection strategies"""
    
    def __init__(self):
        self.similarity_threshold_high = 0.95  # Definite duplicates
        self.similarity_threshold_medium = 0.85  # Likely duplicates
        self.similarity_threshold_low = 0.70   # Possible duplicates
        
        # Norwegian common words to ignore in title comparison
        self.norwegian_stopwords = {
            'og', 'i', 'på', 'med', 'av', 'til', 'for', 'om', 'ved', 'fra',
            'det', 'den', 'de', 'et', 'en', 'er', 'var', 'har', 'ikke',
            'konsert', 'festival', 'arrangement', 'event', 'show', 'teater',
            'forestilling', 'opptreden', 'utstilling', 'workshop', 'kurs'
        }
    
    async def find_duplicates(self, events: List[Event]) -> List[DuplicationMatch]:
        """Find potential duplicates in a list of events"""
        if len(events) < 2:
            return []
        
        log_info(f"Analyzing {len(events)} events for duplicates...")
        
        duplicates = []
        
        # Strategy 1: Exact field matching
        exact_matches = await self._find_exact_matches(events)
        duplicates.extend(exact_matches)
        
        # Strategy 2: Fuzzy string matching
        fuzzy_matches = await self._find_fuzzy_matches(events)
        duplicates.extend(fuzzy_matches)
        
        # Strategy 3: Venue and time proximity
        proximity_matches = await self._find_proximity_matches(events)
        duplicates.extend(proximity_matches)
        
        # Strategy 4: URL similarity
        url_matches = await self._find_url_matches(events)
        duplicates.extend(url_matches)
        
        # Remove duplicate matches and sort by confidence
        unique_matches = self._deduplicate_matches(duplicates)
        unique_matches.sort(key=lambda x: x.similarity_score, reverse=True)
        
        log_info(f"Found {len(unique_matches)} potential duplicate pairs")
        return unique_matches
    
    async def _find_exact_matches(self, events: List[Event]) -> List[DuplicationMatch]:
        """Find events with exactly matching key fields"""
        matches = []
        seen_combinations = set()
        
        for i, event1 in enumerate(events):
            for event2 in events[i+1:]:
                # Create signature for exact matching
                sig1 = self._create_exact_signature(event1)
                sig2 = self._create_exact_signature(event2)
                
                if sig1 == sig2 and sig1 not in seen_combinations:
                    seen_combinations.add(sig1)
                    
                    match = DuplicationMatch(
                        event1=event1,
                        event2=event2,
                        similarity_score=1.0,
                        matching_fields=['title', 'venue', 'start_time'],
                        confidence='high',
                        reason='Exact match on title, venue, and start time'
                    )
                    matches.append(match)
        
        log_info(f"Found {len(matches)} exact matches")
        return matches
    
    def _create_exact_signature(self, event: Event) -> str:
        """Create normalized signature for exact matching"""
        title = self._normalize_text(event.title) if event.title else ""
        venue = self._normalize_text(event.venue) if event.venue else ""
        start_time = event.start.strftime('%Y%m%d%H%M') if event.start else ""
        
        return f"{title}|{venue}|{start_time}"
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove special characters and extra whitespace
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # Remove common Norwegian stopwords
        words = [word for word in text.split() if word not in self.norwegian_stopwords]
        
        return ' '.join(words)
    
    async def _find_fuzzy_matches(self, events: List[Event]) -> List[DuplicationMatch]:
        """Find events with similar titles and details using fuzzy matching"""
        matches = []
        
        for i, event1 in enumerate(events):
            for event2 in events[i+1:]:
                similarity = await self._calculate_event_similarity(event1, event2)
                
                if similarity.similarity_score >= self.similarity_threshold_low:
                    matches.append(similarity)
        
        log_info(f"Found {len(matches)} fuzzy matches")
        return matches
    
    async def _calculate_event_similarity(self, event1: Event, event2: Event) -> DuplicationMatch:
        """Calculate comprehensive similarity between two events"""
        scores = {}
        matching_fields = []
        
        # Title similarity (most important)
        title_score = self._text_similarity(event1.title, event2.title)
        scores['title'] = title_score * 0.4  # 40% weight
        if title_score > 0.7:
            matching_fields.append('title')
        
        # Venue similarity
        venue_score = self._text_similarity(event1.venue, event2.venue)
        scores['venue'] = venue_score * 0.2  # 20% weight
        if venue_score > 0.7:
            matching_fields.append('venue')
        
        # Time proximity (events within 24 hours)
        time_score = self._time_similarity(event1.start, event2.start)
        scores['time'] = time_score * 0.2  # 20% weight
        if time_score > 0.5:
            matching_fields.append('start_time')
        
        # Description similarity
        desc_score = self._text_similarity(event1.description, event2.description)
        scores['description'] = desc_score * 0.1  # 10% weight
        if desc_score > 0.7:
            matching_fields.append('description')
        
        # Source similarity (same source = higher chance of duplicate)
        source_score = 1.0 if event1.source == event2.source else 0.3
        scores['source'] = source_score * 0.1  # 10% weight
        
        # Calculate total similarity
        total_score = sum(scores.values())
        
        # Determine confidence level
        if total_score >= self.similarity_threshold_high:
            confidence = 'high'
            reason = f"High similarity ({total_score:.2f}) on {', '.join(matching_fields)}"
        elif total_score >= self.similarity_threshold_medium:
            confidence = 'medium'
            reason = f"Medium similarity ({total_score:.2f}) on {', '.join(matching_fields)}"
        else:
            confidence = 'low'
            reason = f"Low similarity ({total_score:.2f}) on {', '.join(matching_fields)}"
        
        return DuplicationMatch(
            event1=event1,
            event2=event2,
            similarity_score=total_score,
            matching_fields=matching_fields,
            confidence=confidence,
            reason=reason
        )
    
    def _text_similarity(self, text1: Optional[str], text2: Optional[str]) -> float:
        """Calculate similarity between two text strings"""
        if not text1 or not text2:
            return 0.0
        
        # Normalize texts
        norm1 = self._normalize_text(text1)
        norm2 = self._normalize_text(text2)
        
        if not norm1 or not norm2:
            return 0.0
        
        # Use difflib for sequence matching
        similarity = difflib.SequenceMatcher(None, norm1, norm2).ratio()
        
        # Boost score if one text contains the other
        if norm1 in norm2 or norm2 in norm1:
            similarity = max(similarity, 0.8)
        
        return similarity
    
    def _time_similarity(self, time1: Optional[datetime], time2: Optional[datetime]) -> float:
        """Calculate time proximity score"""
        if not time1 or not time2:
            return 0.0
        
        # Calculate time difference in hours
        time_diff = abs((time1 - time2).total_seconds()) / 3600
        
        # Score based on proximity (higher score for closer times)
        if time_diff == 0:
            return 1.0
        elif time_diff <= 1:  # Within 1 hour
            return 0.9
        elif time_diff <= 6:  # Within 6 hours
            return 0.7
        elif time_diff <= 24:  # Within 24 hours
            return 0.5
        elif time_diff <= 168:  # Within 1 week
            return 0.2
        else:
            return 0.0
    
    async def _find_proximity_matches(self, events: List[Event]) -> List[DuplicationMatch]:
        """Find events that are very close in time and location"""
        matches = []
        
        # Group events by date
        events_by_date = defaultdict(list)
        for event in events:
            if event.start:
                date_key = event.start.date()
                events_by_date[date_key].append(event)
        
        # Check events on same day
        for date, day_events in events_by_date.items():
            if len(day_events) < 2:
                continue
                
            for i, event1 in enumerate(day_events):
                for event2 in day_events[i+1:]:
                    # Check if events are very close in time and have similar venues
                    time_diff = abs((event1.start - event2.start).total_seconds()) / 3600
                    
                    if time_diff <= 2:  # Within 2 hours
                        venue_similarity = self._text_similarity(event1.venue, event2.venue)
                        
                        if venue_similarity > 0.6:  # Similar venue
                            score = 0.8 + (venue_similarity * 0.2) - (time_diff * 0.1)
                            
                            match = DuplicationMatch(
                                event1=event1,
                                event2=event2,
                                similarity_score=score,
                                matching_fields=['start_time', 'venue'],
                                confidence='medium',
                                reason=f'Events within {time_diff:.1f} hours at similar venues'
                            )
                            matches.append(match)
        
        log_info(f"Found {len(matches)} proximity matches")
        return matches
    
    async def _find_url_matches(self, events: List[Event]) -> List[DuplicationMatch]:
        """Find events with similar or identical URLs"""
        matches = []
        
        # Group events by domain
        events_by_domain = defaultdict(list)
        for event in events:
            if event.source_url:
                domain = self._extract_domain(str(event.source_url))
                events_by_domain[domain].append(event)
        
        # Check events from same domain with similar URLs
        for domain, domain_events in events_by_domain.items():
            if len(domain_events) < 2:
                continue
                
            for i, event1 in enumerate(domain_events):
                for event2 in domain_events[i+1:]:
                    url_similarity = self._url_similarity(str(event1.source_url), str(event2.source_url))
                    
                    if url_similarity > 0.8:
                        match = DuplicationMatch(
                            event1=event1,
                            event2=event2,
                            similarity_score=url_similarity,
                            matching_fields=['source_url'],
                            confidence='medium',
                            reason=f'Similar URLs from same domain ({url_similarity:.2f})'
                        )
                        matches.append(match)
        
        log_info(f"Found {len(matches)} URL matches")
        return matches
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc.lower()
        except:
            return ""
    
    def _url_similarity(self, url1: str, url2: str) -> float:
        """Calculate similarity between URLs"""
        if not url1 or not url2:
            return 0.0
        
        # Simple string similarity for URL paths
        return difflib.SequenceMatcher(None, url1, url2).ratio()
    
    def _deduplicate_matches(self, matches: List[DuplicationMatch]) -> List[DuplicationMatch]:
        """Remove duplicate match pairs"""
        seen_pairs = set()
        unique_matches = []
        
        for match in matches:
            # Create a consistent pair identifier
            event_ids = sorted([id(match.event1), id(match.event2)])
            pair_id = tuple(event_ids)
            
            if pair_id not in seen_pairs:
                seen_pairs.add(pair_id)
                unique_matches.append(match)
        
        return unique_matches
    
    def group_duplicates(self, matches: List[DuplicationMatch]) -> List[List[Event]]:
        """Group duplicate matches into clusters of related events"""
        if not matches:
            return []
        
        # Create graph of connected events
        event_connections = defaultdict(set)
        all_events = set()
        
        for match in matches:
            if match.confidence in ['high', 'medium']:  # Only use confident matches
                event1_id = id(match.event1)
                event2_id = id(match.event2)
                
                event_connections[event1_id].add(event2_id)
                event_connections[event2_id].add(event1_id)
                all_events.add(match.event1)
                all_events.add(match.event2)
        
        # Find connected components (groups of duplicates)
        visited = set()
        duplicate_groups = []
        
        for event in all_events:
            event_id = id(event)
            if event_id not in visited:
                group = []
                self._dfs_collect_group(event_id, event_connections, visited, group, all_events)
                if len(group) > 1:
                    duplicate_groups.append(group)
        
        log_info(f"Grouped duplicates into {len(duplicate_groups)} clusters")
        return duplicate_groups
    
    def _dfs_collect_group(self, event_id: int, connections: Dict, visited: Set, 
                          group: List[Event], all_events: Set[Event]):
        """Depth-first search to collect connected events in a group"""
        visited.add(event_id)
        
        # Find the event object by ID
        event = next((e for e in all_events if id(e) == event_id), None)
        if event:
            group.append(event)
        
        # Recursively visit connected events
        for connected_id in connections.get(event_id, []):
            if connected_id not in visited:
                self._dfs_collect_group(connected_id, connections, visited, group, all_events)
    
    def select_canonical_event(self, duplicate_group: List[Event]) -> Event:
        """Select the best event from a group of duplicates to keep as canonical"""
        if len(duplicate_group) == 1:
            return duplicate_group[0]
        
        # Scoring criteria for selecting canonical event
        best_event = None
        best_score = -1
        
        for event in duplicate_group:
            score = 0
            
            # Prefer events with more complete information
            if event.description:
                score += 2
            if event.venue:
                score += 2
            if event.address:
                score += 1
            if event.ticket_url:
                score += 1
            if event.image_url:
                score += 1
            if event.price_info:
                score += 1
            
            # Prefer events from reliable sources
            reliable_sources = ['moss.kommune.no', 'visitvestfold.com', 'moss-avis.no']
            if any(source in (event.source or '') for source in reliable_sources):
                score += 3
            
            # Prefer events with higher confidence scores (not in current Event model)
            # if hasattr(event, 'confidence_score') and event.confidence_score:
            #     score += event.confidence_score
            
            # Prefer more recent events (recently scraped)
            # This would require timestamp tracking in Event model
            
            if score > best_score:
                best_score = score
                best_event = event
        
        return best_event or duplicate_group[0]


# Global deduplicator instance
_deduplicator: Optional[EventDeduplicator] = None

def get_deduplicator() -> EventDeduplicator:
    """Get global deduplicator instance"""
    global _deduplicator
    if _deduplicator is None:
        _deduplicator = EventDeduplicator()
    return _deduplicator
