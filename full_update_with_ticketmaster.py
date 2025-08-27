#!/usr/bin/env python3
"""
Complete Event Update System with Ticketmaster Integration
Updated version of full_update.py that includes Ticketmaster API
"""

import logging
import sqlite3
import subprocess
import sys
from datetime import datetime
from config_manager import config
from ticketmaster_client import MossTicketmasterClient

# Setup logging
config.setup_logging()
logger = logging.getLogger(__name__)

def run_moss_kulturhus_scraper():
    """Run Moss Kulturhus scraper"""
    try:
        logger.info("📥 Step 1: Scraping events from Moss Kulturhus...")
        result = subprocess.run([
            sys.executable, 'direct_moss_scraper.py'
        ], cwd='/var/www/vhosts/herimoss.no/pythoncrawler', 
           capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            logger.info("✅ Moss Kulturhus scraping completed successfully")
            return True
        else:
            logger.error(f"❌ Moss Kulturhus scraping failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error running Moss Kulturhus scraper: {e}")
        return False

def run_ticketmaster_sync():
    """Run Ticketmaster API sync"""
    try:
        logger.info("🎫 Step 2: Syncing events from Ticketmaster...")
        
        client = MossTicketmasterClient()
        events_saved = client.sync_ticketmaster_events()
        
        if events_saved >= 0:  # 0 is also success (no events found)
            logger.info(f"✅ Ticketmaster sync completed: {events_saved} events")
            return True
        else:
            logger.error("❌ Ticketmaster sync failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error running Ticketmaster sync: {e}")
        return False

def run_calendar_generation():
    """Generate updated calendar HTML"""
    try:
        logger.info("📄 Step 3: Generating updated calendar...")
        result = subprocess.run([
            sys.executable, 'generate_enhanced_calendar.py'
        ], cwd='/var/www/vhosts/herimoss.no/pythoncrawler',
           capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            logger.info("✅ Calendar generation completed successfully")
            return True
        else:
            logger.error(f"❌ Calendar generation failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error generating calendar: {e}")
        return False

def get_database_stats():
    """Get statistics from the database"""
    try:
        db_path = config.get('DATABASE_PATH', '/var/www/vhosts/herimoss.no/pythoncrawler/events.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Total events
        cursor.execute("SELECT COUNT(*) FROM events WHERE status = 'active'")
        total_events = cursor.fetchone()[0]
        
        # Events by source
        cursor.execute("""
            SELECT source, COUNT(*) 
            FROM events 
            WHERE status = 'active' 
            GROUP BY source
        """)
        by_source = cursor.fetchall()
        
        # Recent events
        cursor.execute("""
            SELECT COUNT(*) 
            FROM events 
            WHERE status = 'active' 
            AND created_at >= datetime('now', '-24 hours')
        """)
        recent_events = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_events': total_events,
            'by_source': dict(by_source),
            'recent_events': recent_events
        }
        
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return None

def main():
    """Main update function"""
    logger.info("🚀 Starting complete Moss Kulturkalender update...")
    
    success_count = 0
    total_steps = 3
    
    # Step 1: Moss Kulturhus scraping
    if run_moss_kulturhus_scraper():
        success_count += 1
    
    # Step 2: Ticketmaster sync
    if run_ticketmaster_sync():
        success_count += 1
    
    # Step 3: Calendar generation
    if run_calendar_generation():
        success_count += 1
    
    # Get final statistics
    stats = get_database_stats()
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 UPDATE SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"✅ Steps completed: {success_count}/{total_steps}")
    
    if stats:
        logger.info(f"📈 Database Statistics:")
        logger.info(f"   Total active events: {stats['total_events']}")
        logger.info(f"   New events today: {stats['recent_events']}")
        logger.info(f"   Events by source:")
        for source, count in stats['by_source'].items():
            logger.info(f"     • {source or 'unknown'}: {count}")
    
    if success_count == total_steps:
        logger.info("🎉 All updates completed successfully!")
        logger.info("🌐 Website updated: https://herimoss.no")
        return True
    else:
        logger.warning(f"⚠️  Some updates failed ({success_count}/{total_steps} completed)")
        return False

if __name__ == "__main__":
    try:
        success = main()
        exit_code = 0 if success else 1
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("❌ Update interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        sys.exit(1)
