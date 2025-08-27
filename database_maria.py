"""MariaDB storage backend for events (replacement for SQLite DatabaseManager)."""
import mysql.connector
from mysql.connector import errorcode
from datetime import datetime
from typing import List, Dict
from models import Event
from logging_utils import log_info, log_error


class MariaDBManager:
    def __init__(self, host: str, user: str, password: str, database: str):
        self.cfg = dict(host=host, user=user, password=password, database=database)

    def _connect(self):
        try:
            return mysql.connector.connect(**self.cfg)
        except mysql.connector.Error as e:
            log_error('mariadb', f'Connection failed: {e.msg} (code {e.errno}). Ensure database/user exists and privileges granted.')
            raise

    def initialize(self):
        """Create tables if not exist."""
        ddl_events = """
        CREATE TABLE IF NOT EXISTS events (
            id INT AUTO_INCREMENT PRIMARY KEY,
            event_hash VARCHAR(64) UNIQUE NOT NULL,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            start_time DATETIME NOT NULL,
            end_time DATETIME NULL,
            venue VARCHAR(255),
            address VARCHAR(255),
            city VARCHAR(100) DEFAULT 'Moss',
            country VARCHAR(100) DEFAULT 'Norway',
            price_info VARCHAR(255),
            source VARCHAR(100) NOT NULL,
            source_url TEXT,
            ticket_url TEXT,
            categories TEXT,
            keywords TEXT,
            image_url TEXT,
            status VARCHAR(32) DEFAULT 'active',
            confidence_score FLOAT DEFAULT 1.0,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            first_seen DATETIME NOT NULL,
            last_verified DATETIME NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"""
        conn = self._connect(); cur = conn.cursor()
        cur.execute(ddl_events)
        cur.close(); conn.close()
        log_info("MariaDB schema ready")

    def _hash(self, e: Event) -> str:
        import hashlib
        key = f"{(e.title or '').lower()}|{(e.venue or '').lower()}|{e.start.isoformat()}|{e.source_url or ''}".encode()
        return hashlib.sha256(key).hexdigest()[:32]

    def save_events(self, events: List[Event], source: str) -> Dict[str,int]:
        if not events: return {'new':0,'updated':0,'duplicates':0}
        stats={'new':0,'updated':0,'duplicates':0}
        conn=self._connect(); cur=conn.cursor(dictionary=True)
        now = datetime.utcnow()
        def _s(v):
            return str(v) if v is not None else None
        for e in events:
            h=self._hash(e)
            cur.execute("SELECT id,title,description,venue,price_info FROM events WHERE event_hash=%s", (h,))
            row=cur.fetchone()
            if row:
                # minimal update check
                if any([
                    row['title']!=e.title,
                    row['description']!=e.description,
                    row['venue']!=e.venue,
                    row['price_info']!=e.price
                ]):
                    cur.execute("UPDATE events SET title=%s, description=%s, venue=%s, price_info=%s, updated_at=%s, last_verified=%s WHERE id=%s",
                                (e.title,e.description,e.venue,e.price,now,now,row['id']))
                    stats['updated']+=1
                else:
                    cur.execute("UPDATE events SET last_verified=%s WHERE id=%s", (now,row['id']))
                    stats['duplicates']+=1
            else:
                cur.execute("""
                    INSERT INTO events (
                      event_hash,title,description,start_time,end_time,venue,address,city,country,price_info,source,source_url,ticket_url,categories,keywords,image_url,status,confidence_score,created_at,updated_at,first_seen,last_verified
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                    (h,e.title,e.description,e.start,e.end,e.venue,e.address,e.city,'Norway',e.price,e.source,_s(e.source_url),_s(e.ticket_url),'[]','[]',_s(e.image_url),'active',1.0,now,now,now,now)
                )
                stats['new']+=1
        conn.commit(); cur.close(); conn.close()
        log_info(f"MariaDB saved events from {source}: {stats}")
        return stats
