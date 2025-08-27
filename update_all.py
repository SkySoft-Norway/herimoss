#!/usr/bin/env python3
"""Orchestrator: Sync Ticketmaster events then regenerate site (HTML + ICS + RSS).

Usage:
  python3 update_all.py            # simple mode regeneration
  python3 update_all.py --enhanced # use enhanced calendar (if implemented)
  ENRICH_DESCRIPTIONS=1 ENRICH_MAX=5 python3 update_all.py

Respects existing environment variables in generate_enhanced_calendar.py for enrichment and feed skipping.
"""
import os
import sys
from datetime import datetime

from ticketmaster_client import MossTicketmasterClient
import generate_enhanced_calendar as gen

def main():
    use_enhanced = '--enhanced' in sys.argv
    print("[ORCH] Starting full update at", datetime.now())
    # 1. Sync Ticketmaster
    try:
        client = MossTicketmasterClient()
        saved = client.sync_ticketmaster_events()
        print(f"[ORCH] Ticketmaster sync done: {saved} events (may include updates).")
    except Exception as e:
        print(f"[ORCH] Ticketmaster sync failed: {e}")
    # 2. Generate HTML
    try:
        if use_enhanced:
            html = gen.generate_enhanced_calendar_html(use_mariadb=gen.HAS_MYSQL)
        else:
            html = gen.generate_simple_listing(use_mariadb=gen.HAS_MYSQL)
        out_html = '/var/www/vhosts/herimoss.no/httpdocs/index.html'
        with open(out_html, 'w', encoding='utf-8') as f:
            f.write(html)
        print('[ORCH] HTML written.')
        # 3. Feeds
        if os.getenv('SKIP_ICS','0') != '1':
            ics = gen.generate_ical_feed(use_mariadb=gen.HAS_MYSQL)
            with open('/var/www/vhosts/herimoss.no/httpdocs/events.ics','w', encoding='utf-8') as f:
                f.write(ics)
            print('[ORCH] ICS updated.')
        if os.getenv('SKIP_RSS','0') != '1':
            rss = gen.generate_rss_feed(use_mariadb=gen.HAS_MYSQL)
            with open('/var/www/vhosts/herimoss.no/httpdocs/rss.xml','w', encoding='utf-8') as f:
                f.write(rss)
            print('[ORCH] RSS updated.')
    except Exception as e:
        print(f"[ORCH] Generation failed: {e}")
    print('[ORCH] Done.')

if __name__ == '__main__':
    main()
