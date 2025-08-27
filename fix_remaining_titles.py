#!/usr/bin/env python3
"""Fill remaining placeholder titles by synthesizing a friendly title from the source/ticket URL domain.

This is a conservative fallback used when neither description nor URL path provide a readable event name.
"""
import sqlite3
from urllib.parse import urlparse

DB_PATH = '/var/www/vhosts/herimoss.no/pythoncrawler/events.db'

PLACEHOLDERS = ['KJØP BILLETTER', 'BILLETTER', 'Kjøp billetter']


def domain_friendly_title(url: str) -> str:
    try:
        p = urlparse(url)
        host = p.hostname or ''
        if not host:
            return ''
        host = host.replace('www.', '')
        # get last segment of path if not numeric
        path = p.path.rstrip('/')
        last = ''
        if path:
            parts = [s for s in path.split('/') if s]
            if parts:
                cand = parts[-1]
                if not cand.isdigit() and len(cand) > 2:
                    last = cand.replace('-', ' ').replace('_', ' ')
        if last:
            return f"{last} — {host}"
        # fallback
        return f"Billetter — {host}"
    except Exception:
        return ''


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, title, description, source_url, ticket_url FROM events")
    rows = cur.fetchall()
    updates = []
    for id_, title, desc, src, turl in rows:
        if not title:
            continue
        if any(p.lower() in title.lower() for p in PLACEHOLDERS):
            new_title = ''
            # try ticket_url first
            if turl:
                new_title = domain_friendly_title(turl)
            if not new_title and src:
                new_title = domain_friendly_title(src)
            if new_title:
                updates.append((new_title, id_))

    if not updates:
        print('No remaining placeholder titles could be synthesized.')
        return

    print(f'Applying {len(updates)} synthesized titles...')
    for new_title, id_ in updates:
        cur.execute('UPDATE events SET title = ? WHERE id = ?', (new_title, id_))
        print(f' - id={id_} -> "{new_title}"')
    conn.commit()
    conn.close()
    print('Done.')


if __name__ == '__main__':
    main()
