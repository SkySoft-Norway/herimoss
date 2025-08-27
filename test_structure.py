#!/usr/bin/env python3
"""
Simple test script to verify basic structure without external dependencies.
"""
import json
import os
from pathlib import Path

def test_structure():
    """Test that the basic structure is in place."""
    print("Testing Moss Kulturkalender structure...")
    
    base_dir = Path("/var/www/vhosts/herimoss.no/pythoncrawler")
    
    # Check directories
    required_dirs = [
        "state",
        "templates", 
        "scrapers",
        "html",
        "html/assets"
    ]
    
    for dir_name in required_dirs:
        dir_path = base_dir / dir_name
        if dir_path.exists():
            print(f"✓ Directory {dir_name} exists")
        else:
            print(f"✗ Directory {dir_name} missing")
    
    # Check key files
    required_files = [
        "options.json",
        "requirements.txt",
        "main.py",
        "models.py",
        "utils.py",
        "logging_utils.py",
        "scrapers/__init__.py",
        "scrapers/moss_kommune.py"
    ]
    
    for file_name in required_files:
        file_path = base_dir / file_name
        if file_path.exists():
            print(f"✓ File {file_name} exists")
        else:
            print(f"✗ File {file_name} missing")
    
    # Test config loading
    try:
        config_path = base_dir / "options.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print(f"✓ Configuration loaded successfully")
        print(f"  - {len(config['sources'])} sources configured")
        print(f"  - Output: {config['output_html']}")
    except Exception as e:
        print(f"✗ Configuration loading failed: {e}")
    
    print("\nPhase 1 structure test completed!")

if __name__ == "__main__":
    test_structure()
