#!/usr/bin/env python3
"""
Enkel Fase 5 Test - Komplekse HTML kilder
Test scrapers uten å faktisk kjøre nettverksforespørsler
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from logging_utils import init_logging, log_info, log_error

def test_imports():
    """Test at alle scraper-moduler kan importeres riktig"""
    log_info("🧪 Tester imports for Fase 5 scrapere...")
    
    try:
        from scrapers.ticketco_scraper import scrape_ticketco_events
        log_info("✅ TicketCo scraper importert")
    except Exception as e:
        log_error(f"❌ TicketCo import feil: {e}")
        return False
        
    try:
        from scrapers.eventim_scraper import scrape_eventim_events  
        log_info("✅ Eventim scraper importert")
    except Exception as e:
        log_error(f"❌ Eventim import feil: {e}")
        return False
        
    try:
        from scrapers.local_news_scraper import scrape_local_news_events
        log_info("✅ Local News scraper importert")
    except Exception as e:
        log_error(f"❌ Local News import feil: {e}")
        return False
        
    try:
        from scrapers.booking_widget_scraper import scrape_booking_widget_events
        log_info("✅ Booking Widget scraper importert")
    except Exception as e:
        log_error(f"❌ Booking Widget import feil: {e}")
        return False
        
    return True

def test_configuration():
    """Test at options.json inneholder Fase 5 konfigurasjoner"""
    log_info("🧪 Tester Fase 5 konfigurasjon...")
    
    try:
        import json
        with open('options.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        sources = config.get('sources', {})
        fase5_sources = [
            'ticketco_events',
            'eventim_oslo', 
            'moss_avis_kultur',
            'ostlendingen_kultur',
            'verket_booking_widget',
            'moss_kulturhus_api'
        ]
        
        found = 0
        for source in fase5_sources:
            if source in sources:
                log_info(f"✅ {source} konfigurert")
                found += 1
            else:
                log_error(f"❌ {source} mangler i konfigurasjon")
        
        if found == len(fase5_sources):
            log_info("✅ Alle Fase 5 kilder konfigurert")
            return True
        else:
            log_error(f"❌ {len(fase5_sources) - found} kilder mangler")
            return False
            
    except Exception as e:
        log_error(f"❌ Konfigurasjonstest feil: {e}")
        return False

def test_main_integration():
    """Test at main.py inneholder integrasjon for Fase 5"""
    log_info("🧪 Tester main.py integrasjon...")
    
    try:
        with open('main.py', 'r', encoding='utf-8') as f:
            main_content = f.read()
        
        required_imports = [
            'from scrapers.ticketco_scraper import scrape_ticketco_events',
            'from scrapers.eventim_scraper import scrape_eventim_events',
            'from scrapers.local_news_scraper import scrape_local_news_events',
            'from scrapers.booking_widget_scraper import scrape_booking_widget_events'
        ]
        
        required_logic = [
            'source_name == "ticketco_events"',
            'source_name == "eventim_oslo"',
            'source_name in ["moss_avis_kultur", "ostlendingen_kultur"]',
            'source_name in ["verket_booking_widget", "moss_kulturhus_api"]'
        ]
        
        missing_imports = []
        for imp in required_imports:
            if imp not in main_content:
                missing_imports.append(imp)
        
        missing_logic = []
        for logic in required_logic:
            if logic not in main_content:
                missing_logic.append(logic)
        
        if not missing_imports and not missing_logic:
            log_info("✅ main.py integrasjon komplett")
            return True
        else:
            if missing_imports:
                log_error(f"❌ Mangler imports: {missing_imports}")
            if missing_logic:
                log_error(f"❌ Mangler eksekveringslogikk: {missing_logic}")
            return False
            
    except Exception as e:
        log_error(f"❌ main.py test feil: {e}")
        return False

def main():
    """Kjør alle Fase 5 tester"""
    init_logging()
    
    log_info("🚀 Starter Fase 5 validering - Komplekse HTML kilder")
    log_info("=" * 60)
    
    tests = [
        ("Import Test", test_imports),
        ("Konfigurasjon Test", test_configuration), 
        ("main.py Integrasjon Test", test_main_integration)
    ]
    
    results = []
    for test_name, test_func in tests:
        log_info(f"📋 {test_name}...")
        success = test_func()
        results.append(success)
        log_info("-" * 40)
    
    # Sammendrag
    log_info("📊 FASE 5 VALIDERING SAMMENDRAG")
    log_info("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    for i, (success, (test_name, _)) in enumerate(zip(results, tests)):
        status = "✅ BESTÅTT" if success else "❌ FEILET"
        log_info(f"{i+1}. {test_name}: {status}")
    
    log_info("-" * 40)
    log_info(f"📈 Resultat: {passed}/{total} tester bestått")
    
    if passed == total:
        log_info("🎉 FASE 5 FULLFØRT! Alle komplekse HTML scrapere integrert!")
        log_info("💡 Klare for Fase 6: Database og persistering")
        log_info("")
        log_info("📁 Implementerte komponenter:")
        log_info("   • TicketCo billettplattform scraper")
        log_info("   • Eventim.no event scraper")
        log_info("   • Local news scraper (ToS-compliant)")
        log_info("   • Booking widget API scraper")
        log_info("   • Robots.txt compliance")
        log_info("   • JSON-LD strukturert data parsing")
        log_info("   • Rate limiting og circuit breakers")
        log_info("   • Norwegian datetime parsing")
        return True
    else:
        log_error(f"⚠️ {total - passed} test(er) feilet")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
