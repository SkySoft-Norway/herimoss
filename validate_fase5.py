#!/usr/bin/env python3
"""
Fase 5 Validering - Komplekse HTML kilder
Tester alle avanserte scrapere for billettplattformer, nyheter og booking-widgets
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrapers.ticketco_scraper import scrape_ticketco_events
from scrapers.eventim_scraper import scrape_eventim_events  
from scrapers.local_news_scraper import scrape_local_news_events
from scrapers.booking_widget_scraper import scrape_booking_widget_events
from utils import HttpClient
from logging_utils import log_info, log_error

# Test konfigurasjoner for hver scraper
TEST_CONFIGS = {
    "ticketco": {
        "name": "TicketCo Moss",
        "url": "https://www.ticketco.no/no/nb/e?area=moss",
        "max_events": 3,
        "rate_limit": 2.0
    },
    "eventim": {
        "name": "Eventim Oslo",
        "url": "https://www.eventim.no/city/oslo-1/",
        "max_events": 3,
        "rate_limit": 2.0
    },
    "local_news": {
        "name": "Moss Avis Kultur",
        "url": "https://www.moss-avis.no/kultur/",
        "max_events": 3,
        "rate_limit": 5.0,
        "keywords": ["konsert", "festival", "teater", "utstilling"]
    },
    "booking_widget": {
        "name": "Verket Booking",
        "url": "https://verket.no/api/events",
        "max_events": 3,
        "rate_limit": 2.0
    }
}

async def test_scraper(scraper_func, config, scraper_name):
    """Test en enkelt scraper og returner resultater"""
    log_info(f"🧪 Tester {scraper_name}...")
    
    try:
        async with HttpClient() as client:
            events = await scraper_func(config, client)
            
        if not events:
            log_error(f"❌ {scraper_name}: Ingen events funnet")
            return False
            
        log_info(f"✅ {scraper_name}: Fant {len(events)} events")
        
        # Valider første event
        first_event = events[0]
        required_fields = ["title", "start_time", "source"]
        
        missing = [field for field in required_fields if not getattr(first_event, field, None)]
        if missing:
            log_error(f"❌ {scraper_name}: Mangler felt: {missing}")
            return False
            
        log_info(f"   📅 Eksempel: {first_event.title}")
        if first_event.venue:
            log_info(f"   📍 Venue: {first_event.venue}")
        if first_event.description:
            log_info(f"   📝 Beskrivelse: {first_event.description[:100]}...")
            
        return True
        
    except Exception as e:
        log_error(f"❌ {scraper_name}: Feil - {str(e)}")
        return False

async def main():
    """Kjør alle Fase 5 tester"""
    # Initialize logging
    from logging_utils import init_logging
    init_logging()
    
    log_info("🚀 Starter Fase 5 validering - Komplekse HTML kilder")
    log_info("=" * 60)
    
    tests = [
        (scrape_ticketco_events, TEST_CONFIGS["ticketco"], "TicketCo Scraper"),
        (scrape_eventim_events, TEST_CONFIGS["eventim"], "Eventim Scraper"),
        (scrape_local_news_events, TEST_CONFIGS["local_news"], "Local News Scraper"),
        (scrape_booking_widget_events, TEST_CONFIGS["booking_widget"], "Booking Widget Scraper")
    ]
    
    results = []
    for scraper_func, config, name in tests:
        success = await test_scraper(scraper_func, config, name)
        results.append(success)
        log_info("-" * 40)
        await asyncio.sleep(1)  # Gi litt pause mellom tester
    
    # Sammendrag
    log_info("📊 FASE 5 VALIDERING SAMMENDRAG")
    log_info("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    for i, (success, (_, _, name)) in enumerate(zip(results, tests)):
        status = "✅ BESTÅTT" if success else "❌ FEILET"
        log_info(f"{i+1}. {name}: {status}")
    
    log_info("-" * 40)
    log_info(f"📈 Resultat: {passed}/{total} tester bestått")
    
    if passed == total:
        log_info("🎉 FASE 5 FULLFØRT! Alle komplekse HTML scrapere fungerer!")
        log_info("💡 Klare for Fase 6: Database og persistering")
    else:
        log_error(f"⚠️ {total - passed} scraper(e) trenger feilretting")
        return False
        
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
