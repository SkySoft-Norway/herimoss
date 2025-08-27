"""
Database module for Moss Kulturkalender Event Crawler
Handles SQLite database operations, event storage, deduplication and lifecycle management
"""

import sqlite3
import asyncio
import hashlib
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple, Set
from pathlib import Path
from contextlib import asynccontextmanager

from models import Event
from logging_utils import log_info, log_error, log_warning


class DatabaseManager:
    """Manages SQLite database operations for event storage and lifecycle management"""
    
    def __init__(self, db_path: str = "events.db"):
        self.db_path = Path(db_path)
        self._connection_pool = {}
        self._schema_version = 1
        
    async def initialize(self):
        """Initialize database schema and indexes"""
        log_info("Initializing database...")
        
        await self._create_tables()
        await self._create_indexes()
        await self._migrate_schema()
        
        log_info(f"Database initialized at {self.db_path}")
    
    @asynccontextmanager
    async def get_connection(self):
        """Get database connection with proper cleanup"""
        conn = None
        try:
            # SQLite doesn't support true async, but we use thread pool
            # allow using the connection from different threads via check_same_thread=False
            conn = await asyncio.get_event_loop().run_in_executor(
                None, sqlite3.connect, str(self.db_path), False
            )
            conn.row_factory = sqlite3.Row
            yield conn
        finally:
            if conn:
                await asyncio.get_event_loop().run_in_executor(None, conn.close)
    
    async def _create_tables(self):
        """Create database tables"""
        schema_sql = """
        -- Events table
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_hash TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            start_time TEXT NOT NULL,
            end_time TEXT,
            venue TEXT,
            address TEXT,
            city TEXT DEFAULT 'Moss',
            country TEXT DEFAULT 'Norway',
            latitude REAL,
            longitude REAL,
            price_info TEXT,
            currency TEXT DEFAULT 'NOK',
            source TEXT NOT NULL,
            source_url TEXT,
            ticket_url TEXT,
            categories TEXT, -- JSON array
            keywords TEXT,   -- JSON array
            image_url TEXT,
            status TEXT DEFAULT 'active',
            confidence_score REAL DEFAULT 1.0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            first_seen TEXT NOT NULL,
            last_verified TEXT NOT NULL,
            -- Ticketmaster enhanced fields
            tm_event_id TEXT,
            tm_venue_id TEXT,
            tm_min_price REAL,
            tm_max_price REAL,
            tm_on_sale_start TEXT,
            tm_on_sale_end TEXT,
            tm_presale_start TEXT,
            tm_presale_end TEXT,
            tm_sold_out BOOLEAN DEFAULT FALSE,
            tm_tickets_available BOOLEAN,
            tm_age_restriction TEXT,
            tm_genres TEXT, -- JSON array
            tm_status TEXT,
            tm_last_updated TEXT
        );
        
        -- Event history table for tracking changes
        CREATE TABLE IF NOT EXISTS event_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            event_hash TEXT NOT NULL,
            change_type TEXT NOT NULL, -- 'created', 'updated', 'deleted', 'verified'
            old_data TEXT, -- JSON
            new_data TEXT, -- JSON
            changed_fields TEXT, -- JSON array
            timestamp TEXT NOT NULL,
            source TEXT NOT NULL,
            FOREIGN KEY (event_id) REFERENCES events (id)
        );
        
        -- Sources table for tracking source health and statistics
        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            url TEXT NOT NULL,
            last_scraped TEXT,
            last_success TEXT,
            last_error TEXT,
            total_events INTEGER DEFAULT 0,
            success_rate REAL DEFAULT 1.0,
            avg_response_time REAL DEFAULT 0.0,
            status TEXT DEFAULT 'active', -- 'active', 'disabled', 'error'
            error_count INTEGER DEFAULT 0,
            consecutive_errors INTEGER DEFAULT 0,
            circuit_breaker_until TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        
        -- Duplicate tracking table
        CREATE TABLE IF NOT EXISTS duplicate_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_hash TEXT UNIQUE NOT NULL,
            canonical_event_id INTEGER NOT NULL,
            member_event_ids TEXT NOT NULL, -- JSON array
            similarity_score REAL NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (canonical_event_id) REFERENCES events (id)
        );
        
        -- Performance metrics table
        CREATE TABLE IF NOT EXISTS scrape_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            scrape_start TEXT NOT NULL,
            scrape_end TEXT NOT NULL,
            duration_seconds REAL NOT NULL,
            events_found INTEGER NOT NULL,
            events_new INTEGER NOT NULL,
            events_updated INTEGER NOT NULL,
            events_duplicates INTEGER NOT NULL,
            success BOOLEAN NOT NULL,
            error_message TEXT,
            timestamp TEXT NOT NULL
        );
        """
        
        async with self.get_connection() as conn:
            await asyncio.get_event_loop().run_in_executor(
                None, conn.executescript, schema_sql
            )
            await asyncio.get_event_loop().run_in_executor(None, conn.commit)
    
    async def _create_indexes(self):
        """Create database indexes for performance"""
        indexes_sql = """
        CREATE INDEX IF NOT EXISTS idx_events_hash ON events(event_hash);
        CREATE INDEX IF NOT EXISTS idx_events_source ON events(source);
        CREATE INDEX IF NOT EXISTS idx_events_start_time ON events(start_time);
        CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);
        CREATE INDEX IF NOT EXISTS idx_events_city ON events(city);
        CREATE INDEX IF NOT EXISTS idx_events_created_at ON events(created_at);
        CREATE INDEX IF NOT EXISTS idx_events_tm_event_id ON events(tm_event_id);
        CREATE INDEX IF NOT EXISTS idx_events_tm_venue_id ON events(tm_venue_id);
        CREATE INDEX IF NOT EXISTS idx_events_tm_sold_out ON events(tm_sold_out);
        CREATE INDEX IF NOT EXISTS idx_history_event_id ON event_history(event_id);
        CREATE INDEX IF NOT EXISTS idx_history_timestamp ON event_history(timestamp);
        CREATE INDEX IF NOT EXISTS idx_sources_name ON sources(name);
        CREATE INDEX IF NOT EXISTS idx_duplicates_canonical ON duplicate_groups(canonical_event_id);
        CREATE INDEX IF NOT EXISTS idx_metrics_source ON scrape_metrics(source_name);
        CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON scrape_metrics(timestamp);
        """
        
        async with self.get_connection() as conn:
            await asyncio.get_event_loop().run_in_executor(
                None, conn.executescript, indexes_sql
            )
            await asyncio.get_event_loop().run_in_executor(None, conn.commit)
    
    async def _migrate_schema(self):
        """Handle database schema migrations"""
        # Future schema migrations will be implemented here
        pass
    
    def _generate_event_hash(self, event: Event) -> str:
        """Generate unique hash for event deduplication"""
        # Normalize key fields for consistent hashing
        title = event.title.lower().strip() if event.title else ""
        venue = event.venue.lower().strip() if event.venue else ""
        start_time = event.start.isoformat() if event.start else ""
        
        # Include source URL to distinguish same events from different sources
        source_url = str(event.source_url) if event.source_url else ""
        
        hash_string = f"{title}|{venue}|{start_time}|{source_url}"
        return hashlib.sha256(hash_string.encode('utf-8')).hexdigest()[:16]
    
    async def save_events(self, events: List[Event], source_name: str) -> Dict[str, int]:
        """
        Save events to database with deduplication
        Returns dict with counts: {'new': int, 'updated': int, 'duplicates': int}
        """
        if not events:
            return {'new': 0, 'updated': 0, 'duplicates': 0}
        
        log_info(f"Saving {len(events)} events from {source_name} to database...")
        
        stats = {'new': 0, 'updated': 0, 'duplicates': 0}
        current_time = datetime.now().isoformat()
        
        async with self.get_connection() as conn:
            for event in events:
                try:
                    event_hash = self._generate_event_hash(event)
                    
                    # Check if event already exists
                    existing = await self._get_event_by_hash(conn, event_hash)
                    
                    if existing:
                        # Update existing event if data has changed
                        if await self._update_event_if_changed(conn, existing, event, current_time):
                            stats['updated'] += 1
                        else:
                            stats['duplicates'] += 1
                    else:
                        # Insert new event
                        await self._insert_new_event(conn, event, event_hash, current_time)
                        stats['new'] += 1
                        
                except Exception as e:
                    log_error("database", f"Error saving event '{event.title}': {e}")
                    
            await asyncio.get_event_loop().run_in_executor(None, conn.commit)
        
        log_info(f"Saved events from {source_name}: {stats['new']} new, {stats['updated']} updated, {stats['duplicates']} duplicates")
        return stats
    
    async def _get_event_by_hash(self, conn: sqlite3.Connection, event_hash: str) -> Optional[sqlite3.Row]:
        """Get existing event by hash"""
        cursor = await asyncio.get_event_loop().run_in_executor(
            None, conn.execute,
            "SELECT * FROM events WHERE event_hash = ? AND status != 'deleted'",
            (event_hash,)
        )
        return await asyncio.get_event_loop().run_in_executor(None, cursor.fetchone)
    
    async def _insert_new_event(self, conn: sqlite3.Connection, event: Event, event_hash: str, timestamp: str):
        """Insert new event into database with Ticketmaster enhancements"""
        categories_json = json.dumps([event.category]) if event.category else "[]"
        keywords_json = "[]"  # No keywords in new Event model
        
        # Handle Ticketmaster-specific data
        tm_data = getattr(event, '_ticketmaster_data', {})
        
        sql = """
        INSERT INTO events (
            event_hash, title, description, start_time, end_time, venue, address, 
            city, country, latitude, longitude, price_info, currency, source, 
            source_url, ticket_url, categories, keywords, image_url, 
            confidence_score, created_at, updated_at, first_seen, last_verified,
            tm_event_id, tm_venue_id, tm_min_price, tm_max_price, tm_on_sale_start,
            tm_on_sale_end, tm_presale_start, tm_presale_end, tm_sold_out,
            tm_tickets_available, tm_age_restriction, tm_genres, tm_status, tm_last_updated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        await asyncio.get_event_loop().run_in_executor(
            None, conn.execute, sql, (
                event_hash, event.title, event.description,
                event.start.isoformat() if event.start else None,
                event.end.isoformat() if event.end else None,
                event.venue, event.address, event.city, "Norway",
                event.lat, event.lon, event.price, "NOK",
                event.source, str(event.source_url) if event.source_url else None, 
                str(event.ticket_url) if event.ticket_url else None,
                categories_json, keywords_json, str(event.image_url) if event.image_url else None,
                1.0, timestamp, timestamp, timestamp, timestamp,
                # Ticketmaster fields
                tm_data.get('event_id'), tm_data.get('venue_id'),
                tm_data.get('min_price'), tm_data.get('max_price'),
                tm_data.get('on_sale_start'), tm_data.get('on_sale_end'),
                tm_data.get('presale_start'), tm_data.get('presale_end'),
                tm_data.get('sold_out', False), tm_data.get('tickets_available'),
                tm_data.get('age_restriction'), json.dumps(tm_data.get('genres', [])),
                tm_data.get('status'), tm_data.get('last_updated')
            )
        )
        
        # Log to history
        cursor_result = await asyncio.get_event_loop().run_in_executor(
            None, conn.execute, "SELECT last_insert_rowid()"
        )
        row = await asyncio.get_event_loop().run_in_executor(None, cursor_result.fetchone)
        event_id = row[0] if row else None
        await self._log_event_history(conn, event_id, event_hash, 'created', None, event, timestamp, event.source)
    
    async def _update_event_if_changed(self, conn: sqlite3.Connection, existing: sqlite3.Row, 
                                     new_event: Event, timestamp: str) -> bool:
        """Update event if data has changed, return True if updated"""
        # Compare key fields to detect changes
        changed_fields = []
        
        if existing['title'] != new_event.title:
            changed_fields.append('title')
        if existing['description'] != new_event.description:
            changed_fields.append('description')
        if existing['venue'] != new_event.venue:
            changed_fields.append('venue')
        if existing['price_info'] != new_event.price:
            changed_fields.append('price_info')
        
        if not changed_fields:
            # Just update last_verified timestamp
            await asyncio.get_event_loop().run_in_executor(
                None, conn.execute,
                "UPDATE events SET last_verified = ? WHERE id = ?",
                (timestamp, existing['id'])
            )
            return False
        
        # Update changed fields
        categories_json = json.dumps([new_event.category]) if new_event.category else "[]"
        keywords_json = "[]"  # No keywords in new Event model
        
        sql = """
        UPDATE events SET 
            title = ?, description = ?, venue = ?, address = ?, price_info = ?,
            ticket_url = ?, categories = ?, keywords = ?, image_url = ?,
            updated_at = ?, last_verified = ?
        WHERE id = ?
        """
        
        await asyncio.get_event_loop().run_in_executor(
            None, conn.execute, sql, (
                new_event.title, new_event.description, new_event.venue, new_event.address,
                new_event.price, str(new_event.ticket_url) if new_event.ticket_url else None, 
                categories_json, keywords_json,
                str(new_event.image_url) if new_event.image_url else None, 
                timestamp, timestamp, existing['id']
            )
        )
        
        # Log to history
        await self._log_event_history(
            conn, existing['id'], existing['event_hash'], 'updated',
            dict(existing), new_event, timestamp, new_event.source, changed_fields
        )
        
        return True
    
    async def _log_event_history(self, conn: sqlite3.Connection, event_id: int, event_hash: str,
                               change_type: str, old_data: Optional[dict], new_data: Event,
                               timestamp: str, source: str, changed_fields: Optional[List[str]] = None):
        """Log event change to history table"""
        sql = """
        INSERT INTO event_history (
            event_id, event_hash, change_type, old_data, new_data, 
            changed_fields, timestamp, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        old_json = json.dumps(old_data) if old_data else None
        new_json = json.dumps(new_data.__dict__, default=str) if new_data else None
        changed_json = json.dumps(changed_fields) if changed_fields else None
        
        await asyncio.get_event_loop().run_in_executor(
            None, conn.execute, sql, (
                event_id, event_hash, change_type, old_json, new_json,
                changed_json, timestamp, source
            )
        )
    
    async def get_events(self, 
                        limit: int = 100, 
                        offset: int = 0,
                        source: Optional[str] = None,
                        start_date: Optional[datetime] = None,
                        end_date: Optional[datetime] = None,
                        city: str = "Moss") -> List[Dict]:
        """Get events with filtering and pagination"""
        
        conditions = ["status = 'active'"]
        params = []
        
        if source:
            conditions.append("source = ?")
            params.append(source)
        
        if city:
            conditions.append("city = ?")
            params.append(city)
        
        if start_date:
            conditions.append("start_time >= ?")
            params.append(start_date.isoformat())
        
        if end_date:
            conditions.append("start_time <= ?")
            params.append(end_date.isoformat())
        
        where_clause = " AND ".join(conditions)
        sql = f"""
        SELECT * FROM events 
        WHERE {where_clause}
        ORDER BY start_time ASC 
        LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        
        async with self.get_connection() as conn:
            cursor = await asyncio.get_event_loop().run_in_executor(
                None, conn.execute, sql, params
            )
            rows = await asyncio.get_event_loop().run_in_executor(None, cursor.fetchall)
            
        return [dict(row) for row in rows]
    
    async def cleanup_old_events(self, days_old: int = 30) -> int:
        """Mark old events as deleted and clean up history"""
        cutoff_date = (datetime.now() - timedelta(days=days_old)).isoformat()
        
        async with self.get_connection() as conn:
            # Mark old events as deleted
            cursor = await asyncio.get_event_loop().run_in_executor(
                None, conn.execute,
                "UPDATE events SET status = 'deleted', updated_at = ? WHERE start_time < ? AND status = 'active'",
                (datetime.now().isoformat(), cutoff_date)
            )
            
            deleted_count = cursor.rowcount
            
            # Clean up old history entries (keep last 90 days)
            history_cutoff = (datetime.now() - timedelta(days=90)).isoformat()
            await asyncio.get_event_loop().run_in_executor(
                None, conn.execute,
                "DELETE FROM event_history WHERE timestamp < ?",
                (history_cutoff,)
            )
            
            await asyncio.get_event_loop().run_in_executor(None, conn.commit)
            
        log_info(f"Cleaned up {deleted_count} old events")
        return deleted_count
    
    async def update_source_stats(self, source_name: str, success: bool, 
                                response_time: float, events_count: int = 0,
                                error_message: Optional[str] = None):
        """Update source statistics and health status"""
        current_time = datetime.now().isoformat()
        
        async with self.get_connection() as conn:
            # Get existing source stats
            cursor = await asyncio.get_event_loop().run_in_executor(
                None, conn.execute,
                "SELECT * FROM sources WHERE name = ?",
                (source_name,)
            )
            existing = await asyncio.get_event_loop().run_in_executor(None, cursor.fetchone)
            
            if existing:
                # Update existing source
                if success:
                    new_total = existing['total_events'] + events_count
                    new_error_count = 0
                    new_consecutive_errors = 0
                    last_success = current_time
                    last_error = existing['last_error']
                    status = 'active'
                    circuit_breaker_until = None
                else:
                    new_total = existing['total_events']
                    new_error_count = existing['error_count'] + 1
                    new_consecutive_errors = existing['consecutive_errors'] + 1
                    last_success = existing['last_success']
                    last_error = current_time
                    
                    # Implement circuit breaker logic
                    if new_consecutive_errors >= 5:
                        status = 'error'
                        # Set circuit breaker for increasing intervals
                        breaker_minutes = min(60 * (2 ** (new_consecutive_errors - 5)), 1440)  # Max 24 hours
                        circuit_breaker_until = (datetime.now() + timedelta(minutes=breaker_minutes)).isoformat()
                    else:
                        status = existing['status']
                        circuit_breaker_until = existing['circuit_breaker_until']
                
                # Calculate new success rate
                total_attempts = new_error_count + (new_total / max(events_count, 1))
                success_rate = 1.0 - (new_error_count / max(total_attempts, 1))
                
                sql = """
                UPDATE sources SET 
                    last_scraped = ?, last_success = ?, last_error = ?,
                    total_events = ?, success_rate = ?, avg_response_time = ?,
                    status = ?, error_count = ?, consecutive_errors = ?,
                    circuit_breaker_until = ?, updated_at = ?
                WHERE name = ?
                """
                
                await asyncio.get_event_loop().run_in_executor(
                    None, conn.execute, sql, (
                        current_time, last_success, last_error, new_total,
                        success_rate, response_time, status, new_error_count,
                        new_consecutive_errors, circuit_breaker_until, current_time, source_name
                    )
                )
            else:
                # Insert new source
                status = 'active' if success else 'error'
                sql = """
                INSERT INTO sources (
                    name, url, last_scraped, last_success, last_error,
                    total_events, success_rate, avg_response_time, status,
                    error_count, consecutive_errors, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                
                await asyncio.get_event_loop().run_in_executor(
                    None, conn.execute, sql, (
                        source_name, "", current_time,
                        current_time if success else None,
                        current_time if not success else None,
                        events_count, 1.0 if success else 0.0, response_time,
                        status, 0 if success else 1, 0 if success else 1,
                        current_time, current_time
                    )
                )
            
            await asyncio.get_event_loop().run_in_executor(None, conn.commit)
    
    async def log_scrape_metrics(self, source_name: str, duration: float, 
                               events_found: int, stats: Dict[str, int],
                               success: bool, error_message: Optional[str] = None):
        """Log scraping metrics for monitoring"""
        current_time = datetime.now().isoformat()
        
        sql = """
        INSERT INTO scrape_metrics (
            source_name, scrape_start, scrape_end, duration_seconds,
            events_found, events_new, events_updated, events_duplicates,
            success, error_message, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        scrape_start = (datetime.now() - timedelta(seconds=duration)).isoformat()
        
        async with self.get_connection() as conn:
            await asyncio.get_event_loop().run_in_executor(
                None, conn.execute, sql, (
                    source_name, scrape_start, current_time, duration,
                    events_found, stats.get('new', 0), stats.get('updated', 0),
                    stats.get('duplicates', 0), success, error_message, current_time
                )
            )
            await asyncio.get_event_loop().run_in_executor(None, conn.commit)
    
    async def get_database_stats(self) -> Dict[str, any]:
        """Get comprehensive database statistics"""
        async with self.get_connection() as conn:
            # Event counts
            cursor = await asyncio.get_event_loop().run_in_executor(
                None, conn.execute,
                "SELECT COUNT(*) as total, status FROM events GROUP BY status"
            )
            status_counts = {row['status']: row['total'] for row in await asyncio.get_event_loop().run_in_executor(None, cursor.fetchall)}
            
            # Source stats
            cursor = await asyncio.get_event_loop().run_in_executor(
                None, conn.execute,
                "SELECT name, total_events, success_rate, status FROM sources ORDER BY total_events DESC"
            )
            sources = [dict(row) for row in await asyncio.get_event_loop().run_in_executor(None, cursor.fetchall)]
            
            # Recent activity
            cursor = await asyncio.get_event_loop().run_in_executor(
                None, conn.execute,
                """SELECT DATE(created_at) as date, COUNT(*) as count 
                   FROM events 
                   WHERE created_at >= date('now', '-30 days')
                   GROUP BY DATE(created_at) 
                   ORDER BY date DESC LIMIT 30"""
            )
            daily_activity = [dict(row) for row in await asyncio.get_event_loop().run_in_executor(None, cursor.fetchall)]
            
        return {
            'event_counts': status_counts,
            'total_events': sum(status_counts.values()),
            'active_events': status_counts.get('active', 0),
            'sources': sources,
            'daily_activity': daily_activity,
            'database_path': str(self.db_path),
            'schema_version': self._schema_version
        }


# Global database instance
_db_manager: Optional[DatabaseManager] = None

async def get_database() -> DatabaseManager:
    """Get global database manager instance"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
        await _db_manager.initialize()
    return _db_manager

async def close_database():
    """Close database connections"""
    global _db_manager
    if _db_manager:
        # Database connections are automatically closed in context managers
        _db_manager = None
