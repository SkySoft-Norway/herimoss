#!/usr/bin/env python3
"""One-off fixer for the Levi Henriksen & Babylon Badlands event data issues.

Updates:
- Correct title (remove trailing marketing phrase)
- Set proper venue name 'Verket Scene'
- Set start/end datetime (2025-09-05 19:00–22:00 Europe/Oslo)
- Set info/source URL (arrangement-side) instead of only ticket URL
- Remove duplicate row if present
"""
import sqlite3, sys

DB = '/var/www/vhosts/herimoss.no/pythoncrawler/events.db'
INFO_URL = 'https://www.verketscene.no/programmet/teigens-tropper-med-anita-skorgan-9bdlp'  # Provided by user (arrangementside)
TITLE_CORRECT = 'Levi Henriksen & Babylon Badlands'
START = '2025-09-05T19:00:00'
END = '2025-09-05T22:00:00'

def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    # Find candidate rows containing Levi
    rows = cur.execute("SELECT id, title FROM events WHERE title LIKE '%Levi Henriksen%' ").fetchall()
    ids = [r[0] for r in rows]
    if not ids:
        print('No Levi rows found')
        return
    # Keep the first id, others will be deleted after update
    keep_id = ids[0]
    delete_ids = ids[1:]
    cur.execute("UPDATE events SET title=?, venue=?, start_time=?, end_time=?, source_url=?, updated_at=datetime('now'), last_verified=datetime('now') WHERE id=?", 
                (TITLE_CORRECT, 'Verket Scene', START, END, INFO_URL, keep_id))
    for did in delete_ids:
        cur.execute("DELETE FROM events WHERE id=?", (did,))
    conn.commit()
    print(f'Updated Levi event id={keep_id}; removed duplicates: {delete_ids}')

if __name__ == '__main__':
    main()
