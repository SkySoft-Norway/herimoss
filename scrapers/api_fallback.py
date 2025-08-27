"""
API error handling and fallback strategies for external service integrations.
Provides robust error handling, retry logic, and graceful degradation.
"""
import asyncio
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
import pytz
from models import Event
from utils import HttpClient
from logging_utils import log_info, log_warning, log_error


@dataclass
class APIStatus:
    """Track API service status and health."""
    service_name: str
    is_available: bool = True
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    consecutive_failures: int = 0
    next_retry_after: Optional[datetime] = None
    error_message: Optional[str] = None


class APIManager:
    """Manages multiple API services with fallback strategies."""
    
    def __init__(self):
        self.services: Dict[str, APIStatus] = {}
        self.oslo_tz = pytz.timezone('Europe/Oslo')
        
        # Circuit breaker settings
        self.max_consecutive_failures = 3
        self.backoff_minutes = [5, 15, 60]  # Progressive backoff
        
    def register_service(self, service_name: str):
        """Register a new API service for monitoring."""
        if service_name not in self.services:
            self.services[service_name] = APIStatus(service_name=service_name)
    
    def is_service_available(self, service_name: str) -> bool:
        """Check if a service is available for requests."""
        if service_name not in self.services:
            self.register_service(service_name)
            return True
        
        status = self.services[service_name]
        
        # If service is marked as unavailable, check if retry time has passed
        if not status.is_available and status.next_retry_after:
            if datetime.now(self.oslo_tz) >= status.next_retry_after:
                # Reset service for retry
                status.is_available = True
                status.next_retry_after = None
                log_info(f"Service {service_name} available for retry")
        
        return status.is_available
    
    def record_success(self, service_name: str):
        """Record successful API call."""
        if service_name not in self.services:
            self.register_service(service_name)
        
        status = self.services[service_name]
        status.is_available = True
        status.last_success = datetime.now(self.oslo_tz)
        status.consecutive_failures = 0
        status.next_retry_after = None
        status.error_message = None
    
    def record_failure(self, service_name: str, error_message: str):
        """Record failed API call and implement circuit breaker."""
        if service_name not in self.services:
            self.register_service(service_name)
        
        status = self.services[service_name]
        status.last_failure = datetime.now(self.oslo_tz)
        status.consecutive_failures += 1
        status.error_message = error_message
        
        # Implement circuit breaker
        if status.consecutive_failures >= self.max_consecutive_failures:
            status.is_available = False
            
            # Calculate backoff time
            backoff_index = min(status.consecutive_failures - self.max_consecutive_failures, 
                              len(self.backoff_minutes) - 1)
            backoff_minutes = self.backoff_minutes[backoff_index]
            
            status.next_retry_after = datetime.now(self.oslo_tz) + timedelta(minutes=backoff_minutes)
            
            log_warning(f"Service {service_name} circuit breaker activated. "
                       f"Retry after {backoff_minutes} minutes")
    
    def get_service_status(self, service_name: str) -> APIStatus:
        """Get current status of a service."""
        if service_name not in self.services:
            self.register_service(service_name)
        return self.services[service_name]
    
    def get_all_statuses(self) -> Dict[str, APIStatus]:
        """Get status of all registered services."""
        return self.services.copy()


# Global API manager instance
api_manager = APIManager()


async def call_api_with_fallback(
    service_name: str,
    api_function: Callable,
    config: dict,
    client: HttpClient,
    fallback_function: Optional[Callable] = None
) -> List[Event]:
    """
    Call an API function with error handling and fallback.
    
    Args:
        service_name: Name of the API service (e.g., 'meetup', 'bandsintown')
        api_function: The async function to call for the primary API
        config: Configuration dict for the API
        client: HTTP client instance
        fallback_function: Optional fallback function if primary fails
    
    Returns:
        List of Event objects, empty list if all attempts fail
    """
    # Check if service is available
    if not api_manager.is_service_available(service_name):
        status = api_manager.get_service_status(service_name)
        log_warning(f"Service {service_name} is unavailable until {status.next_retry_after}. "
                   f"Last error: {status.error_message}")
        
        # Try fallback if available
        if fallback_function:
            log_info(f"Attempting fallback for {service_name}")
            try:
                events = await fallback_function(config, client)
                return events
            except Exception as e:
                log_error(f"Fallback for {service_name} also failed: {e}")
        
        return []
    
    # Attempt primary API call
    try:
        log_info(f"Calling primary API for {service_name}")
        events = await api_function(config, client)
        
        # Record success
        api_manager.record_success(service_name)
        log_info(f"API call to {service_name} successful: {len(events)} events")
        
        return events
        
    except Exception as e:
        error_msg = str(e)
        log_error(f"API call to {service_name} failed: {error_msg}")
        
        # Record failure
        api_manager.record_failure(service_name, error_msg)
        
        # Try fallback if available
        if fallback_function:
            log_info(f"Attempting fallback for {service_name}")
            try:
                events = await fallback_function(config, client)
                log_info(f"Fallback for {service_name} successful: {len(events)} events")
                return events
            except Exception as fallback_error:
                log_error(f"Fallback for {service_name} also failed: {fallback_error}")
        
        return []


async def validate_api_keys() -> Dict[str, bool]:
    """
    Validate that required API keys are available.
    
    Returns:
        Dict mapping service names to whether their API key is configured
    """
    api_keys = {
        'meetup': bool(os.getenv('MEETUP_API_KEY')),
        'bandsintown': bool(os.getenv('BANDSINTOWN_APP_ID')),
        'songkick': bool(os.getenv('SONGKICK_API_KEY'))
    }
    
    log_info("API key validation:")
    for service, has_key in api_keys.items():
        status = "✓ configured" if has_key else "✗ missing"
        log_info(f"  {service}: {status}")
    
    return api_keys


async def test_api_connectivity(client: HttpClient) -> Dict[str, bool]:
    """
    Test connectivity to all API services.
    
    Returns:
        Dict mapping service names to whether they're reachable
    """
    connectivity = {}
    
    # Test Meetup API
    try:
        response = await client.get("https://api.meetup.com", timeout=5)
        connectivity['meetup'] = response.status_code < 500
    except Exception:
        connectivity['meetup'] = False
    
    # Test Bandsintown API
    try:
        response = await client.get("https://rest.bandsintown.com", timeout=5)
        connectivity['bandsintown'] = response.status_code < 500
    except Exception:
        connectivity['bandsintown'] = False
    
    # Test Songkick API
    try:
        response = await client.get("https://api.songkick.com", timeout=5)
        connectivity['songkick'] = response.status_code < 500
    except Exception:
        connectivity['songkick'] = False
    
    log_info("API connectivity test:")
    for service, is_reachable in connectivity.items():
        status = "✓ reachable" if is_reachable else "✗ unreachable"
        log_info(f"  {service}: {status}")
    
    return connectivity


class FallbackEventScraper:
    """Fallback scraper that uses cached data or alternative sources."""
    
    def __init__(self, cache_dir: str = "../data/api_cache"):
        self.cache_dir = cache_dir
        self.oslo_tz = pytz.timezone('Europe/Oslo')
    
    async def get_cached_events(self, service_name: str, max_age_hours: int = 24) -> List[Event]:
        """
        Get cached events from a previous successful API call.
        
        Args:
            service_name: Name of the service to get cached events for
            max_age_hours: Maximum age of cache to consider valid
        
        Returns:
            List of cached Event objects, empty if no valid cache
        """
        try:
            import json
            import os
            
            cache_file = os.path.join(self.cache_dir, f"{service_name}_events.json")
            
            if not os.path.exists(cache_file):
                return []
            
            # Check cache age
            cache_time = datetime.fromtimestamp(os.path.getmtime(cache_file), tz=self.oslo_tz)
            age_hours = (datetime.now(self.oslo_tz) - cache_time).total_seconds() / 3600
            
            if age_hours > max_age_hours:
                log_info(f"Cache for {service_name} too old ({age_hours:.1f}h), skipping")
                return []
            
            # Load cached events
            with open(cache_file, 'r', encoding='utf-8') as f:
                events_data = json.load(f)
            
            # Convert back to Event objects (simplified - would need full deserialization)
            log_info(f"Using cached events for {service_name} ({len(events_data)} events)")
            
            return []  # Placeholder - would implement full deserialization
            
        except Exception as e:
            log_warning(f"Failed to load cached events for {service_name}: {e}")
            return []


# Create global fallback scraper instance
fallback_scraper = FallbackEventScraper()
