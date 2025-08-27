#!/usr/bin/env python3
"""
Phase 8 Quick Validation
Essential tests for production deployment readiness
"""

import subprocess
import sys
import json
import os
from pathlib import Path

def test_cli_basics():
    """Test basic CLI functionality"""
    print("🖥️ Testing CLI basics...")
    
    tests = [
        (["python3", "cli.py", "--help"], "Help command"),
        (["python3", "cli.py", "status"], "Status command"),
        (["python3", "cli.py", "run", "--dry-run", "--max-events", "1"], "Dry run"),
    ]
    
    passed = 0
    for cmd, name in tests:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                print(f"  ✅ {name}")
                passed += 1
            else:
                print(f"  ❌ {name} (exit code: {result.returncode})")
        except Exception as e:
            print(f"  ❌ {name} (error: {e})")
    
    return passed, len(tests)

def test_deployment_files():
    """Test deployment files exist"""
    print("🚀 Testing deployment files...")
    
    required_files = [
        ("cli.py", "CLI script"),
        ("deploy.sh", "Deployment script"),
        ("production.json", "Production config"),
        ("validate_phase8.py", "Validation script"),
        ("simple_crawler.py", "Crawler module")
    ]
    
    passed = 0
    for filename, description in required_files:
        if Path(filename).exists():
            print(f"  ✅ {description}")
            passed += 1
        else:
            print(f"  ❌ {description} missing")
    
    return passed, len(required_files)

def test_directory_structure():
    """Test required directories"""
    print("📁 Testing directory structure...")
    
    required_dirs = [
        ("logs", "Log directory"),
        ("data", "Data directory"), 
        ("backups", "Backup directory"),
        ("reports", "Reports directory")
    ]
    
    passed = 0
    for dirname, description in required_dirs:
        if Path(dirname).exists():
            print(f"  ✅ {description}")
            passed += 1
        else:
            print(f"  ❌ {description} missing")
    
    return passed, len(required_dirs)

def test_configuration():
    """Test configuration files"""
    print("⚙️ Testing configuration...")
    
    configs = [
        ("options.json", "Main configuration"),
        ("production.json", "Production configuration")
    ]
    
    passed = 0
    for filename, description in configs:
        try:
            if Path(filename).exists():
                with open(filename, 'r') as f:
                    json.load(f)
                print(f"  ✅ {description} valid")
                passed += 1
            else:
                print(f"  ❌ {description} missing")
        except json.JSONDecodeError:
            print(f"  ❌ {description} invalid JSON")
        except Exception as e:
            print(f"  ❌ {description} error: {e}")
    
    return passed, len(configs)

def test_permissions():
    """Test file permissions"""
    print("🔒 Testing permissions...")
    
    executable_files = [
        ("cli.py", "CLI script"),
        ("deploy.sh", "Deployment script"),
        ("validate_phase8.py", "Validation script")
    ]
    
    passed = 0
    for filename, description in executable_files:
        if Path(filename).exists() and os.access(filename, os.X_OK):
            print(f"  ✅ {description} executable")
            passed += 1
        else:
            print(f"  ❌ {description} not executable")
    
    return passed, len(executable_files)

def main():
    """Run quick validation"""
    print("🧪 Phase 8 Quick Validation")
    print("=" * 50)
    
    total_passed = 0
    total_tests = 0
    
    # Run all tests
    tests = [
        test_cli_basics,
        test_deployment_files,
        test_directory_structure,
        test_configuration,
        test_permissions
    ]
    
    for test_func in tests:
        passed, count = test_func()
        total_passed += passed
        total_tests += count
        print()
    
    # Summary
    print("=" * 50)
    print(f"RESULTS: {total_passed}/{total_tests} tests passed")
    
    if total_passed == total_tests:
        print("🎉 Phase 8 validation PASSED!")
        return 0
    else:
        print("❌ Phase 8 validation FAILED!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
