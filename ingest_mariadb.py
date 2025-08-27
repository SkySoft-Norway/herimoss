#!/usr/bin/env python3
"""Ingest events into MariaDB (fresh start)."""
import json, asyncio
from pathlib import Path
from datetime import datetime
from models import Event
from database_maria import MariaDBManager
from logging_utils import init_logging

ROOT=Path(__file__).resolve().parent
VS=ROOT/'verketscene_events.json'
MK=ROOT/'mosskulturhus_events.json'

def parse_iso(s):
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.utcnow()

def rec_to_event(r, source):
    start = parse_iso(r.get('start') or r.get('datetime') or datetime.utcnow().isoformat())
    end = parse_iso(r['end']) if r.get('end') else None
    return Event(
        id=Event.generate_id(r.get('title') or 'Uten tittel', start, r.get('venue')),
        title=r.get('title') or 'Uten tittel',
        description=r.get('description') or r.get('context'),
        url=r.get('info_url') or r.get('url'),
        ticket_url=r.get('ticket_url'),
        image_url=None,
        venue=r.get('venue'),
        address=None,
        city='Moss',
        lat=None, lon=None,
        category=r.get('category'),
        start=start,
        end=end,
        price=r.get('price'),
        source=source,
        source_type='html',
        source_url=r.get('info_url') or r.get('url'),
        first_seen=datetime.utcnow(),
        last_seen=datetime.utcnow(),
        status='upcoming'
    )

def main():
    init_logging(str(ROOT/'logs'/'maria_log.json'), str(ROOT/'logs'/'maria_errors.json'))
    mgr=MariaDBManager(host='localhost', user='Terje_moss', password='Klokken!12!?!', database='Terje_moss')
    mgr.initialize()
    events=[]
    if MK.exists():
        data=json.loads(MK.read_text(encoding='utf-8'))
        recs=data.get('events') if isinstance(data, dict) else data
        for r in recs:
            events.append(rec_to_event(r,'mosskulturhus'))
    if VS.exists():
        data=json.loads(VS.read_text(encoding='utf-8'))
        recs=data.get('events') if isinstance(data, dict) else data
        for r in recs:
            events.append(rec_to_event(r,'verketscene'))
    # Split per source
    from collections import defaultdict
    groups=defaultdict(list)
    for e in events:
        groups[e.source].append(e)
    totals={'new':0,'updated':0,'duplicates':0}
    for src, lst in groups.items():
        stats=mgr.save_events(lst, src)
        for k,v in stats.items():
            totals[k]+=v
    print('Totals:', totals)

if __name__=='__main__':
    main()
