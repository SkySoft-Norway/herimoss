"""
Machine Learning Event Categorization for Moss Kulturkalender
Intelligent categorization and recommendation system            # Create enhanced event with predicted category
            enhanced_event = Event(
                id=event.id,
                title=event.title,
                description=event.description,
                start=event.start,
                end=getattr(event, 'end', None),
                venue=event.venue,
                address=getattr(event, 'address', None),
                price=getattr(event, 'price', None),
                url=getattr(event, 'url', None),
                source=event.source,
                source_type=event.source_type,
                first_seen=event.first_seen,
                last_seen=event.last_seen,
                category=prediction.category,  # Add predicted category
                source_url=getattr(event, 'source_url', None),
                status=getattr(event, 'status', 'upcoming')
            )
            
            # Add confidence score as a custom attribute (not part of the model)
            
            return enhanced_eventnts
"""

import asyncio
import json
import pickle
import re
from datetime import datetime, timedelta
from typing import List, Dict, Set, Tuple, Optional, Any
from pathlib import Path
from collections import defaultdict, Counter
from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import LabelEncoder

from models import Event
from logging_utils import log_info, log_warning, log_error


@dataclass
class CategoryPrediction:
    """Represents a category prediction with confidence"""
    category: str
    confidence: float
    features: List[str]
    reasoning: str


@dataclass
class EventRecommendation:
    """Represents a recommended event with score"""
    event: Event
    score: float
    reasons: List[str]


class NorwegianCulturalClassifier:
    """Machine learning classifier for Norwegian cultural events"""
    
    def __init__(self):
        self.categories = {
            'musikk': {
                'keywords': ['konsert', 'band', 'musikk', 'sang', 'kor', 'jazz', 'rock', 'pop', 'klassisk', 'festival'],
                'venues': ['kulturhus', 'scene', 'sal', 'amfi', 'festivalplass']
            },
            'teater': {
                'keywords': ['teater', 'forestilling', 'drama', 'komedie', 'skuespill', 'oppsetning', 'scene'],
                'venues': ['teater', 'scene', 'sal', 'studio']
            },
            'utstilling': {
                'keywords': ['utstilling', 'galleri', 'kunst', 'maleri', 'skulptur', 'fotografi', 'kunstner'],
                'venues': ['galleri', 'museum', 'kunstsenter', 'kulturhus']
            },
            'litteratur': {
                'keywords': ['forfatter', 'bok', 'litteratur', 'dikt', 'lesning', 'bokbad', 'bibliotek'],
                'venues': ['bibliotek', 'bokhandel', 'kulturhus']
            },
            'dans': {
                'keywords': ['dans', 'ballett', 'koreografi', 'danseteater', 'bevegelse'],
                'venues': ['dansestudio', 'scene', 'kulturhus']
            },
            'film': {
                'keywords': ['film', 'kino', 'visning', 'dokumentar', 'premiere', 'filmfestival'],
                'venues': ['kino', 'kulturhus', 'bibliotek']
            },
            'familie': {
                'keywords': ['barn', 'familie', 'barneforestilling', 'familieaktivitet', 'workshop'],
                'venues': ['kulturhus', 'bibliotek', 'museum']
            },
            'workshop': {
                'keywords': ['workshop', 'kurs', 'seminar', 'læring', 'kreativ', 'håndverk'],
                'venues': ['kulturhus', 'bibliotek', 'museum', 'verksted']
            },
            'festival': {
                'keywords': ['festival', 'arrangement', 'helg', 'flere dager', 'program'],
                'venues': ['festivalplass', 'park', 'sentrum']
            },
            'foredrag': {
                'keywords': ['foredrag', 'presentasjon', 'historie', 'forskning', 'kunnskap'],
                'venues': ['bibliotek', 'museum', 'kulturhus', 'sal']
            }
        }
        
        self.vectorizer = None
        self.classifier = None
        self.label_encoder = None
        self.is_trained = False
        
        # Norwegian stopwords for better text processing
        self.norwegian_stopwords = {
            'og', 'i', 'på', 'med', 'av', 'til', 'for', 'om', 'ved', 'fra',
            'det', 'den', 'de', 'et', 'en', 'er', 'var', 'har', 'ikke',
            'som', 'vil', 'kan', 'man', 'skal', 'får', 'dit', 'her', 'hvor'
        }
    
    async def initialize(self):
        """Initialize the ML categorizer"""
        log_info("🤖 Initializing ML categorizer...")
        
        # Try to load existing model
        if self.load_model():
            log_info("✅ Loaded existing ML model")
        else:
            log_info("No existing model found, will train on first use")
    
    async def categorize_event(self, event: Event) -> Event:
        """Categorize an event and return enhanced version"""
        try:
            # Get prediction
            prediction = await self.classify_event(event)
            
            # Create enhanced event
            enhanced_event = Event(
                id=event.id,
                title=event.title,
                description=event.description,
                start=event.start,
                end=getattr(event, 'end', None),
                venue=event.venue,
                address=getattr(event, 'address', None),
                price=getattr(event, 'price', None),
                url=getattr(event, 'url', None),
                source=event.source,
                source_type=event.source_type,
                first_seen=event.first_seen,
                last_seen=event.last_seen,
                category=prediction.category,  # Add predicted category
                source_url=getattr(event, 'source_url', None),
                status=getattr(event, 'status', 'upcoming')
            )
            # (confidence_score removed: not a field of Event)
            return enhanced_event
            
        except Exception as e:
            log_error("ml", f"Event categorization failed: {e}")
            return event
    
    def get_filter(self) -> 'SmartEventFilter':
        """Get the event filter instance"""
        return get_filter()
    
    async def get_recommendations(self, event: Event, limit: int = 5) -> List[Event]:
        """Get event recommendations based on similar events"""
        try:
            # This is a simplified recommendation system
            # In a full implementation, you would use collaborative filtering or content-based recommendations
            
            from database import get_database
            db = await get_database()
            
            # Get events from same category
            prediction = await self.classify_event(event)
            
            # Get recent events from database (placeholder implementation)
            similar_events = await db.get_events(limit=limit * 2)
            
            # Filter to same category if possible
            category_events = []
            for existing_event in similar_events:
                if hasattr(existing_event, 'category') and existing_event.category == prediction.category:
                    category_events.append(existing_event)
            # Return up to limit recommendations
            return category_events[:limit]
            
        except Exception as e:
            log_error("ml", f"Recommendations failed: {e}")
            return []
    
    def _extract_features(self, event: Event) -> str:
        """Extract text features from event for classification"""
        features = []
        
        # Title features (most important)
        if event.title:
            features.append(event.title.lower())
        
        # Description features
        if event.description:
            # Clean description
            desc_clean = re.sub(r'[^\w\s]', ' ', event.description.lower())
            desc_clean = ' '.join([word for word in desc_clean.split() 
                                 if word not in self.norwegian_stopwords and len(word) > 2])
            features.append(desc_clean)
        
        # Venue features
        if event.venue:
            venue_clean = event.venue.lower()
            features.append(venue_clean)
        
        # Time-based features - support both start_time and start fields
        start_dt = getattr(event, 'start', None)
        if start_dt:
            # Weekend vs weekday
            is_weekend = start_dt.weekday() >= 5
            features.append('helg' if is_weekend else 'hverdag')
            
            # Time of day
            hour = start_dt.hour
            if hour < 12:
                features.append('morgen')
            elif hour < 17:
                features.append('ettermiddag')
            else:
                features.append('kveld')
        
        # Price indicators - support both price_info and price fields
        price_field = getattr(event, 'price', None)
        if price_field:
            if 'gratis' in price_field.lower() or '0' in price_field:
                features.append('gratis')
            else:
                features.append('kostnad')
        
        return ' '.join(features)
    
    def _rule_based_classification(self, event: Event) -> Optional[CategoryPrediction]:
        """Rule-based classification using keyword matching"""
        text = self._extract_features(event).lower()
        scores = {}
        
        for category, data in self.categories.items():
            score = 0
            matched_keywords = []
            
            # Check keywords in title (higher weight)
            if event.title:
                title_lower = event.title.lower()
                for keyword in data['keywords']:
                    if keyword in title_lower:
                        score += 3
                        matched_keywords.append(keyword)
            
            # Check keywords in description
            if event.description:
                desc_lower = event.description.lower()
                for keyword in data['keywords']:
                    if keyword in desc_lower:
                        score += 1
                        matched_keywords.append(keyword)
            
            # Check venue types
            if event.venue:
                venue_lower = event.venue.lower()
                for venue_type in data['venues']:
                    if venue_type in venue_lower:
                        score += 2
                        matched_keywords.append(venue_type)
            
            if score > 0:
                scores[category] = {
                    'score': score,
                    'keywords': matched_keywords
                }
        
        if not scores:
            return None
        
        # Get best category
        best_category = max(scores.keys(), key=lambda k: scores[k]['score'])
        confidence = min(scores[best_category]['score'] / 10.0, 1.0)  # Normalize to 0-1
        
        return CategoryPrediction(
            category=best_category,
            confidence=confidence,
            features=scores[best_category]['keywords'],
            reasoning=f"Matched keywords: {', '.join(scores[best_category]['keywords'])}"
        )
    
    async def train_classifier(self, events: List[Event]) -> bool:
        """Train ML classifier on existing categorized events"""
        log_info("🤖 Training machine learning classifier...")
        
        # Prepare training data
        training_texts = []
        training_labels = []
        
        for event in events:
            if hasattr(event, 'category') and event.category:
                text = self._extract_features(event)
                training_texts.append(text)
                training_labels.append(event.category)
        
        if len(training_texts) < 10:
            log_warning("Not enough training data for ML classifier, using rule-based only")
            return False
        
        try:
            # Initialize components
            self.vectorizer = TfidfVectorizer(
                max_features=1000,
                ngram_range=(1, 2),
                stop_words=list(self.norwegian_stopwords)
            )
            
            self.label_encoder = LabelEncoder()
            self.classifier = MultinomialNB(alpha=0.1)
            
            # Transform data
            X = self.vectorizer.fit_transform(training_texts)
            y = self.label_encoder.fit_transform(training_labels)
            
            # Train classifier
            self.classifier.fit(X, y)
            self.is_trained = True
            
            log_info(f"✅ ML classifier trained on {len(training_texts)} events")
            return True
            
        except Exception as e:
            log_error("ml", f"Failed to train classifier: {e}")
            return False
    
    async def classify_event(self, event: Event) -> CategoryPrediction:
        """Classify event using hybrid approach (rules + ML)"""
        
        # First try rule-based classification
        rule_prediction = self._rule_based_classification(event)
        
        # If ML classifier is trained, use it too
        if self.is_trained and self.vectorizer and self.classifier:
            try:
                text = self._extract_features(event)
                X = self.vectorizer.transform([text])
                
                # Get prediction probabilities
                proba = self.classifier.predict_proba(X)[0]
                best_idx = np.argmax(proba)
                confidence = proba[best_idx]
                
                ml_category = self.label_encoder.inverse_transform([best_idx])[0]
                
                # Combine rule-based and ML predictions
                if rule_prediction and rule_prediction.confidence > 0.7:
                    # Trust rule-based if high confidence
                    return rule_prediction
                elif confidence > 0.6:
                    # Use ML if confident
                    return CategoryPrediction(
                        category=ml_category,
                        confidence=confidence,
                        features=['ml_prediction'],
                        reasoning=f"ML prediction with {confidence:.2f} confidence"
                    )
                elif rule_prediction:
                    # Fall back to rule-based
                    return rule_prediction
                else:
                    # Low confidence ML prediction
                    return CategoryPrediction(
                        category=ml_category,
                        confidence=confidence,
                        features=['ml_prediction'],
                        reasoning=f"Low confidence ML prediction ({confidence:.2f})"
                    )
                    
            except Exception as e:
                log_error("ml", f"ML classification failed: {e}")
                # Fall back to rule-based
                if rule_prediction:
                    return rule_prediction
        
        # Return rule-based or default
        if rule_prediction:
            return rule_prediction
        else:
            return CategoryPrediction(
                category='arrangement',
                confidence=0.1,
                features=[],
                reasoning="No matching keywords found, using default category"
            )
    
    def save_model(self, path: str = "ml_models"):
        """Save trained model to disk"""
        if not self.is_trained:
            return False
        
        model_dir = Path(path)
        model_dir.mkdir(exist_ok=True)
        
        try:
            # Save components
            with open(model_dir / "vectorizer.pkl", "wb") as f:
                pickle.dump(self.vectorizer, f)
            
            with open(model_dir / "classifier.pkl", "wb") as f:
                pickle.dump(self.classifier, f)
            
            with open(model_dir / "label_encoder.pkl", "wb") as f:
                pickle.dump(self.label_encoder, f)
            
            log_info(f"✅ ML model saved to {model_dir}")
            return True
            
        except Exception as e:
            log_error("ml", f"Failed to save model: {e}")
            return False
    
    def load_model(self, path: str = "ml_models") -> bool:
        """Load trained model from disk"""
        model_dir = Path(path)
        
        if not model_dir.exists():
            return False
        
        try:
            # Load components
            with open(model_dir / "vectorizer.pkl", "rb") as f:
                self.vectorizer = pickle.load(f)
            
            with open(model_dir / "classifier.pkl", "rb") as f:
                self.classifier = pickle.load(f)
            
            with open(model_dir / "label_encoder.pkl", "rb") as f:
                self.label_encoder = pickle.load(f)
            
            self.is_trained = True
            log_info(f"✅ ML model loaded from {model_dir}")
            return True
            
        except Exception as e:
            log_error("ml", f"Failed to load model: {e}")
            return False


class SmartEventFilter:
    """Intelligent event filtering and recommendation system"""
    
    def __init__(self):
        self.user_preferences = {}
        self.event_history = {}
        
    def set_user_preferences(self, preferences: Dict[str, Any]):
        """Set user preferences for filtering"""
        self.user_preferences = preferences
    
    async def should_include_event(self, event: Event) -> bool:
        """Determine if an event should be included based on quality and basic filters"""
        # Basic quality checks
        if not event.title or len(event.title.strip()) < 3:
            return False
        
        # Check for spam indicators
        spam_keywords = ['spam', 'reklame', 'tilbud', 'salg', 'kjøp nå']
        if any(keyword in event.title.lower() for keyword in spam_keywords):
            return False
        
        # Check if event has minimum required information
        has_venue = event.venue and len(event.venue.strip()) > 0
        has_time = hasattr(event, 'start') and event.start
        
        if not (has_venue or has_time):
            return False
        
        # Check if event is not too far in the past
        from datetime import datetime, timedelta
        event_date = getattr(event, 'start', None)
        if event_date and event_date < datetime.now() - timedelta(days=7):
            return False
        
        return True
    
    async def filter_events(self, events: List[Event], filters: Dict[str, Any]) -> List[Event]:
        """Apply intelligent filtering to events"""
        filtered = events.copy()
        
        # Date range filtering
        if 'start_date' in filters:
            start_date = filters['start_date']
            filtered = [e for e in filtered if e.start and e.start >= start_date]
        
        if 'end_date' in filters:
            end_date = filters['end_date']
            filtered = [e for e in filtered if e.start and e.start <= end_date]
        
        # Category filtering
        if 'categories' in filters:
            categories = filters['categories']
            filtered = [e for e in filtered if getattr(e, 'category', None) in categories]
        
        # Price filtering
        if 'price_range' in filters:
            price_range = filters['price_range']
            filtered = await self._filter_by_price(filtered, price_range)
        
        # Location filtering
        if 'max_distance' in filters and 'user_location' in filters:
            filtered = await self._filter_by_distance(filtered, filters['user_location'], filters['max_distance'])
        
        # Time of day filtering
        if 'time_preference' in filters:
            filtered = await self._filter_by_time(filtered, filters['time_preference'])
        
        # Quality filtering (remove low-quality events)
        filtered = await self._filter_by_quality(filtered)
        
        return filtered
    
    async def _filter_by_price(self, events: List[Event], price_range: Tuple[float, float]) -> List[Event]:
        """Filter events by price range"""
        min_price, max_price = price_range
        filtered = []
        
        for event in events:
            if not event.price:
                # No price info - include if min_price is 0 (free events)
                if min_price <= 0:
                    filtered.append(event)
                continue
            
            price_text = event.price.lower()
            
            # Check for free events
            if 'gratis' in price_text or 'free' in price_text:
                if min_price <= 0:
                    filtered.append(event)
                continue
            
            # Extract price numbers
            import re
            prices = re.findall(r'\d+', price_text)
            if prices:
                price = float(prices[0])
                if min_price <= price <= max_price:
                    filtered.append(event)
        
        return filtered
    
    async def _filter_by_distance(self, events: List[Event], user_location: Tuple[float, float], max_distance: float) -> List[Event]:
        """Filter events by distance from user location"""
        # This would require geocoding and distance calculation
        # For now, return all events (placeholder)
        return events
    
    async def _filter_by_time(self, events: List[Event], time_preference: str) -> List[Event]:
        """Filter events by time of day preference"""
        filtered = []
        
        for event in events:
            if not event.start:
                continue
            
            hour = event.start.hour
            
            if time_preference == 'morning' and 6 <= hour < 12:
                filtered.append(event)
            elif time_preference == 'afternoon' and 12 <= hour < 17:
                filtered.append(event)
            elif time_preference == 'evening' and 17 <= hour < 23:
                filtered.append(event)
            elif time_preference == 'any':
                filtered.append(event)
        
        return filtered
    
    async def _filter_by_quality(self, events: List[Event]) -> List[Event]:
        """Filter out low-quality events"""
        filtered = []
        
        for event in events:
            quality_score = 0
            
            # Check for complete information
            if event.title and len(event.title) > 5:
                quality_score += 1
            if event.description and len(event.description) > 20:
                quality_score += 1
            if event.venue:
                quality_score += 1
            if event.start:
                quality_score += 1
            
            # Check for spam indicators
            if event.title:
                spam_words = ['spam', 'reklame', 'tilbud', 'salg']
                if any(word in event.title.lower() for word in spam_words):
                    quality_score -= 2
            
            # Include events with quality score >= 2
            if quality_score >= 2:
                filtered.append(event)
        
        return filtered
    
    async def recommend_events(self, user_id: str, available_events: List[Event], limit: int = 10) -> List[EventRecommendation]:
        """Generate personalized event recommendations"""
        recommendations = []
        
        # Get user preferences and history
        preferences = self.user_preferences.get(user_id, {})
        history = self.event_history.get(user_id, [])
        
        for event in available_events:
            score = await self._calculate_recommendation_score(event, preferences, history)
            
            if score > 0.1:  # Minimum threshold
                reasons = await self._generate_recommendation_reasons(event, preferences, history, score)
                
                recommendation = EventRecommendation(
                    event=event,
                    score=score,
                    reasons=reasons
                )
                recommendations.append(recommendation)
        
        # Sort by score and return top recommendations
        recommendations.sort(key=lambda r: r.score, reverse=True)
        return recommendations[:limit]
    
    async def _calculate_recommendation_score(self, event: Event, preferences: Dict, history: List) -> float:
        """Calculate recommendation score for an event"""
        score = 0.5  # Base score
        
        # Category preference
        if 'preferred_categories' in preferences:
            event_category = getattr(event, 'category', None)
            if event_category in preferences['preferred_categories']:
                score += 0.3
        
        # Time preference
        if 'preferred_times' in preferences and event.start:
            hour = event.start.hour
            if hour in preferences['preferred_times']:
                score += 0.2
        
        # Venue preference
        if 'preferred_venues' in preferences and event.venue:
            for venue in preferences['preferred_venues']:
                if venue.lower() in event.venue.lower():
                    score += 0.2
                    break
        
        # Price preference
        if 'price_sensitivity' in preferences:
            if preferences['price_sensitivity'] == 'free' and event.price:
                if 'gratis' in event.price.lower() or '0' in event.price:
                    score += 0.3
                else:
                    score -= 0.2
        
        # Avoid events similar to recent history
        for hist_event in history[-10:]:  # Last 10 events
            if hist_event.get('title') == event.title:
                score -= 0.5  # Avoid exact duplicates
            elif hist_event.get('venue') == event.venue:
                score -= 0.1  # Slight penalty for same venue
        
        return max(0, min(1, score))  # Clamp to 0-1
    
    async def _generate_recommendation_reasons(self, event: Event, preferences: Dict, history: List, score: float) -> List[str]:
        """Generate human-readable reasons for recommendation"""
        reasons = []
        
        if score > 0.8:
            reasons.append("Perfekt match for dine preferanser")
        elif score > 0.6:
            reasons.append("God match for dine interesser")
        
        if 'preferred_categories' in preferences:
            event_category = getattr(event, 'category', None)
            if event_category in preferences['preferred_categories']:
                reasons.append(f"Du liker {event_category} arrangementer")
        
        if event.price and 'gratis' in event.price.lower():
            reasons.append("Gratis arrangement")
        
        if event.start and event.start.weekday() >= 5:
            reasons.append("Helgarrangement")
        
        return reasons


class PerformanceOptimizer:
    """Performance optimization and caching system"""
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = {}
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'processing_times': []
        }
    
    def cache_result(self, key: str, result: Any, ttl_seconds: int = 3600):
        """Cache a result with TTL"""
        self.cache[key] = result
        self.cache_ttl[key] = datetime.now() + timedelta(seconds=ttl_seconds)
    
    def get_cached_result(self, key: str) -> Optional[Any]:
        """Get cached result if valid"""
        if key not in self.cache:
            self.stats['cache_misses'] += 1
            return None
        
        if datetime.now() > self.cache_ttl[key]:
            # Expired
            del self.cache[key]
            del self.cache_ttl[key]
            self.stats['cache_misses'] += 1
            return None
        
        self.stats['cache_hits'] += 1
        return self.cache[key]
    
    def cleanup_cache(self):
        """Remove expired cache entries"""
        now = datetime.now()
        expired_keys = [k for k, ttl in self.cache_ttl.items() if now > ttl]
        
        for key in expired_keys:
            del self.cache[key]
            del self.cache_ttl[key]
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        total_requests = self.stats['cache_hits'] + self.stats['cache_misses']
        hit_rate = self.stats['cache_hits'] / max(total_requests, 1)
        
        return {
            'cache_entries': len(self.cache),
            'cache_hits': self.stats['cache_hits'],
            'cache_misses': self.stats['cache_misses'],
            'hit_rate': hit_rate,
            'avg_processing_time': np.mean(self.stats['processing_times']) if self.stats['processing_times'] else 0
        }


# Global instances
_classifier: Optional[NorwegianCulturalClassifier] = None
_filter: Optional[SmartEventFilter] = None
_optimizer: Optional[PerformanceOptimizer] = None

def get_ml_categorizer() -> NorwegianCulturalClassifier:
    """Get global ML categorizer instance"""
    global _classifier
    if _classifier is None:
        _classifier = NorwegianCulturalClassifier()
    return _classifier

def get_classifier() -> NorwegianCulturalClassifier:
    """Get global classifier instance (alias for compatibility)"""
    return get_ml_categorizer()

def get_filter() -> SmartEventFilter:
    """Get global filter instance"""
    global _filter
    if _filter is None:
        _filter = SmartEventFilter()
    return _filter

def get_optimizer() -> PerformanceOptimizer:
    """Get global optimizer instance"""
    global _optimizer
    if _optimizer is None:
        _optimizer = PerformanceOptimizer()
    return _optimizer
