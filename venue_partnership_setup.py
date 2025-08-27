#!/usr/bin/env python3
"""
Venue Partnership Integration Setup for Moss Events
Strategy #6: Direct partnerships with cultural venues for event feeds
"""

import json
import requests
from datetime import datetime
import sqlite3

class VenuePartnershipManager:
    def __init__(self):
        self.partnerships = {}
        self.api_endpoints = {}
        
    def setup_moss_kulturhus_partnership(self):
        """
        Setup direct partnership with Moss Kulturhus
        """
        
        partnership_proposal = {
            "venue": "Moss Kulturhus",
            "contact_info": {
                "website": "https://www.mosskulturhus.no",
                "email": "post@mosskulturhus.no",
                "phone": "+47 69 92 90 00",
                "address": "Fleischer Bygg, Dronningens gate 83, 1530 Moss"
            },
            
            "partnership_benefits": {
                "for_venue": [
                    "Økt synlighet for arrangementer",
                    "Automatisk markedsføring på herimoss.no",
                    "Detaljert statistikk over interesse",
                    "Gratis tjeneste for event-promotering",
                    "Integrert billettlenking"
                ],
                "for_moss_kalender": [
                    "Oppdatert event-informasjon i sanntid",
                    "Komplette event-detaljer",
                    "Pålitelig datakilde",
                    "Redusert manuelt arbeid"
                ]
            },
            
            "technical_integration": {
                "preferred_methods": [
                    {
                        "method": "JSON API Feed",
                        "description": "REST API som returnerer event data i JSON format",
                        "endpoint_example": "https://www.mosskulturhus.no/api/events",
                        "update_frequency": "Real-time eller daglig",
                        "authentication": "API nøkkel eller basic auth"
                    },
                    {
                        "method": "RSS/XML Feed",
                        "description": "Strukturert RSS feed med event informasjon",
                        "endpoint_example": "https://www.mosskulturhus.no/events.rss",
                        "update_frequency": "Daglig",
                        "authentication": "Ingen (offentlig feed)"
                    },
                    {
                        "method": "Database Integration",
                        "description": "Direkte tilgang til venue's booking database",
                        "access_method": "Readonly database user eller views",
                        "update_frequency": "Real-time",
                        "authentication": "Database credentials"
                    },
                    {
                        "method": "Webhook Notifications",
                        "description": "Venue sender webhook når nye events opprettes",
                        "endpoint": "https://herimoss.no/api/venue-webhook",
                        "trigger": "New event, event update, cancellation",
                        "authentication": "Shared secret eller API key"
                    }
                ]
            },
            
            "data_requirements": {
                "required_fields": [
                    "title", "description", "start_date", "start_time", 
                    "venue", "price", "booking_url", "category"
                ],
                "optional_fields": [
                    "end_date", "end_time", "age_limit", "accessibility_info",
                    "performer", "genre", "duration", "language"
                ],
                "format": "JSON or XML with UTF-8 encoding"
            }
        }
        
        return partnership_proposal
    
    def setup_verket_scene_partnership(self):
        """
        Setup partnership with Verket Scene
        """
        
        partnership = {
            "venue": "Verket Scene",
            "contact_info": {
                "website": "https://www.verketscene.no",
                "email": "post@verketscene.no",
                "address": "Moss"
            },
            "integration_approach": "Similar to Moss Kulturhus",
            "special_considerations": [
                "Smaller venue - may need simpler integration",
                "Possibly using different booking system",
                "May prefer manual submission initially"
            ]
        }
        
        return partnership
    
    def create_partnership_email_template(self):
        """
        Create professional email template for venue partnerships
        """
        
        email_template = """
Emne: Samarbeid om Event-kalender for Moss Kommune - herimoss.no

Hei!

Mitt navn er [DITT_NAVN] og jeg driver herimoss.no - en gratis kulturkalender for Moss kommune som samler alle arrangementer på ett sted.

Vi har allerede integrert arrangementer fra dere gjennom webscraping, men ønsker å tilby et mer direkte og nøyaktig samarbeid.

FORDELENE FOR DERE:
• Økt synlighet for alle deres arrangementer
• Automatisk markedsføring uten ekstra arbeid
• Gratis tjeneste - ingen kostnad for dere
• Detaljert statistikk over interesse for arrangementer
• Direkte lenking til deres billettgystem

FORDELENE FOR OSS:
• Oppdatert og nøyaktig informasjon i sanntid
• Komplett event-data med alle detaljer
• Redusert vedlikehold og manuelt arbeid

TEKNISKE LØSNINGER (velg det som passer best):
1. JSON API - Vi kan lese event-data fra et enkelt API endpoint
2. RSS Feed - Enkelt RSS-feed med event-informasjon
3. Email-varsling - Send oss en strukturert email ved nye events
4. Webhook - Vi mottar automatisk beskjed når dere legger inn nye events

Dette er en win-win situasjon som gir dere mer synlighet og oss bedre data.

Kunne vi hatt en kort samtale om mulighetene?

Med vennlig hilsen,
[DITT_NAVN]
[DIN_EMAIL]
[DIN_TELEFON]

herimoss.no - Moss sin kulturkalender
        """
        
        return email_template
    
    def create_api_specification(self):
        """
        Create API specification for venue partners
        """
        
        api_spec = {
            "title": "Moss Venue Event API Specification",
            "version": "1.0",
            "description": "API specification for venue partners to share event data",
            
            "endpoints": {
                "/api/events": {
                    "method": "GET",
                    "description": "Return all upcoming events",
                    "parameters": {
                        "from_date": "YYYY-MM-DD (optional, default: today)",
                        "to_date": "YYYY-MM-DD (optional, default: +6 months)",
                        "limit": "integer (optional, default: 100)"
                    },
                    "response_format": {
                        "events": [
                            {
                                "id": "unique_event_id",
                                "title": "Event title",
                                "description": "Full description",
                                "start_date": "YYYY-MM-DD",
                                "start_time": "HH:MM",
                                "end_date": "YYYY-MM-DD (optional)",
                                "end_time": "HH:MM (optional)",
                                "venue": "Venue name",
                                "address": "Full address",
                                "price": "Price information",
                                "booking_url": "URL to ticket booking",
                                "category": "concert|theater|exhibition|other",
                                "age_limit": "Age limit if any",
                                "accessibility": "Accessibility information",
                                "created_at": "YYYY-MM-DD HH:MM:SS",
                                "updated_at": "YYYY-MM-DD HH:MM:SS"
                            }
                        ],
                        "total": "total_count",
                        "page": "current_page"
                    }
                }
            },
            
            "authentication": {
                "method": "API Key",
                "header": "X-API-Key: YOUR_API_KEY",
                "alternative": "Basic Authentication"
            }
        }
        
        return api_spec

def create_venue_integration_client():
    """
    Create client code for venue API integration
    """
    
    client_code = '''
#!/usr/bin/env python3
"""
Venue API Integration Client
Fetches events from partner venues with direct API access
"""

import requests
import sqlite3
import json
from datetime import datetime, timedelta
import logging

class VenueAPIClient:
    def __init__(self):
        self.venues = {
            "moss_kulturhus": {
                "name": "Moss Kulturhus",
                "api_url": "https://www.mosskulturhus.no/api/events",
                "api_key": "YOUR_API_KEY_HERE",
                "auth_method": "header"  # or "basic"
            },
            "verket_scene": {
                "name": "Verket Scene", 
                "api_url": "https://www.verketscene.no/api/events",
                "api_key": "YOUR_API_KEY_HERE",
                "auth_method": "header"
            }
        }
        
    def fetch_venue_events(self, venue_id):
        """Fetch events from a specific venue API"""
        
        venue_config = self.venues.get(venue_id)
        if not venue_config:
            logging.error(f"Unknown venue: {venue_id}")
            return []
        
        try:
            headers = {'User-Agent': 'MossKalender/1.0'}
            
            if venue_config['auth_method'] == 'header':
                headers['X-API-Key'] = venue_config['api_key']
            
            response = requests.get(venue_config['api_url'], headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                events = data.get('events', [])
                logging.info(f"Fetched {len(events)} events from {venue_config['name']}")
                return events
            else:
                logging.error(f"API error from {venue_config['name']}: {response.status_code}")
                return []
                
        except Exception as e:
            logging.error(f"Error fetching from {venue_config['name']}: {e}")
            return []
    
    def save_venue_events(self, events, venue_name):
        """Save venue events to database"""
        
        conn = sqlite3.connect('/var/www/vhosts/herimoss.no/pythoncrawler/events.db')
        cursor = conn.cursor()
        
        saved_count = 0
        for event in events:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO events 
                    (title, venue, description, start_time, end_time, source_url, 
                     price_info, category, status, external_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
                """, (
                    event.get('title'),
                    venue_name,
                    event.get('description'),
                    f"{event.get('start_date')} {event.get('start_time')}",
                    f"{event.get('end_date')} {event.get('end_time')}" if event.get('end_date') else None,
                    event.get('booking_url'),
                    event.get('price'),
                    event.get('category', 'other'),
                    event.get('id')
                ))
                saved_count += 1
            except Exception as e:
                logging.error(f"Error saving event {event.get('title')}: {e}")
        
        conn.commit()
        conn.close()
        
        logging.info(f"Saved {saved_count} events from {venue_name}")
        return saved_count
    
    def sync_all_venues(self):
        """Sync events from all partner venues"""
        
        total_events = 0
        
        for venue_id, venue_config in self.venues.items():
            logging.info(f"Syncing events from {venue_config['name']}...")
            
            events = self.fetch_venue_events(venue_id)
            if events:
                saved = self.save_venue_events(events, venue_config['name'])
                total_events += saved
        
        logging.info(f"Total events synced: {total_events}")
        return total_events

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    client = VenueAPIClient()
    client.sync_all_venues()
    '''
    
    return client_code

def main():
    """Main setup function for venue partnerships"""
    print("🤝 SETTING UP VENUE PARTNERSHIPS (Strategy #6)")
    print("=" * 50)
    
    manager = VenuePartnershipManager()
    
    # Moss Kulturhus Partnership
    print("\n🎭 MOSS KULTURHUS PARTNERSHIP:")
    moss_partnership = manager.setup_moss_kulturhus_partnership()
    
    print(f"Venue: {moss_partnership['venue']}")
    print(f"Contact: {moss_partnership['contact_info']['email']}")
    print(f"Phone: {moss_partnership['contact_info']['phone']}")
    
    print("\nBenefits for venue:")
    for benefit in moss_partnership['partnership_benefits']['for_venue']:
        print(f"  • {benefit}")
    
    print("\nTechnical integration options:")
    for method in moss_partnership['technical_integration']['preferred_methods']:
        print(f"  • {method['method']}: {method['description']}")
    
    # Email template
    print(f"\n📧 EMAIL TEMPLATE:")
    email = manager.create_partnership_email_template()
    
    # Save files
    with open('/var/www/vhosts/herimoss.no/pythoncrawler/venue_partnership_proposal.json', 'w', encoding='utf-8') as f:
        json.dump(moss_partnership, f, indent=2, ensure_ascii=False)
    
    with open('/var/www/vhosts/herimoss.no/pythoncrawler/partnership_email_template.txt', 'w', encoding='utf-8') as f:
        f.write(email)
    
    # API specification
    api_spec = manager.create_api_specification()
    with open('/var/www/vhosts/herimoss.no/pythoncrawler/venue_api_specification.json', 'w', encoding='utf-8') as f:
        json.dump(api_spec, f, indent=2, ensure_ascii=False)
    
    # Integration client
    client_code = create_venue_integration_client()
    with open('/var/www/vhosts/herimoss.no/pythoncrawler/venue_api_client.py', 'w') as f:
        f.write(client_code)
    
    print(f"\n✅ Partnership setup files created:")
    print(f"  • venue_partnership_proposal.json")
    print(f"  • partnership_email_template.txt")
    print(f"  • venue_api_specification.json")
    print(f"  • venue_api_client.py")
    
    print(f"\n🚀 NEXT STEPS:")
    print(f"1. Send partnership email to venues")
    print(f"2. Schedule meetings to discuss integration")
    print(f"3. Provide API specification to their developers")
    print(f"4. Test integration with venue_api_client.py")
    print(f"5. Set up automated daily sync")

if __name__ == "__main__":
    main()
