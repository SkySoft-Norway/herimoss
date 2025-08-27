#!/usr/bin/env python3
"""
Database migration script to add Ticketmaster fields
"""

import sqlite3
import sys
from pathlib import Path

def migrate_database(db_path="events.db"):
    """Add Ticketmaster fields to existing database"""
    
    print(f"Migrating database: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if migration is needed
        cursor.execute("PRAGMA table_info(events)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'tm_event_id' in columns:
            print("✅ Database already has Ticketmaster fields")
            conn.close()
            return
        
        print("📊 Adding Ticketmaster fields...")
        
        # Add Ticketmaster columns
        migration_sql = [
            "ALTER TABLE events ADD COLUMN tm_event_id TEXT",
            "ALTER TABLE events ADD COLUMN tm_venue_id TEXT",
            "ALTER TABLE events ADD COLUMN tm_min_price REAL",
            "ALTER TABLE events ADD COLUMN tm_max_price REAL",
            "ALTER TABLE events ADD COLUMN tm_on_sale_start TEXT",
            "ALTER TABLE events ADD COLUMN tm_on_sale_end TEXT", 
            "ALTER TABLE events ADD COLUMN tm_presale_start TEXT",
            "ALTER TABLE events ADD COLUMN tm_presale_end TEXT",
            "ALTER TABLE events ADD COLUMN tm_sold_out BOOLEAN DEFAULT FALSE",
            "ALTER TABLE events ADD COLUMN tm_tickets_available BOOLEAN",
            "ALTER TABLE events ADD COLUMN tm_age_restriction TEXT",
            "ALTER TABLE events ADD COLUMN tm_genres TEXT",
            "ALTER TABLE events ADD COLUMN tm_status TEXT",
            "ALTER TABLE events ADD COLUMN tm_last_updated TEXT"
        ]
        
        for sql in migration_sql:
            try:
                cursor.execute(sql)
                print(f"✅ {sql}")
            except sqlite3.OperationalError as e:
                print(f"⚠️  {sql} - {e}")
        
        # Add indexes
        index_sql = [
            "CREATE INDEX IF NOT EXISTS idx_events_tm_event_id ON events(tm_event_id)",
            "CREATE INDEX IF NOT EXISTS idx_events_tm_venue_id ON events(tm_venue_id)",
            "CREATE INDEX IF NOT EXISTS idx_events_tm_sold_out ON events(tm_sold_out)"
        ]
        
        for sql in index_sql:
            try:
                cursor.execute(sql)
                print(f"✅ {sql}")
            except sqlite3.OperationalError as e:
                print(f"⚠️  {sql} - {e}")
        
        conn.commit()
        conn.close()
        
        print("🎉 Database migration completed successfully")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "events.db"
    migrate_database(db_path)