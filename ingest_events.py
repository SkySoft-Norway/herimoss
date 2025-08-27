#!/usr/bin/env python3
"""Ingest events from JSON files into the SQLite DB using DatabaseManager.save_events

Reads `verketscene_events.json` and `mosskulturhus_events.json`, normalizes minimal fields,
creates `models.Event` instances, and saves them.
"""
import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
VS_JSON = ROOT / 'verketscene_events.json'
MK_JSON = ROOT / 'mosskulturhus_events.json'
DB_PATH = ROOT / 'events.db'

sys.path.insert(0, str(ROOT))
from database import DatabaseManager
from models import Event
from logging_utils import init_logging


def parse_date(s: str):
    if not s:
        return None
    # Try ISO first
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%d'):
        try:
            return datetime.fromisoformat(s)
        except Exception:
            pass
    # Try common norwegian patterns like '9. okt' or '9. okt 2025'
    try:
        s2 = s.replace('•',' ').strip()
        # remove weekday names if present
        s2 = s2.split(' - ')[0]
        # fallback: return None
    except Exception:
        return None
    return None


def event_from_record(rec: dict, source: str) -> Event | None:
    # rec expected to have title, ticket_url/url, datetime, venue, price, external_id
    title = rec.get('title') or 'Uten tittel'
    dt_raw = rec.get('start') or rec.get('datetime')
    start = parse_date(dt_raw) or datetime.now()
    end_raw = rec.get('end')
    end = parse_date(end_raw) if end_raw else None

    info_url = rec.get('info_url') or rec.get('url')
    ticket_url = rec.get('ticket_url') or rec.get('url')
    evt = Event(
        id=Event.generate_id(title, start, rec.get('venue')),
        title=title,
        description=rec.get('context') or rec.get('description'),
        url=info_url,
        ticket_url=ticket_url,
        image_url=None,
        venue=rec.get('venue'),
        address=None,
        city='Moss',
        lat=None,
        lon=None,
        category=rec.get('category'),
        start=start,
        end=end,
        price=rec.get('price'),
        source=source,
        source_type='html',
        source_url=info_url,
        first_seen=datetime.now(),
        last_seen=datetime.now(),
        status='upcoming'
    )
    return evt


async def main():
    # init logging so DatabaseManager can use it
    init_logging(str(ROOT / 'logs' / 'crawler_log.json'), str(ROOT / 'logs' / 'crawler_errors.json'))
    dm = DatabaseManager(str(DB_PATH))
    await dm.initialize()

    records = []
    if VS_JSON.exists():
        j = json.loads(VS_JSON.read_text(encoding='utf-8'))
        recs = j.get('events') if isinstance(j, dict) else j
        for r in recs:
            evt = event_from_record(r, 'verketscene')
            if evt:
                records.append(evt)

    if MK_JSON.exists():
        j = json.loads(MK_JSON.read_text(encoding='utf-8'))
        recs = j.get('events') if isinstance(j, dict) else j
        for r in recs:
            evt = event_from_record(r, 'mosskulturhus')
            if evt:
                records.append(evt)

    # Save in batches per source to get per-source stats
    stats_total = {'new':0,'updated':0,'duplicates':0}
    by_source = {'verketscene': [], 'mosskulturhus': []}
    for e in records:
        by_source[e.source].append(e)

    for source, evs in by_source.items():
        if not evs:
            continue
        stats = await dm.save_events(evs, source)
        print(f"Ingested from {source}: {stats}")
        for k in stats_total:
            stats_total[k] += stats.get(k,0)

    print('Totals:', stats_total)


if __name__ == '__main__':
    asyncio.run(main())
