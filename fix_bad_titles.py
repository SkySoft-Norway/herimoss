#!/usr/bin/env python3
"""Fix events in the SQLite DB where title is incorrectly set to "KJØP BILLETTER" or similar.

Strategy:
- For events with titles that look like buy-ticket placeholders, try to extract a real title
  from the description (first sentence/line) or the source_url path.
- Update the DB in-place and print a short report.
"""
import sqlite3
import re
from urllib.parse import urlparse, unquote

DB_PATH = '/var/www/vhosts/herimoss.no/pythoncrawler/events.db'

PLACEHOLDER_PATTERNS = [r'^\s*KJ\s?ØP\b', r'\bBILLETTER\b', r'\bKjøp billetter\b', r'^\s*BILLETTER\s*$']


def looks_like_placeholder(title: str) -> bool:
    if not title:
        return False
    t = title.strip()
    for p in PLACEHOLDER_PATTERNS:
        if re.search(p, t, re.IGNORECASE):
            return True
    return False


def extract_from_description(desc: str) -> str:
    if not desc:
        return ''
    # Use first non-empty line
    for line in desc.splitlines():
        s = line.strip()
        if s:
            # Stop at common separators (dash, em dash, bullet, dot followed by space)
            m = re.match(r'^(.*?)(?:\s+[–—-]\s+|\.|!|\s+•\s+)', s)
            if m:
                candidate = m.group(1).strip()
            else:
                candidate = s
            # Remove trailing 'KJØP BILLETTER' if the source description appended it
            candidate = re.sub(r'\bKJ\s?ØP\b.*$','', candidate, flags=re.IGNORECASE).strip()
            if len(candidate) >= 5:
                return candidate
    return ''


def extract_from_url(url: str) -> str:
    if not url:
        return ''
    try:
        p = urlparse(url)
        path = p.path.rstrip('/')
        if not path:
            return ''
        last = path.split('/')[-1]
        last = unquote(last)
        # replace separators
        candidate = re.sub(r'[-_]+', ' ', last).strip()
        # remove file extensions
        candidate = re.sub(r'\.(html|php|asp|aspx)$', '', candidate, flags=re.IGNORECASE)
        if len(candidate) >= 5:
            return candidate
    except Exception:
        pass
    return ''


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id, title, description, source_url FROM events")
    rows = cursor.fetchall()

    updates = []
    for id_, title, desc, src in rows:
        if looks_like_placeholder(title or ''):
            new_title = extract_from_description(desc or '')
            if not new_title:
                new_title = extract_from_url(src or '')
            if new_title and new_title.lower() not in (title or '').lower():
                updates.append((new_title, id_))

    if not updates:
        print('No placeholder titles found to update.')
        return

    print(f'Updating {len(updates)} events...')
    for new_title, id_ in updates:
        cursor.execute('UPDATE events SET title = ? WHERE id = ?', (new_title, id_))
        print(f' - id={id_} -> "{new_title}"')

    conn.commit()
    conn.close()
    print('Done.')


if __name__ == '__main__':
    main()
