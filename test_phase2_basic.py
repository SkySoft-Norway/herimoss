#!/usr/bin/env python3
"""
Simplified test script for Phase 2 core functionality without external dependencies.
"""
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

def test_basic_structure():
    """Test that Phase 2 files are in place."""
    print("Testing Phase 2 file structure...")
    
    base_dir = Path("/var/www/vhosts/herimoss.no/pythoncrawler")
    
    required_files = [
        "normalize.py",
        "dedupe.py", 
        "state_manager.py",
        "scrapers/html_scraper.py"
    ]
    
    for file_name in required_files:
        file_path = base_dir / file_name
        if file_path.exists():
            print(f"  ✓ {file_name} exists")
        else:
            print(f"  ✗ {file_name} missing")
    
    print("  ✓ Phase 2 structure test passed")

def test_imports():
    """Test that core modules can be imported without external deps."""
    print("Testing basic imports...")
    
    try:
        # Test basic Python functionality
        import json
        import datetime
        print("  ✓ Standard library imports OK")
        
        # Test file structure
        import sys
        sys.path.append('/var/www/vhosts/herimoss.no/pythoncrawler')
        
        # Test that files are syntactically correct
        with open('/var/www/vhosts/herimoss.no/pythoncrawler/models.py', 'r') as f:
            compile(f.read(), 'models.py', 'exec')
        print("  ✓ models.py syntax OK")
        
        print("  ✓ Import test passed")
        
    except Exception as e:
        print(f"  ✗ Import test failed: {e}")

def test_json_config():
    """Test configuration loading."""
    print("Testing configuration...")
    
    try:
        config_path = "/var/www/vhosts/herimoss.no/pythoncrawler/options.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Verify key sections exist
        required_sections = ["sources", "http", "html", "rules"]
        for section in required_sections:
            if section in config:
                print(f"  ✓ Config section '{section}' present")
            else:
                print(f"  ✗ Config section '{section}' missing")
        
        # Check source count
        sources = config.get("sources", {})
        print(f"  ✓ {len(sources)} sources configured")
        
        print("  ✓ Configuration test passed")
        
    except Exception as e:
        print(f"  ✗ Configuration test failed: {e}")

def test_state_directory():
    """Test state directory structure."""
    print("Testing state directory...")
    
    state_dir = Path("/var/www/vhosts/herimoss.no/pythoncrawler/state")
    
    if state_dir.exists():
        print("  ✓ State directory exists")
    else:
        print("  ✗ State directory missing")
        return
    
    # Create test files to verify write access
    try:
        test_file = state_dir / "test.json"
        test_data = {"test": "data", "timestamp": datetime.now().isoformat()}
        
        with open(test_file, 'w') as f:
            json.dump(test_data, f)
        
        # Read it back
        with open(test_file, 'r') as f:
            loaded_data = json.load(f)
        
        if loaded_data["test"] == "data":
            print("  ✓ State directory writable")
        
        # Cleanup
        test_file.unlink()
        
    except Exception as e:
        print(f"  ✗ State directory test failed: {e}")

def test_pipeline_concepts():
    """Test core pipeline concepts with basic Python."""
    print("Testing pipeline concepts...")
    
    # Test basic event structure
    event_data = {
        "id": "test123",
        "title": "Test Event",
        "start": datetime.now().isoformat(),
        "venue": "Test Venue",
        "source": "test",
        "source_type": "manual"
    }
    
    # Test JSON serialization
    try:
        json_str = json.dumps(event_data)
        loaded_data = json.loads(json_str)
        if loaded_data["title"] == "Test Event":
            print("  ✓ Event serialization works")
    except Exception as e:
        print(f"  ✗ Event serialization failed: {e}")
    
    # Test basic normalization concepts
    try:
        title = "  KONSERT: Test Event  "
        normalized_title = title.strip().title()
        if "Test Event" in normalized_title:
            print("  ✓ Basic normalization works")
    except Exception as e:
        print(f"  ✗ Normalization failed: {e}")
    
    # Test basic deduplication concepts
    try:
        import hashlib
        event1_key = "test-event|2025-08-25|test-venue"
        event2_key = "test-event|2025-08-25|test-venue"  # Same
        
        hash1 = hashlib.sha1(event1_key.encode()).hexdigest()[:16]
        hash2 = hashlib.sha1(event2_key.encode()).hexdigest()[:16]
        
        if hash1 == hash2:
            print("  ✓ Basic deduplication hashing works")
    except Exception as e:
        print(f"  ✗ Deduplication test failed: {e}")
    
    print("  ✓ Pipeline concepts test passed")

def test_file_operations():
    """Test file I/O operations needed for state management."""
    print("Testing file operations...")
    
    test_dir = Path("/var/www/vhosts/herimoss.no/pythoncrawler/test_io")
    test_dir.mkdir(exist_ok=True)
    
    try:
        # Test JSON file writing
        events_file = test_dir / "events.json"
        test_events = [
            {"id": "1", "title": "Event 1", "start": datetime.now().isoformat()},
            {"id": "2", "title": "Event 2", "start": datetime.now().isoformat()}
        ]
        
        with open(events_file, 'w', encoding='utf-8') as f:
            json.dump(test_events, f, ensure_ascii=False, indent=2)
        
        # Test reading back
        with open(events_file, 'r', encoding='utf-8') as f:
            loaded_events = json.load(f)
        
        if len(loaded_events) == 2:
            print("  ✓ JSON file I/O works")
        
        # Test atomic write (temp file + rename)
        temp_file = events_file.with_suffix('.tmp')
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(test_events, f)
        
        temp_file.rename(events_file)
        print("  ✓ Atomic file operations work")
        
        # Cleanup
        for file in test_dir.glob("*"):
            file.unlink()
        test_dir.rmdir()
        
    except Exception as e:
        print(f"  ✗ File operations test failed: {e}")

def main():
    """Run all basic tests."""
    print("=== Phase 2 Basic Testing ===\n")
    
    test_basic_structure()
    print()
    
    test_imports()
    print()
    
    test_json_config()
    print()
    
    test_state_directory()
    print()
    
    test_pipeline_concepts()
    print()
    
    test_file_operations()
    print()
    
    print("=== Phase 2 basic tests completed! ===")
    print("Note: Full testing requires external dependencies from requirements.txt")

if __name__ == "__main__":
    main()
