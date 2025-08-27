#!/usr/bin/env python3
"""
Test for ticketmaster_verket_scraper.py
"""
import ticketmaster_verket_scraper

def test_fetch_verket_events():
    events = ticketmaster_verket_scraper.fetch_verket_events()
    assert isinstance(events, list)
    assert all('title' in e and 'source_url' in e for e in events)
    print(f"Fetched {len(events)} events from Verket Scene (Ticketmaster.no)")
    for e in events:
        print(f"{e['title']} -> {e['source_url']}")

if __name__ == "__main__":
    test_fetch_verket_events()
