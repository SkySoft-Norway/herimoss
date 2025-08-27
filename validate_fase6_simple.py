#!/usr/bin/env python3
"""
Enkel Fase 6 Test - Database og persistering
Test database komponenter uten komplekse operasjoner
"""

import asyncio
import sys
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import Event
from database import DatabaseManager
from dedupe_advanced import get_deduplicator
from logging_utils import init_logging, log_info, log_error


async def test_database_basic():
    """Test basic database operations"""
    log_info("🧪 Testing basic database operations...")
    
    try:
        # Use temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        db = DatabaseManager(db_path)
        await db.initialize()
        
        # Test basic connection and schema
        async with db.get_connection() as conn:
            cursor = await asyncio.get_event_loop().run_in_executor(
                None, conn.execute, "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = await asyncio.get_event_loop().run_in_executor(None, cursor.fetchall)
            
        table_names = [row[0] for row in tables]
        expected_tables = ['events', 'event_history', 'sources', 'duplicate_groups', 'scrape_metrics']
        
        missing_tables = [t for t in expected_tables if t not in table_names]
        if missing_tables:
            log_error("test", f"❌ Missing tables: {missing_tables}")
            return False
        
        # Cleanup
        Path(db_path).unlink()
        
        log_info("✅ Basic database operations successful")
        return True
        
    except Exception as e:
        log_error("test", f"❌ Basic database test failed: {e}")
        return False


async def test_deduplication_basic():
    """Test basic deduplication functionality"""
    log_info("🧪 Testing basic deduplication...")
    
    try:
        # Create test events
        event1 = Event(
            id="test-1",
            title="Test Event",
            start=datetime.now() + timedelta(days=1),
            venue="Test Venue",
            source="test_source",
            source_type="html",
            first_seen=datetime.now(),
            last_seen=datetime.now()
        )
        
        event2 = Event(
            id="test-2", 
            title="Test Event",  # Same title
            start=datetime.now() + timedelta(days=1),  # Same time
            venue="Test Venue",  # Same venue
            source="test_source2",  # Different source
            source_type="html",
            first_seen=datetime.now(),
            last_seen=datetime.now()
        )
        
        deduplicator = get_deduplicator()
        
        # Test duplicate detection
        matches = await deduplicator.find_duplicates([event1, event2])
        
        if len(matches) == 0:
            log_error("test", "❌ Should detect duplicate between identical events")
            return False
        
        if matches[0].confidence not in ['high', 'medium']:
            log_error("test", f"❌ Expected high/medium confidence, got {matches[0].confidence}")
            return False
        
        log_info("✅ Basic deduplication successful")
        return True
        
    except Exception as e:
        log_error("test", f"❌ Deduplication test failed: {e}")
        return False


async def test_imports():
    """Test that all modules can be imported"""
    log_info("🧪 Testing imports...")
    
    try:
        from database import get_database, close_database
        from dedupe_advanced import EventDeduplicator, DuplicationMatch
        
        log_info("✅ All imports successful")
        return True
        
    except Exception as e:
        log_error("test", f"❌ Import test failed: {e}")
        return False


async def main():
    """Run simple Fase 6 tests"""
    init_logging()
    
    log_info("🚀 Starter Fase 6 enkel validering - Database og persistering")
    log_info("=" * 60)
    
    tests = [
        ("Import Test", test_imports),
        ("Basic Database Operations", test_database_basic),
        ("Basic Deduplication", test_deduplication_basic)
    ]
    
    results = []
    for test_name, test_func in tests:
        log_info(f"📋 {test_name}...")
        success = await test_func()
        results.append(success)
        log_info("-" * 40)
        await asyncio.sleep(0.5)
    
    # Sammendrag
    log_info("📊 FASE 6 ENKEL VALIDERING SAMMENDRAG")
    log_info("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    for i, (success, (test_name, _)) in enumerate(zip(results, tests)):
        status = "✅ BESTÅTT" if success else "❌ FEILET"
        log_info(f"{i+1}. {test_name}: {status}")
    
    log_info("-" * 40)
    log_info(f"📈 Resultat: {passed}/{total} tester bestått")
    
    if passed == total:
        log_info("🎉 FASE 6 GRUNNLEGGENDE VALIDERING FULLFØRT!")
        log_info("💡 Database og deduplication komponenter fungerer")
        log_info("")
        log_info("🗄️ Validerte komponenter:")
        log_info("   • Database schema opprettet")
        log_info("   • Database tilkoblinger fungerer")
        log_info("   • Advanced deduplication algoritmer")
        log_info("   • Event sammenligning og matching")
        log_info("   • Alle imports og avhengigheter")
        return True
    else:
        log_error("test", f"⚠️ {total - passed} test(er) feilet")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
