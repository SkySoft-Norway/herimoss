#!/usr/bin/env python3
"""
Test for Selenium-based Ticketmaster Verket Scene scraper
"""
import ticketmaster_verket_selenium

def test_fetch_verket_events_selenium():
    events = ticketmaster_verket_selenium.fetch_verket_events_selenium()
    assert isinstance(events, list)
    assert all('title' in e and 'source_url' in e for e in events)
    print(f"Fetched {len(events)} events from Verket Scene (Ticketmaster.no, Selenium)")
    for e in events:
        print(f"{e['title']} -> {e['source_url']}")

if __name__ == "__main__":
    test_fetch_verket_events_selenium()
