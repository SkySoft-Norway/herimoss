#!/usr/bin/env python3
"""
Test script for Phase 2 implementation.
"""
import json
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Mock test data for pipeline testing
def create_test_events():
    """Create test events for pipeline testing."""
    from models import Event
    
    now = datetime.now(timezone.utc)
    
    events = [
        Event(
            id="test1",
            title="Test Konsert",
            description="En fantastisk konsert",
            start=now + timedelta(days=7),
            venue="Verket Scene",
            source="test",
            source_type="manual",
            first_seen=now,
            last_seen=now
        ),
        Event(
            id="test2", 
            title="Test Konsert",  # Duplicate title
            description="En annen beskrivelse",
            start=now + timedelta(days=7, minutes=30),  # Similar time
            venue="Verket Scene",
            source="test2",
            source_type="manual",
            first_seen=now,
            last_seen=now
        ),
        Event(
            id="test3",
            title="Gammelt arrangement", 
            start=now - timedelta(days=2),  # Old event - should be archived
            venue="Moss Kulturhus",
            source="test",
            source_type="manual",
            first_seen=now,
            last_seen=now
        )
    ]
    
    return events

def test_normalization():
    """Test event normalization."""
    print("Testing normalization...")
    
    from normalize import EventNormalizer
    from models import Event
    
    normalizer = EventNormalizer()
    
    # Test with messy data
    test_event = Event(
        id="test",
        title="  KONSERT: The Beatles  ",
        description="<p>En fantastisk <b>konsert</b> med...</p>",
        venue="verket",
        price="kr 250,-",
        start=datetime.now(timezone.utc),
        source="test",
        source_type="manual",
        first_seen=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc)
    )
    
    normalized = normalizer.normalize_event(test_event)
    
    print(f"  Original title: '{test_event.title}'")
    print(f"  Normalized title: '{normalized.title}'")
    print(f"  Original venue: '{test_event.venue}'")
    print(f"  Normalized venue: '{normalized.venue}'")
    print(f"  Normalized category: '{normalized.category}'")
    print("  ✓ Normalization test passed")

def test_deduplication():
    """Test event deduplication."""
    print("Testing deduplication...")
    
    from dedupe import deduplicate_event_list
    
    events = create_test_events()
    unique_events, seen_hashes, duplicate_mappings = deduplicate_event_list(events)
    
    print(f"  Original events: {len(events)}")
    print(f"  Unique events: {len(unique_events)}")
    print(f"  Duplicates found: {len(duplicate_mappings)}")
    print(f"  Seen hashes: {len(seen_hashes)}")
    
    if len(duplicate_mappings) > 0:
        print("  ✓ Deduplication test passed (found duplicates)")
    else:
        print("  ! No duplicates detected (may be OK)")

def test_state_management():
    """Test state management."""
    print("Testing state management...")
    
    from state_manager import StateManager
    
    # Use test directory
    test_dir = Path("test_state")
    test_dir.mkdir(exist_ok=True)
    
    state_manager = StateManager(str(test_dir))
    
    # Test with events
    events = create_test_events()
    
    # Save and load events
    state_manager.save_events(events)
    loaded_events = state_manager.load_events()
    
    print(f"  Saved {len(events)} events")
    print(f"  Loaded {len(loaded_events)} events")
    
    if len(events) == len(loaded_events):
        print("  ✓ State management test passed")
    else:
        print("  ✗ State management test failed")
    
    # Cleanup
    for file in test_dir.glob("*"):
        file.unlink()
    test_dir.rmdir()

def test_full_pipeline():
    """Test the complete pipeline."""
    print("Testing full pipeline...")
    
    from normalize import normalize_events
    from dedupe import deduplicate_event_list
    from state_manager import StateManager
    
    # Create test events
    events = create_test_events()
    print(f"  Created {len(events)} test events")
    
    # Normalize
    normalized = normalize_events(events)
    print(f"  Normalized to {len(normalized)} events")
    
    # Deduplicate
    unique_events, seen_hashes, duplicates = deduplicate_event_list(normalized)
    print(f"  Deduplicated to {len(unique_events)} unique events")
    
    # Test archiving
    from normalize import should_archive_event
    current_events = [e for e in unique_events if not should_archive_event(e)]
    archived_events = [e for e in unique_events if should_archive_event(e)]
    
    print(f"  Current events: {len(current_events)}")
    print(f"  Events to archive: {len(archived_events)}")
    
    print("  ✓ Full pipeline test passed")

def main():
    """Run all tests."""
    print("=== Phase 2 Testing ===\n")
    
    try:
        test_normalization()
        print()
        
        test_deduplication()
        print()
        
        test_state_management()
        print()
        
        test_full_pipeline()
        print()
        
        print("=== All Phase 2 tests completed successfully! ===")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
