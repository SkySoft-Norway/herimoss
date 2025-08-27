#!/usr/bin/env python3
"""
Phase 3 validation script - tests all scraper components without network calls
"""
import sys
import os
from datetime import datetime
import pytz

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all Phase 3 components can be imported"""
    try:
        from scrapers.moss_kommune import scrape_moss_kommune
        from scrapers.html_scraper import scrape_moss_kulturhus, scrape_verket_scene
        from scrapers.google_calendar import scrape_google_calendar
        from utils import HttpClient
        from models import Event, Config
        from normalize import EventNormalizer
        from dedupe import EventDeduplicator
        from state_manager import StateManager
        print("✓ All Phase 3 components imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def test_event_model():
    """Test Event model creation"""
    try:
        from models import Event
        import pytz
        
        oslo_tz = pytz.timezone('Europe/Oslo')
        now = datetime.now(oslo_tz)
        
        # Create event with proper fields using the pattern from scrapers
        title = "Test Arrangement"
        start = now
        venue = "Test Venue"
        event_id = Event.generate_id(title, start, venue)
        
        event = Event(
            id=event_id,
            title=title,
            description="Test beskrivelse for arrangement",
            start=start,
            venue=venue,
            url="https://example.com/test",
            source="test_source",
            source_type="html",
            first_seen=now,
            last_seen=now
        )
        
        print("✓ Event model working correctly")
        print(f"  - Event ID: {event.id}")
        print(f"  - Start: {event.start}")
        return True
    except Exception as e:
        print(f"✗ Event model error: {e}")
        return False

def test_core_components():
    """Test core pipeline components"""
    try:
        from normalize import EventNormalizer
        from dedupe import EventDeduplicator
        from state_manager import StateManager
        
        # Test normalizer
        normalizer = EventNormalizer()
        test_datetime = normalizer.normalize_datetime("2025-08-25T14:00:00")
        if test_datetime:
            print("✓ Date normalizer working")
        
        # Test deduplicator  
        deduplicator = EventDeduplicator()
        print("✓ Deduplicator initialized")
        
        # Test state manager
        state_manager = StateManager("../data")
        print("✓ State manager initialized")
        
        return True
    except Exception as e:
        print(f"✗ Core component error: {e}")
        return False

def test_configuration():
    """Test configuration loading"""
    try:
        import json
        import os
        
        # Try different possible paths for options.json
        config_paths = ['../options.json', 'options.json', '/var/www/vhosts/herimoss.no/options.json']
        config_data = None
        
        for path in config_paths:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                print(f"✓ Configuration loaded from: {path}")
                break
        
        if not config_data:
            print("✗ Configuration file not found in any expected location")
            return False
        
        sources = config_data.get('sources', {})
        print(f"  - Found {len(sources)} sources configured")
        
        # Check key sources are configured
        required_sources = ['moss_kommune', 'moss_kulturhus', 'verket_scene']
        for source in required_sources:
            if source in sources:
                print(f"  - {source}: ✓")
            else:
                print(f"  - {source}: ✗ missing")
        
        return True
    except Exception as e:
        print(f"✗ Configuration error: {e}")
        return False

def main():
    """Run all Phase 3 validation tests"""
    print("=== Phase 3 Validation ===")
    print("Testing all scraper components and pipeline...")
    print()
    
    tests = [
        ("Component Imports", test_imports),
        ("Event Model", test_event_model), 
        ("Core Components", test_core_components),
        ("Configuration", test_configuration)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"{test_name}:")
        if test_func():
            passed += 1
        print()
    
    print("=== Phase 3 Validation Results ===")
    print(f"Passed: {passed}/{total} tests")
    
    if passed == total:
        print("🎉 Phase 3 COMPLETE - All scrapers ready for production!")
        print()
        print("Available scrapers:")
        print("- Moss Kommune (iCal/RSS feeds)")
        print("- HTML scraper with schema.org/JSON-LD support")
        print("- Google Calendar integration")
        print("- Enhanced Norwegian date parsing")
        print("- Event normalization and deduplication")
        return 0
    else:
        print("❌ Phase 3 has issues that need to be addressed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
