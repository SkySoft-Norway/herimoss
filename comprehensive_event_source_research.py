#!/usr/bin/env python3
"""
Comprehensive Facebook and Alternative Event Source Research for Moss
"""

import requests
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

def research_moss_facebook_pages():
    """Research and test access to major Moss Facebook pages"""
    
    moss_pages = {
        "Official Venues": {
            "Moss Kulturhus": "https://www.facebook.com/mosskulturhus",
            "Verket Scene": "https://www.facebook.com/verketscene", 
            "Moss Kino": "https://www.facebook.com/mosskino",
            "Galleri Moss": "https://www.facebook.com/gallerimoss",
            "Moss Kunstforening": "https://www.facebook.com/mosskunstforening"
        },
        "Municipal & Tourism": {
            "Moss Kommune": "https://www.facebook.com/mosskommune",
            "Visit Moss": "https://www.facebook.com/visitmoss",
            "Visit Østfold": "https://www.facebook.com/visitostfold",
            "Moss Sentrum": "https://www.facebook.com/mossentrum"
        },
        "Community & Events": {
            "Moss Events": "https://www.facebook.com/mossevents",
            "Moss Live": "https://www.facebook.com/mosslive",
            "Mosseregionen": "https://www.facebook.com/mosseregionen",
            "Moss Bymuseum": "https://www.facebook.com/mossbymuseum",
            "Moss Bibliotek": "https://www.facebook.com/mossbibliotek"
        }
    }
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    
    results = {}
    
    for category, pages in moss_pages.items():
        results[category] = {}
        for name, url in pages.items():
            try:
                response = session.get(url, timeout=5)
                status = response.status_code
                
                # Try to find event indicators
                if status == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Look for event-related content
                    event_indicators = []
                    if soup.find(text=re.compile(r'event|arrangement', re.I)):
                        event_indicators.append("event_text_found")
                    
                    title = soup.find('title')
                    title_text = title.text if title else "No title"
                    
                    results[category][name] = {
                        "url": url,
                        "status": status,
                        "accessible": True,
                        "title": title_text,
                        "event_indicators": event_indicators
                    }
                else:
                    results[category][name] = {
                        "url": url, 
                        "status": status,
                        "accessible": False
                    }
                    
            except Exception as e:
                results[category][name] = {
                    "url": url,
                    "error": str(e),
                    "accessible": False
                }
    
    return results

def generate_facebook_integration_strategies():
    """Generate 10 optimal strategies for Facebook event extraction"""
    
    strategies = [
        {
            "id": 1,
            "name": "RSS Feed Monitoring",
            "description": "Bruke Facebook RSS feeds der tilgjengelig",
            "method": "facebook.com/feeds/page.php?id=PAGE_ID&format=rss20",
            "pros": ["Automatisk", "Strukturert data", "Ingen scraping"],
            "cons": ["Ikke alle sider har RSS", "Begrenset info"],
            "difficulty": "Enkel",
            "reliability": "Middels"
        },
        {
            "id": 2,
            "name": "Graph API med App",
            "description": "Offisiell Facebook Graph API tilgang",
            "method": "Registrer Facebook app, søk om Event API tilgang",
            "pros": ["Offisiell API", "Strukturert data", "Pålitelig"],
            "cons": ["Krever godkjenning", "Rate limits", "Kompleks setup"],
            "difficulty": "Kompleks",
            "reliability": "Høy"
        },
        {
            "id": 3,
            "name": "Webhooks fra Facebook Pages",
            "description": "Bruke Facebook Page webhooks for real-time oppdateringer",
            "method": "Sette opp webhook subscriptions på Facebook pages",
            "pros": ["Real-time", "Automatisk", "Direkte fra Facebook"],
            "cons": ["Krever page admin", "Teknisk kompleks"],
            "difficulty": "Kompleks", 
            "reliability": "Høy"
        },
        {
            "id": 4,
            "name": "IFTTT/Zapier Automation",
            "description": "Bruke tredjepartstjenester for Facebook monitoring",
            "method": "Sette opp IFTTT/Zapier triggers på Facebook posts",
            "pros": ["Ingen koding", "Enkel setup", "Mange integrasjoner"],
            "cons": ["Kostnad", "Begrenset kontroll", "Tredjepartsavhengighet"],
            "difficulty": "Enkel",
            "reliability": "Middels"
        },
        {
            "id": 5,
            "name": "Browser Automation (Selenium)",
            "description": "Automatisert nettleser for å navigere Facebook",
            "method": "Selenium WebDriver for å simulere menneskelig navigasjon",
            "pros": ["Kan håndtere JavaScript", "Full nettleserfunksjonalitet"],
            "cons": ["Brudd på ToS", "Detekterbar", "Ressurskrevende"],
            "difficulty": "Kompleks",
            "reliability": "Lav"
        },
        {
            "id": 6,
            "name": "Email Newsletter Monitoring",
            "description": "Overvåke e-post nyhetsbrev fra venues",
            "method": "Sette opp dedikert e-post for venue newsletters",
            "pros": ["Tillatt metode", "Ofte inneholder event info", "Automatiserbar"],
            "cons": ["Ikke alle har newsletters", "Trenger email parsing"],
            "difficulty": "Middels",
            "reliability": "Middels"
        },
        {
            "id": 7,
            "name": "Social Media Aggregation APIs",
            "description": "Bruke tjenester som samler sosiale medier",
            "method": "APIs som Hootsuite, Sprout Social, eller Buffer",
            "pros": ["Lovlig tilgang", "Flere plattformer", "Profesjonelle verktøy"],
            "cons": ["Kostnad", "Krever business account", "Begrenset til egne sider"],
            "difficulty": "Middels",
            "reliability": "Høy"
        },
        {
            "id": 8,
            "name": "Community Submission Portal",
            "description": "Lar brukere submitte Facebook events de finner",
            "method": "Web form hvor folk kan lime inn Facebook event URLer",
            "pros": ["Community-driven", "Lovlig", "Bred dekning"],
            "cons": ["Manuell arbeid", "Avhengig av brukere", "Trenger moderering"],
            "difficulty": "Enkel",
            "reliability": "Middels"
        },
        {
            "id": 9,
            "name": "Partnership med Venues",
            "description": "Direkte samarbeid med kultursteder for event feeds",
            "method": "Avtaler om JSON/XML feeds eller database tilgang",
            "pros": ["Direkte tilgang", "Oppdatert info", "Langsiktig løsning"],
            "cons": ["Krever forhandlinger", "Begrenset til partnere"],
            "difficulty": "Politisk",
            "reliability": "Høy"
        },
        {
            "id": 10,
            "name": "AI-Powered Content Analysis",
            "description": "Bruke AI til å analysere offentlig tilgjengelig content",
            "method": "NLP analyse av venue websites, sosiale medier, pressemelding",
            "pros": ["Intelligent parsing", "Kan finne skjult info", "Skalerbar"],
            "cons": ["Kompleks utvikling", "Kan være unøyaktig", "Ressurskrevende"],
            "difficulty": "Meget kompleks",
            "reliability": "Variabel"
        }
    ]
    
    return strategies

def generate_alternative_event_sources():
    """Generate 10 alternative event sources to Facebook"""
    
    sources = [
        {
            "id": 1,
            "name": "Eventbrite API",
            "description": "Offisiell API for Eventbrite events i Moss området",
            "url": "https://www.eventbrite.com/platform/api",
            "access_method": "Free API med registrering",
            "coverage": "Mange lokale events, betalte arrangementer",
            "data_quality": "Høy",
            "cost": "Gratis (med limits)"
        },
        {
            "id": 2,
            "name": "Meetup.com API",
            "description": "API for sosiale og kulturelle møter i Moss",
            "url": "https://www.meetup.com/api/",
            "access_method": "GraphQL API med OAuth",
            "coverage": "Community events, workshops, sosiale sammenkomster",
            "data_quality": "Høy",
            "cost": "Gratis"
        },
        {
            "id": 3,
            "name": "Kommunale RSS feeds",
            "description": "Moss Kommune og andre offentlige RSS feeds",
            "url": "https://www.moss.kommune.no/rss",
            "access_method": "Direkte RSS parsing",
            "coverage": "Offentlige arrangementer, kulturprogrammer",
            "data_quality": "Høy",
            "cost": "Gratis"
        },
        {
            "id": 4,
            "name": "Lokale Avis APIs/RSS",
            "description": "Moss Avis, Østfold24, andre lokale medier",
            "url": "https://www.mossavis.no/rss",
            "access_method": "RSS feeds og web scraping",
            "coverage": "Event omtaler, kulturstoff, annonser",
            "data_quality": "Middels",
            "cost": "Gratis"
        },
        {
            "id": 5,
            "name": "Bibliotek Event APIs",
            "description": "Norske bibliotek har ofte åpne event APIs",
            "url": "https://www.bibkat.no/api",
            "access_method": "REST API eller RSS",
            "coverage": "Bibliotek events, foredrag, utstillinger",
            "data_quality": "Høy",
            "cost": "Gratis"
        },
        {
            "id": 6,
            "name": "Tourism Board APIs",
            "description": "Visit Norway, Visit Østfold event data",
            "url": "https://www.visitnorway.com/api",
            "access_method": "Tourism API med nøkkel",
            "coverage": "Turistrelaterte kulturevents",
            "data_quality": "Høy",
            "cost": "Mulig kostnad"
        },
        {
            "id": 7,
            "name": "Venue Direct APIs",
            "description": "Direkte integrasjon med venue booking systemer",
            "url": "Varies by venue",
            "access_method": "Partnership agreements",
            "coverage": "Komplett event info fra venues",
            "data_quality": "Meget høy",
            "cost": "Avtalt"
        },
        {
            "id": 8,
            "name": "Google Events Structured Data",
            "description": "Scrape Google event search results",
            "url": "https://www.google.com/search?q=events+moss+norway",
            "access_method": "Structured data extraction",
            "coverage": "Events Google har indeksert",
            "data_quality": "Middels",
            "cost": "Gratis"
        },
        {
            "id": 9,
            "name": "Cultural Institution Networks",
            "description": "Nettverk av kulturinstitusjoner med delte feeds",
            "url": "https://www.kulturradet.no/api",
            "access_method": "Kulturrådet og lignende APIs",
            "coverage": "Støttede kulturarrangementer",
            "data_quality": "Høy",
            "cost": "Gratis"
        },
        {
            "id": 10,
            "name": "University/School Event Feeds",
            "description": "HIOA Moss, videregående skoler, folkehøgskoler",
            "url": "https://www.hioa.no/events/rss",
            "access_method": "Institusjons RSS eller APIs", 
            "coverage": "Utdanning-relaterte kulturevents",
            "data_quality": "Høy",
            "cost": "Gratis"
        }
    ]
    
    return sources

def generate_ticketmaster_alternatives():
    """Generate alternatives to Ticketmaster after being blocked"""
    
    alternatives = [
        {
            "name": "Billettservice.no",
            "description": "Norsk billettjeneste, kan ha API",
            "url": "https://www.billettservice.no",
            "api_available": "Ukjent - kontakt nødvendig"
        },
        {
            "name": "Ticket.no", 
            "description": "Alternativ norsk billettformidler",
            "url": "https://www.ticket.no",
            "api_available": "Mulig API tilgang"
        },
        {
            "name": "Direktekontakt med venues",
            "description": "Bypass billettformidlere helt",
            "method": "Direkte booking systemer fra venues"
        }
    ]
    
    return alternatives

if __name__ == "__main__":
    print("🔍 FORSKINGSRAPPORT: Facebook og Alternative Event-kilder for Moss")
    print("=" * 70)
    
    # Test Facebook access
    print("\n📘 TESTING FACEBOOK PAGE ACCESS...")
    fb_results = research_moss_facebook_pages()
    
    accessible_count = 0
    for category, pages in fb_results.items():
        print(f"\n{category}:")
        for name, result in pages.items():
            if result.get('accessible'):
                print(f"  ✅ {name}: Tilgjengelig")
                accessible_count += 1
            else:
                print(f"  ❌ {name}: Ikke tilgjengelig ({result.get('status', 'error')})")
    
    print(f"\n📊 Resultat: {accessible_count} av {sum(len(pages) for pages in fb_results.values())} sider tilgjengelige")
    
    # Generate strategies
    print("\n🎯 10 OPTIMALE FACEBOOK INTEGRASJONSSTRATEGIER:")
    print("=" * 50)
    strategies = generate_facebook_integration_strategies()
    
    for strategy in strategies:
        print(f"\n{strategy['id']}. {strategy['name']}")
        print(f"   📝 {strategy['description']}")
        print(f"   ⚡ Vanskelighetsgrad: {strategy['difficulty']}")
        print(f"   📊 Pålitelighet: {strategy['reliability']}")
        print(f"   ✅ Fordeler: {', '.join(strategy['pros'][:2])}")
    
    # Generate alternative sources
    print("\n\n🌐 10 ALTERNATIVE EVENT-KILDER:")
    print("=" * 40)
    sources = generate_alternative_event_sources()
    
    for source in sources:
        print(f"\n{source['id']}. {source['name']}")
        print(f"   📝 {source['description']}")
        print(f"   💰 Kostnad: {source['cost']}")
        print(f"   📊 Datakvalitet: {source['data_quality']}")
    
    # Ticketmaster alternatives
    print(f"\n\n🎫 ALTERNATIVER TIL TICKETMASTER:")
    print("=" * 35)
    alternatives = generate_ticketmaster_alternatives()
    
    for alt in alternatives:
        print(f"• {alt['name']}: {alt['description']}")
    
    print(f"\n✅ Rapport fullført: {len(strategies)} Facebook-strategier og {len(sources)} alternative kilder identifisert")
