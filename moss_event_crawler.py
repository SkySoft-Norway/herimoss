#!/usr/bin/env python3
"""
Moss Event Crawler with Ticketmaster Integration
Replaces Verket Scene scraping with comprehensive Ticketmaster API data
"""

import asyncio
import sys
import argparse
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path

from logging_utils import init_logging, log_info, log_error, log_warning
from database import get_database, DatabaseManager
from models import Event, Statistics
from ticketmaster_api_client import fetch_ticketmaster_events
from dedupe import deduplicate_event_list


class MossEventCrawler:
    """Enhanced event crawler with Ticketmaster API integration"""
    
    def __init__(self, 
                 max_events: Optional[int] = None,
                 dry_run: bool = False,
                 radius_km: int = 20,
                 include_legacy_scrapers: bool = True):
        self.max_events = max_events
        self.dry_run = dry_run
        self.radius_km = radius_km  # Search radius around Moss
        self.include_legacy_scrapers = include_legacy_scrapers
        self.shutdown_requested = False
        self.stats = Statistics(start_time=datetime.now())
        
        # Initialize logging
        init_logging()
        
    async def crawl_ticketmaster_events(self) -> List[Event]:
        """Crawl events from Ticketmaster API with Norwegian locale"""
        log_info(f"🎫 Starting Ticketmaster API crawl (radius: {self.radius_km}km)")
        
        try:
            events = await fetch_ticketmaster_events(radius_km=self.radius_km)
            
            # Apply event limit if specified
            if self.max_events and len(events) > self.max_events:
                events = events[:self.max_events]
                log_info(f"📊 Limited to {self.max_events} events")
            
            log_info(f"✅ Fetched {len(events)} events from Ticketmaster")
            return events
            
        except Exception as e:
            log_error("ticketmaster", f"Ticketmaster crawl failed: {e}")
            return []
    
    async def crawl_legacy_sources(self) -> List[Event]:
        """Crawl legacy sources including Moss Kulturhus and other venues"""
        log_info("📰 Starting legacy source crawling...")
        
        events = []
        
        if not self.include_legacy_scrapers:
            log_info("📊 Legacy scrapers disabled")
            return events
        
        # Try importing and running legacy scrapers
        try:
            # Moss Kulturhus scraper
            try:
                from mosskulturhus_scraper_simple import scrape
                import json
                from pathlib import Path
                
                log_info("🔄 Running Moss Kulturhus scraper...")
                
                # Run the scraper with detail enrichment
                scrape(detail=True)
                
                # Read the generated JSON file
                json_file = Path("/var/www/vhosts/herimoss.no/pythoncrawler/mosskulturhus_events.json")
                if json_file.exists():
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Convert to Event objects
                    kulturhus_events = []
                    for event_data in data.get('events', []):
                        try:
                            # Parse start time
                            start_time = None
                            if event_data.get('start'):
                                start_time = datetime.fromisoformat(event_data['start'])
                            
                            # Create Event object with required fields
                            from uuid import uuid4
                            event = Event(
                                id=str(uuid4()),
                                title=event_data.get('title', 'Unknown Event'),
                                description=event_data.get('description', ''),
                                start=start_time,
                                end=None,  # Moss Kulturhus events typically don't have end times
                                venue=event_data.get('venue', 'Moss Kulturhus'),
                                location="Moss, Norway",
                                price=event_data.get('price', ''),
                                ticket_url=event_data.get('ticket_url', ''),
                                info_url=event_data.get('info_url', ''),
                                source="Moss Kulturhus",
                                source_type="html",
                                category="Kultur",
                                age_restriction="",
                                organizer="Moss Kulturhus",
                                first_seen=datetime.now(),
                                last_seen=datetime.now()
                            )
                            kulturhus_events.append(event)
                            
                        except Exception as e:
                            log_error("kulturhus_parse", f"Failed to parse event {event_data.get('title', 'unknown')}: {e}")
                    
                    if kulturhus_events:
                        events.extend(kulturhus_events)
                        log_info(f"🏛️  Moss Kulturhus: {len(kulturhus_events)} events")
                    else:
                        log_info("🏛️  Moss Kulturhus: No valid events found")
                else:
                    log_warning("legacy_scraper", "Moss Kulturhus JSON file not generated")
                    
            except ImportError:
                log_warning("legacy_scraper", "Moss Kulturhus scraper not available")
            except Exception as e:
                log_error("legacy_scraper", f"Moss Kulturhus scraper failed: {e}")
            
            # Facebook Events scraper
            try:
                from facebook_event_scraper import crawl_facebook_events
                log_info("🔄 Running Facebook Events scraper...")
                facebook_events = await crawl_facebook_events()
                if facebook_events:
                    events.extend(facebook_events)
                    log_info(f"📘 Facebook Events: {len(facebook_events)} events")
                else:
                    log_info("📘 Facebook Events: No events found")
            except ImportError:
                log_warning("legacy_scraper", "Facebook Events scraper not available")
            except Exception as e:
                log_error("legacy_scraper", f"Facebook Events scraper failed: {e}")
            
            # Tix/Billetto scraper for Moss venues
            try:
                from tix_mosskulturhus_scraper import crawl_tix_events
                log_info("🔄 Running Tix/Billetto scraper...")
                tix_events = await crawl_tix_events()
                if tix_events:
                    events.extend(tix_events)
                    log_info(f"🎫 Tix/Billetto: {len(tix_events)} events")
                else:
                    log_info("🎫 Tix/Billetto: No events found")
            except ImportError:
                log_warning("legacy_scraper", "Tix/Billetto scraper not available")
            except Exception as e:
                log_error("legacy_scraper", f"Tix/Billetto scraper failed: {e}")
            
            # Moss Bibliotekene scraper
            try:
                from moss_bibliotek_scraper import crawl_moss_bibliotek_events
                log_info("🔄 Running Moss Bibliotekene scraper...")
                bibliotek_events = await crawl_moss_bibliotek_events()
                if bibliotek_events:
                    events.extend(bibliotek_events)
                    log_info(f"📚 Moss Bibliotekene: {len(bibliotek_events)} events")
                else:
                    log_info("📚 Moss Bibliotekene: No events found")
            except ImportError:
                log_warning("legacy_scraper", "Moss Bibliotekene scraper not available")
            except Exception as e:
                log_error("legacy_scraper", f"Moss Bibliotekene scraper failed: {e}")
            
            # Visit Østfold scraper
            try:
                from visitostfold_scraper import crawl_visitostfold_events
                log_info("🔄 Running Visit Østfold scraper...")
                visitostfold_events = await crawl_visitostfold_events()
                if visitostfold_events:
                    events.extend(visitostfold_events)
                    log_info(f"🌐 Visit Østfold: {len(visitostfold_events)} events")
                else:
                    log_info("🌐 Visit Østfold: No events found")
            except ImportError:
                log_warning("legacy_scraper", "Visit Østfold scraper not available")
            except Exception as e:
                log_error("legacy_scraper", f"Visit Østfold scraper failed: {e}")
            
            # Moss Avis scraper
            try:
                from moss_avis_scraper import crawl_moss_avis_events
                log_info("🔄 Running Moss Avis scraper...")
                moss_avis_events = await crawl_moss_avis_events()
                if moss_avis_events:
                    events.extend(moss_avis_events)
                    log_info(f"📰 Moss Avis: {len(moss_avis_events)} events")
                else:
                    log_info("📰 Moss Avis: No events found")
            except ImportError:
                log_warning("legacy_scraper", "Moss Avis scraper not available")
            except Exception as e:
                log_error("legacy_scraper", f"Moss Avis scraper failed: {e}")
            
            # Galleri F15 scraper
            try:
                from galleri_f15_scraper import crawl_galleri_f15_events
                log_info("🔄 Running Galleri F15 scraper...")
                galleri_events = await crawl_galleri_f15_events()
                if galleri_events:
                    events.extend(galleri_events)
                    log_info(f"🎨 Galleri F15: {len(galleri_events)} events")
                else:
                    log_info("🎨 Galleri F15: No events found")
            except ImportError:
                log_warning("legacy_scraper", "Galleri F15 scraper not available")
            except Exception as e:
                log_error("legacy_scraper", f"Galleri F15 scraper failed: {e}")
            
            # Odeon Kino scraper
            try:
                from odeon_kino_scraper import crawl_odeon_kino_events
                log_info("🔄 Running Odeon Kino scraper...")
                kino_events = await crawl_odeon_kino_events()
                if kino_events:
                    events.extend(kino_events)
                    log_info(f"🎬 Odeon Kino: {len(kino_events)} events")
                else:
                    log_info("🎬 Odeon Kino: No events found")
            except ImportError:
                log_warning("legacy_scraper", "Odeon Kino scraper not available")
            except Exception as e:
                log_error("legacy_scraper", f"Odeon Kino scraper failed: {e}")
                
        except Exception as e:
            log_error("legacy_crawl", f"Legacy crawl setup failed: {e}")
        
        log_info(f"📰 Legacy crawl completed: {len(events)} events from {len([s for s in ['Moss Kulturhus', 'Facebook', 'Tix/Billetto', 'Other venues'] if events])} sources")
        return events
    
    async def deduplicate_events(self, events: List[Event]) -> List[Event]:
        """Advanced deduplication with Ticketmaster priority"""
        log_info(f"🔍 Deduplicating {len(events)} events...")
        
        if not events:
            return events
        
        try:
            # Prioritize Ticketmaster events over scraped data
            tm_events = [e for e in events if e.source == "Ticketmaster"]
            other_events = [e for e in events if e.source != "Ticketmaster"]
            
            log_info(f"📊 {len(tm_events)} Ticketmaster events, {len(other_events)} other events")
            
            # Use existing deduplication logic
            seen_hashes = set()
            unique_events, updated_hashes, duplicate_mappings = deduplicate_event_list(
                events, seen_hashes, fuzzy_threshold=85
            )
            
            log_info(f"✨ Deduplication complete: {len(unique_events)} unique events")
            log_info(f"🗑️  Removed {len(events) - len(unique_events)} duplicates")
            
            return unique_events
            
        except Exception as e:
            log_error("deduplication", f"Deduplication failed: {e}")
            return events  # Return original events if deduplication fails
    
    async def save_events_to_database(self, events: List[Event]) -> Dict[str, int]:
        """Save events to database with enhanced Ticketmaster data"""
        if not events:
            return {'new': 0, 'updated': 0, 'duplicates': 0}
        
        log_info(f"💾 Saving {len(events)} events to database...")
        
        try:
            db = await get_database()
            
            # Save events by source for better tracking
            tm_events = [e for e in events if e.source == "Ticketmaster"]
            other_events = [e for e in events if e.source != "Ticketmaster"]
            
            total_stats = {'new': 0, 'updated': 0, 'duplicates': 0}
            
            # Save Ticketmaster events with priority
            if tm_events:
                tm_stats = await db.save_events(tm_events, "Ticketmaster")
                for key in total_stats:
                    total_stats[key] += tm_stats.get(key, 0)
                log_info(f"🎫 Ticketmaster: {tm_stats['new']} new, {tm_stats['updated']} updated")
            
            # Save other events
            if other_events:
                other_stats = await db.save_events(other_events, "Legacy Sources")
                for key in total_stats:
                    total_stats[key] += other_stats.get(key, 0)
                log_info(f"📰 Legacy: {other_stats['new']} new, {other_stats['updated']} updated")
            
            log_info(f"✅ Database save complete: {total_stats}")
            return total_stats
            
        except Exception as e:
            log_error("database", f"Failed to save events: {e}")
            return {'new': 0, 'updated': 0, 'duplicates': 0, 'errors': 1}
    
    async def generate_html_output(self, events: List[Event]) -> Optional[str]:
        """Generate HTML calendar output"""
        log_info("🌐 Generating HTML calendar output...")
        
        try:
            # This would integrate with existing HTML generation
            output_path = "/var/www/vhosts/herimoss.no/httpdocs/index.html"
            
            if self.dry_run:
                log_info("🔍 Dry run: HTML generation skipped")
                return None
            
            # Generate enhanced HTML with Ticketmaster data
            await self._generate_enhanced_html(events, output_path)
            
            log_info(f"🌐 HTML generated: {output_path}")
            return output_path
            
        except Exception as e:
            log_error("html_generation", f"HTML generation failed: {e}")
            return None
    
    async def _generate_enhanced_html(self, events: List[Event], output_path: str):
        """Generate HTML with enhanced Ticketmaster features"""
        
        # Sort events by date
        sorted_events = sorted(events, key=lambda e: e.start)
        
        # Separate upcoming and past events
        now = datetime.now()
        upcoming_events = [e for e in sorted_events if e.start >= now]
        past_events = [e for e in sorted_events if e.start < now]
        
        html_content = f"""
<!DOCTYPE html>
<html lang="no">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Oppdatert kulturkalender for Moss med arrangementer fra Ticketmaster, Moss Kulturhus og andre venues. Se kommende konserter, teater, stand-up og kulturarrangementer.">
    <meta name="keywords" content="Moss, kulturkalender, arrangementer, konserter, teater, Verket Scene, Moss Kulturhus, Ticketmaster, billetter">
    <meta name="author" content="Moss Kulturkalender">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="https://herimoss.no/">
    
    <!-- Open Graph / Facebook -->
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://herimoss.no/">
    <meta property="og:title" content="Moss Kulturkalender - Alle arrangementer på ett sted">
    <meta property="og:description" content="Se alle kulturarrangementer i Moss. Oppdatert automatisk med data fra Ticketmaster og lokale venues.">
    <meta property="og:locale" content="nb_NO">
    
    <!-- Twitter -->
    <meta property="twitter:card" content="summary_large_image">
    <meta property="twitter:url" content="https://herimoss.no/">
    <meta property="twitter:title" content="Moss Kulturkalender">
    <meta property="twitter:description" content="Se alle kulturarrangementer i Moss på ett sted">
    
    <title>Moss Kulturkalender - Alle arrangementer i Moss på ett sted</title>
    
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; background: #f8f9fa; }}
        
        /* Header styles */
        .main-header {{ background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%); color: white; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header-content {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        .header h1 {{ font-size: 2.5em; margin-bottom: 5px; font-weight: 300; }}
        .header p {{ opacity: 0.9; font-size: 1.1em; }}
        
        /* Search bar */
        .search-section {{ margin: 20px 0; }}
        .search-container {{ position: relative; max-width: 500px; margin: 0 auto; }}
        .search-input {{ width: 100%; padding: 15px 50px 15px 20px; border: none; border-radius: 25px; 
                        font-size: 1.1em; background: rgba(255,255,255,0.9); color: #333; 
                        box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
        .search-input::placeholder {{ color: #666; }}
        .search-button {{ position: absolute; right: 5px; top: 50%; transform: translateY(-50%); 
                         background: #3498db; border: none; border-radius: 50%; width: 40px; height: 40px; 
                         color: white; cursor: pointer; display: flex; align-items: center; justify-content: center; }}
        .search-button:hover {{ background: #2980b9; }}
        
        /* Navigation */
        .nav-bar {{ background: rgba(255,255,255,0.1); margin-top: 20px; border-radius: 5px; }}
        .nav-list {{ list-style: none; display: flex; flex-wrap: wrap; }}
        .nav-list li {{ margin-right: 30px; }}
        .nav-list a {{ color: white; text-decoration: none; padding: 15px 0; display: block; font-weight: 500; transition: opacity 0.3s; }}
        .nav-list a:hover {{ opacity: 0.8; }}
        .nav-list a.active {{ border-bottom: 2px solid #3498db; }}
        .nav-list a.tip-button {{ background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%); 
                                 color: white; padding: 8px 16px; border-radius: 20px; 
                                 text-decoration: none; transition: all 0.3s; font-weight: 600; }}
        .nav-list a.tip-button:hover {{ background: linear-gradient(135deg, #e67e22 0%, #d35400 100%); 
                                       transform: translateY(-2px); box-shadow: 0 4px 12px rgba(243, 156, 18, 0.3); }}
        
        /* Main content */
        .container {{ max-width: 1200px; margin: 0 auto; padding: 30px 20px; }}
        
        /* Stats section */
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .stat-card {{ background: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.07); text-align: center; }}
        .stat-number {{ font-size: 2.5em; font-weight: bold; color: #2c3e50; }}
        .stat-label {{ color: #666; margin-top: 5px; }}
        .stat-card.ticketmaster {{ border-top: 4px solid #0066cc; }}
        .stat-card.kulturhus {{ border-top: 4px solid #e74c3c; }}
        .stat-card.bibliotek {{ border-top: 4px solid #8e44ad; }}
        .stat-card.visitostfold {{ border-top: 4px solid #27ae60; }}
        .stat-card.mossavis {{ border-top: 4px solid #f39c12; }}
        .stat-card.gallerif15 {{ border-top: 4px solid #e67e22; }}
        .stat-card.odeokino {{ border-top: 4px solid #2c3e50; }}
        .stat-card.total {{ border-top: 4px solid #27ae60; }}
        
        /* Section titles */
        .section-title {{ font-size: 1.8em; margin: 40px 0 20px; color: #2c3e50; font-weight: 300; }}
        
        /* Latest events grid */
        .latest-events-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; margin-bottom: 40px; }}
        .latest-event {{ position: relative; animation: slideInUp 0.6s ease-out; }}
        .latest-event:nth-child(2) {{ animation-delay: 0.2s; }}
        .latest-event:nth-child(3) {{ animation-delay: 0.4s; }}
        
        @keyframes slideInUp {{
            from {{ opacity: 0; transform: translateY(30px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        
        .new-badge {{ background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); 
                     color: white; padding: 2px 8px; border-radius: 12px; 
                     font-size: 0.7em; font-weight: bold; margin-left: 10px;
                     animation: pulse 2s infinite; }}
        
        @keyframes pulse {{
            0% {{ transform: scale(1); }}
            50% {{ transform: scale(1.1); }}
            100% {{ transform: scale(1); }}
        }}
        
        /* Event grid */
        .event-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 25px; }}
        .event-card {{ background: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); overflow: hidden; transition: transform 0.3s, box-shadow 0.3s; }}
        .event-card:hover {{ transform: translateY(-5px); box-shadow: 0 8px 25px rgba(0,0,0,0.15); }}
        .event-card.ticketmaster {{ border-left: 5px solid #0066cc; }}
        .event-card.kulturhus {{ border-left: 5px solid #e74c3c; }}
        .event-card.bibliotek {{ border-left: 5px solid #8e44ad; }}
        .event-card.visitostfold {{ border-left: 5px solid #27ae60; }}
        .event-card.mossavis {{ border-left: 5px solid #f39c12; }}
        .event-card.gallerif15 {{ border-left: 5px solid #e67e22; }}
        .event-card.odeokino {{ border-left: 5px solid #2c3e50; }}
        .event-card.other {{ border-left: 5px solid #95a5a6; }}
        
        .event-content {{ padding: 25px; }}
        .event-title {{ font-size: 1.3em; font-weight: 600; margin-bottom: 15px; line-height: 1.3; }}
        .event-meta {{ color: #666; margin-bottom: 10px; display: flex; align-items: center; }}
        .event-meta i {{ margin-right: 8px; }}
        .event-price {{ font-weight: bold; color: #e74c3c; }}
        .event-venue {{ color: #3498db; font-weight: 500; }}
        .event-category {{ color: #7f8c8d; font-style: italic; }}
        
        /* Source badges */
        .source-badge {{ display: inline-block; padding: 3px 8px; border-radius: 12px; font-size: 0.8em; font-weight: 500; margin-left: 10px; }}
        .tm-badge {{ background: #0066cc; color: white; }}
        .kulturhus-badge {{ background: #e74c3c; color: white; }}
        .bibliotek-badge {{ background: #8e44ad; color: white; }}
        .visitostfold-badge {{ background: #27ae60; color: white; }}
        .mossavis-badge {{ background: #f39c12; color: white; }}
        .gallerif15-badge {{ background: #e67e22; color: white; }}
        .odeokino-badge {{ background: #2c3e50; color: white; }}
        .other-badge {{ background: #95a5a6; color: white; }}
        
        /* Availability status */
        .availability {{ padding: 6px 12px; border-radius: 6px; font-size: 0.9em; margin: 12px 0; font-weight: 500; }}
        .availability.available {{ background: #d4edda; color: #155724; }}
        .availability.sold-out {{ background: #f8d7da; color: #721c24; }}
        .availability.unavailable {{ background: #fff3cd; color: #856404; }}
        
        /* Event description */
        .event-description {{ color: #555; font-size: 0.95em; margin: 15px 0; line-height: 1.5; }}
        
        /* Ticket buttons */
        .ticket-button {{ display: inline-block; background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); color: white; 
                          padding: 12px 24px; text-decoration: none; border-radius: 25px; margin-top: 15px; 
                          font-weight: 600; transition: all 0.3s; }}
        .ticket-button:hover {{ background: linear-gradient(135deg, #c0392b 0%, #a93226 100%); transform: translateY(-2px); }}
        .ticket-button.sold-out {{ background: #95a5a6; cursor: not-allowed; }}
        .ticket-button.sold-out:hover {{ transform: none; }}
        
        /* Footer */
        .main-footer {{ background: #2c3e50; color: white; margin-top: 50px; }}
        .footer-content {{ max-width: 1200px; margin: 0 auto; padding: 40px 20px; }}
        .footer-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 40px; }}
        .footer-section h3 {{ margin-bottom: 15px; font-size: 1.2em; }}
        .footer-section ul {{ list-style: none; }}
        .footer-section ul li {{ margin-bottom: 8px; }}
        .footer-section ul li a {{ color: #bdc3c7; text-decoration: none; transition: color 0.3s; }}
        .footer-section ul li a:hover {{ color: white; }}
        .footer-bottom {{ text-align: center; padding-top: 30px; border-top: 1px solid #34495e; margin-top: 30px; color: #bdc3c7; }}
        /* Pagination */
        .pagination-container {{ display: flex; justify-content: space-between; align-items: center; margin: 30px 0; 
                               background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.07); }}
        .pagination-info {{ color: #666; }}
        .pagination {{ display: flex; align-items: center; gap: 10px; }}
        .pagination button {{ background: #f8f9fa; border: 1px solid #dee2e6; color: #495057; padding: 8px 12px; 
                            border-radius: 5px; cursor: pointer; transition: all 0.3s; }}
        .pagination button:hover {{ background: #3498db; color: white; border-color: #3498db; }}
        .pagination button.active {{ background: #3498db; color: white; border-color: #3498db; }}
        .pagination button:disabled {{ background: #f8f9fa; color: #6c757d; cursor: not-allowed; border-color: #dee2e6; }}
        .pagination button:disabled:hover {{ background: #f8f9fa; color: #6c757d; border-color: #dee2e6; }}
        .show-all-btn {{ background: #27ae60; color: white; padding: 10px 20px; border: none; border-radius: 5px; 
                       cursor: pointer; font-weight: 500; transition: background 0.3s; }}
        .show-all-btn:hover {{ background: #219a52; }}
        
        /* Filter/search controls */
        .controls-section {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.07); margin-bottom: 20px; }}
        .search-stats {{ color: #666; font-size: 0.9em; margin-top: 10px; text-align: center; }}
        
        /* Hidden class for filtered items */
        .hidden {{ display: none !important; }}
        
        .back-to-top {{ position: fixed; bottom: 30px; right: 30px; background: #3498db; color: white; 
                        padding: 12px 16px; border-radius: 50%; text-decoration: none; box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                        opacity: 0; transition: opacity 0.3s; }}
        .back-to-top.visible {{ opacity: 1; }}
        
        /* Tip Form Modal */
        .tip-modal {{ display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; 
                     background: rgba(0,0,0,0.8); backdrop-filter: blur(5px); }}
        .tip-modal.show {{ display: flex; align-items: center; justify-content: center; }}
        .tip-form-container {{ background: white; border-radius: 15px; max-width: 600px; width: 90%; max-height: 90vh; 
                              overflow-y: auto; box-shadow: 0 20px 60px rgba(0,0,0,0.3); animation: modalSlideIn 0.3s ease-out; }}
        @keyframes modalSlideIn {{ from {{ transform: scale(0.7) translateY(-50px); opacity: 0; }} 
                                  to {{ transform: scale(1) translateY(0); opacity: 1; }} }}
        .tip-form-header {{ background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%); color: white; 
                           padding: 25px; border-radius: 15px 15px 0 0; }}
        .tip-form-header h2 {{ margin: 0; font-size: 1.8em; display: flex; align-items: center; }}
        .tip-form-header p {{ margin: 10px 0 0; opacity: 0.9; }}
        .tip-form-body {{ padding: 30px; }}
        .tip-form-close {{ position: absolute; top: 15px; right: 20px; background: none; border: none; 
                          color: white; font-size: 28px; cursor: pointer; opacity: 0.8; transition: opacity 0.3s; }}
        .tip-form-close:hover {{ opacity: 1; }}
        
        .form-group {{ margin-bottom: 20px; }}
        .form-label {{ display: block; margin-bottom: 8px; font-weight: 600; color: #2c3e50; }}
        .form-input, .form-textarea {{ width: 100%; padding: 12px 15px; border: 2px solid #ecf0f1; 
                                      border-radius: 8px; font-size: 1em; transition: border-color 0.3s; box-sizing: border-box; }}
        .form-input:focus, .form-textarea:focus {{ outline: none; border-color: #f39c12; }}
        .form-textarea {{ min-height: 120px; resize: vertical; font-family: inherit; }}
        .form-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }}
        
        .form-submit {{ background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); color: white; 
                       border: none; padding: 15px 30px; border-radius: 8px; font-size: 1.1em; 
                       font-weight: 600; cursor: pointer; transition: all 0.3s; width: 100%; }}
        .form-submit:hover {{ background: linear-gradient(135deg, #2ecc71 0%, #27ae60 100%); 
                             transform: translateY(-2px); box-shadow: 0 6px 20px rgba(39, 174, 96, 0.3); }}
        .form-submit:disabled {{ background: #95a5a6; cursor: not-allowed; transform: none; box-shadow: none; }}
        
        .spam-protection {{ position: absolute; left: -9999px; opacity: 0; }}
        .success-message {{ background: #d4edda; color: #155724; padding: 15px; border-radius: 8px; 
                           border: 1px solid #c3e6cb; margin-bottom: 20px; }}
        .error-message {{ background: #f8d7da; color: #721c24; padding: 15px; border-radius: 8px; 
                         border: 1px solid #f5c6cb; margin-bottom: 20px; }}
        
        /* Responsive design */
        @media (max-width: 768px) {{
            .header h1 {{ font-size: 2em; }}
            .nav-list {{ flex-direction: column; }}
            .nav-list li {{ margin-right: 0; }}
            .event-grid {{ grid-template-columns: 1fr; }}
            .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
        }}
        
        @media (max-width: 480px) {{
            .container {{ padding: 20px 15px; }}
            .header-content {{ padding: 15px; }}
            .stats-grid {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <header class="main-header">
        <div class="header-content">
            <h1>🎭 Moss Kulturkalender</h1>
            <p>Din komplette oversikt over kulturarrangementer i Moss</p>
            <!-- Search Section -->
            <div class="search-section">
                <div class="search-container">
                    <input type="text" id="searchInput" class="search-input" placeholder="Søk etter arrangementer, artister eller venues...">
                    <button type="button" class="search-button" onclick="performSearch()">🔍</button>
                </div>
                <div class="search-stats" id="searchStats"></div>
            </div>
            
            <nav class="nav-bar">
                <ul class="nav-list">
                    <li><a href="#kommende" class="active">Kommende arrangementer</a></li>
                    <li><a href="#venues">Venues</a></li>
                    <li><a href="#kategorier">Kategorier</a></li>
                    <li><a href="#om">Om kalenderen</a></li>
                    <li><a href="#" onclick="openTipForm()" class="tip-button">💡 Tips oss</a></li>
                </ul>
            </nav>
        </div>
    </header>
    
    <main class="container">
        <!-- Statistics Section -->
        <div class="stats-grid">
            <div class="stat-card total">
                <div class="stat-number">{len(upcoming_events)}</div>
                <div class="stat-label">Kommende arrangementer</div>
            </div>
            <div class="stat-card ticketmaster">
                <div class="stat-number">{len([e for e in events if e.source == 'Ticketmaster'])}</div>
                <div class="stat-label">Ticketmaster</div>
            </div>
            <div class="stat-card kulturhus">
                <div class="stat-number">{len([e for e in events if 'kulturhus' in e.source.lower()])}</div>
                <div class="stat-label">Moss Kulturhus</div>
            </div>
            <div class="stat-card bibliotek">
                <div class="stat-number">{len([e for e in events if 'bibliotek' in e.source.lower()])}</div>
                <div class="stat-label">Moss Bibliotek</div>
            </div>
            <div class="stat-card visitostfold">
                <div class="stat-number">{len([e for e in events if 'visit' in e.source.lower() and 'østfold' in e.source.lower()])}</div>
                <div class="stat-label">Visit Østfold</div>
            </div>
            <div class="stat-card mossavis">
                <div class="stat-number">{len([e for e in events if 'moss avis' in e.source.lower()])}</div>
                <div class="stat-label">Moss Avis</div>
            </div>
            <div class="stat-card gallerif15">
                <div class="stat-number">{len([e for e in events if 'galleri' in e.source.lower() and 'f15' in e.source.lower()])}</div>
                <div class="stat-label">Galleri F15</div>
            </div>
            <div class="stat-card odeokino">
                <div class="stat-number">{len([e for e in events if 'odeon' in e.source.lower() and 'kino' in e.source.lower()])}</div>
                <div class="stat-label">Odeon Kino</div>
            </div>
        </div>
        
        <!-- Siste nytt seksjonen -->
        <section id="siste-nytt">
            <h2 class="section-title">⚡ Siste nytt</h2>
            <p style="color: #666; margin-bottom: 20px;">De 3 nyeste arrangementene lagt til</p>
            <div class="latest-events-grid">
"""
        
        # Get the 3 most recently added events (based on first_seen)
        latest_events = sorted(upcoming_events, key=lambda e: e.first_seen, reverse=True)[:3]
        
        for event in latest_events:
            is_ticketmaster = event.source == "Ticketmaster"
            tm_data = getattr(event, '_ticketmaster_data', {}) if is_ticketmaster else {}
            
            # Format date and time
            event_date = event.start.strftime('%d.%m.%Y')
            event_time = event.start.strftime('%H:%M') if event.start.hour != 0 or event.start.minute != 0 else ''
            
            # Determine source class and badge
            if event.source == "Ticketmaster":
                source_class = "ticketmaster"
                source_badge = f'<span class="source-badge tm-badge">{event.source}</span>'
            elif "kulturhus" in event.source.lower():
                source_class = "kulturhus"
                source_badge = f'<span class="source-badge kulturhus-badge">{event.source}</span>'
            elif "bibliotek" in event.source.lower():
                source_class = "bibliotek"
                source_badge = f'<span class="source-badge bibliotek-badge">{event.source}</span>'
            elif "visit" in event.source.lower() and "østfold" in event.source.lower():
                source_class = "visitostfold"
                source_badge = f'<span class="source-badge visitostfold-badge">{event.source}</span>'
            elif "moss avis" in event.source.lower():
                source_class = "mossavis"
                source_badge = f'<span class="source-badge mossavis-badge">{event.source}</span>'
            elif "galleri" in event.source.lower() and "f15" in event.source.lower():
                source_class = "gallerif15"
                source_badge = f'<span class="source-badge gallerif15-badge">{event.source}</span>'
            elif "odeon" in event.source.lower() and "kino" in event.source.lower():
                source_class = "odeokino"
                source_badge = f'<span class="source-badge odeokino-badge">{event.source}</span>'
            else:
                source_class = "other"
                source_badge = f'<span class="source-badge other-badge">{event.source}</span>'
            
            # Price display
            price_display = event.price or "Pris ikke oppgitt"
            if is_ticketmaster and tm_data.get('priceRanges'):
                price_range = tm_data['priceRanges'][0]
                min_price = price_range.get('min', 0)
                max_price = price_range.get('max', 0)
                currency = price_range.get('currency', 'NOK')
                if min_price and max_price and min_price != max_price:
                    price_display = f"Fra {min_price} {currency}"
                elif min_price:
                    price_display = f"{min_price} {currency}"
            
            # Ticket URLs
            ticket_url = event.ticket_url
            info_url = event.url  # Use url instead of info_url
            if is_ticketmaster and tm_data.get('url'):
                ticket_url = tm_data['url']
                info_url = tm_data['url']
            
            html_content += f"""
                <div class="event-card latest-event {source_class}">
                    <div class="event-content">
                        <h3 class="event-title">
                            {event.title}
                            {source_badge}
                            <span class="new-badge">NY!</span>
                        </h3>
                        <div class="event-meta">
                            <i>📅</i> {event_date} {event_time}
                        </div>
                        <div class="event-meta">
                            <i>📍</i> <span class="event-venue">{event.venue}</span>
                        </div>
                        <div class="event-meta">
                            <i>💰</i> <span class="event-price">{price_display}</span>
                        </div>
            """
            
            if event.description and len(event.description.strip()) > 10:
                description = event.description[:150] + "..." if len(event.description) > 150 else event.description
                html_content += f'<p class="event-description">{description}</p>'
            
            # Ticket button
            if ticket_url and ticket_url != "None":
                button_class = "ticket-button"
                button_text = "Kjøp billett" if is_ticketmaster else "Mer info"
                html_content += f'<a href="{ticket_url}" target="_blank" rel="noopener" class="{button_class}">{button_text}</a>'
            
            html_content += """
                    </div>
                </div>
            """
        
        html_content += """
            </div>
        </section>
        
        <section id="kommende">
            <h2 class="section-title">🎪 Kommende arrangementer</h2>
            <p style="color: #666; margin-bottom: 30px;">Automatisk oppdatert {datetime.now().strftime('%d.%m.%Y kl. %H:%M')}</p>
            
            <!-- Pagination Controls -->
            <div class="pagination-container">
                <div class="pagination-info">
                    <span id="paginationInfo">Viser 1-10 av {len(upcoming_events)} arrangementer</span>
                </div>
                <div class="pagination">
                    <button id="prevPage" onclick="changePage(-1)">‹ Forrige</button>
                    <span id="pageNumbers"></span>
                    <button id="nextPage" onclick="changePage(1)">Neste ›</button>
                </div>
                <button class="show-all-btn" id="showAllBtn" onclick="showAll()">Vis alle</button>
            </div>
            
            <div class="event-grid" id="eventGrid">
"""
        
        for event in upcoming_events:
            is_ticketmaster = event.source == "Ticketmaster"
            tm_data = getattr(event, '_ticketmaster_data', {}) if is_ticketmaster else {}
            
            # Format date and time
            event_date = event.start.strftime('%d.%m.%Y')
            event_time = event.start.strftime('%H:%M') if event.start.hour != 0 or event.start.minute != 0 else ''
            
            # Enhanced price display with min/max prices
            price_display = "Pris ikke oppgitt"
            if tm_data.get('sold_out'):
                price_display = "UTSOLGT"
            elif tm_data.get('min_price') and tm_data.get('max_price'):
                min_p = tm_data.get('min_price')
                max_p = tm_data.get('max_price')
                if min_p == max_p:
                    price_display = f"kr {min_p:.0f}"
                else:
                    price_display = f"kr {min_p:.0f}-{max_p:.0f}"
            elif tm_data.get('min_price'):
                price_display = f"fra kr {tm_data.get('min_price'):.0f}"
            elif event.price and event.price.strip():
                price_display = event.price
            elif is_ticketmaster:
                # For Ticketmaster events without price data, show availability instead
                price_display = "Se Ticketmaster for pris"
            
            # Ticket availability status
            availability_status = ""
            if tm_data.get('sold_out'):
                availability_status = '<div class="availability sold-out">❌ Utsolgt</div>'
            elif tm_data.get('tickets_available'):
                availability_status = '<div class="availability available">✅ Billetter tilgjengelig</div>'
            elif tm_data.get('tickets_available') == False:
                availability_status = '<div class="availability unavailable">⏳ Ikke på salg ennå</div>'
            
            # Ticket button
            ticket_button = ""
            if event.ticket_url:
                button_class = "sold-out" if tm_data.get('sold_out') else ""
                ticket_text = "Utsolgt" if tm_data.get('sold_out') else "Kjøp billetter"
                ticket_button = f'<a href="{event.ticket_url}" class="ticket-button {button_class}" target="_blank">{ticket_text}</a>'
            
            # Determine source styling
            if is_ticketmaster:
                source_class = "ticketmaster"
                source_badge = '<span class="source-badge tm-badge">Ticketmaster</span>'
            elif "kulturhus" in event.source.lower():
                source_class = "kulturhus" 
                source_badge = f'<span class="source-badge kulturhus-badge">{event.source}</span>'
            elif "bibliotek" in event.source.lower():
                source_class = "bibliotek"
                source_badge = f'<span class="source-badge bibliotek-badge">{event.source}</span>'
            elif "visit" in event.source.lower() and "østfold" in event.source.lower():
                source_class = "visitostfold"
                source_badge = f'<span class="source-badge visitostfold-badge">{event.source}</span>'
            elif "moss avis" in event.source.lower():
                source_class = "mossavis"
                source_badge = f'<span class="source-badge mossavis-badge">{event.source}</span>'
            elif "galleri" in event.source.lower() and "f15" in event.source.lower():
                source_class = "gallerif15"
                source_badge = f'<span class="source-badge gallerif15-badge">{event.source}</span>'
            elif "odeon" in event.source.lower() and "kino" in event.source.lower():
                source_class = "odeokino"
                source_badge = f'<span class="source-badge odeokino-badge">{event.source}</span>'
            else:
                source_class = "other"
                source_badge = f'<span class="source-badge other-badge">{event.source}</span>'
            
            html_content += f"""
            <div class="event-card {source_class}">
                <div class="event-content">
                    <div class="event-title">
                        {event.title}
                        {source_badge}
                    </div>
                    <div class="event-meta">📅 {event_date} {event_time}</div>
                    <div class="event-meta event-venue">📍 {event.venue or 'Sted ikke oppgitt'}</div>
                    <div class="event-meta event-price">💰 {price_display}</div>
                    {f'<div class="event-meta event-category">🎭 {event.category}</div>' if event.category else ''}
                    {availability_status}
                    {f'<div class="event-description">{event.description[:200]}...</div>' if event.description else ''}
                    {ticket_button}
                </div>
            </div>
"""
        
        html_content += f"""
            </div>
        </section>
        
        <section id="venues" style="margin-top: 50px;">
            <h2 class="section-title">📍 Venues i Moss</h2>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px;">
                <div style="background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.07);">
                    <h3 style="color: #0066cc; margin-bottom: 10px;">🎭 Verket Scene</h3>
                    <p style="color: #666;">Bernt Ankers gate 19, Moss<br>Hovedscene for konserter og kulturarrangementer</p>
                </div>
                <div style="background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.07);">
                    <h3 style="color: #e74c3c; margin-bottom: 10px;">🏛️ Moss Kulturhus</h3>
                    <p style="color: #666;">Moss sentrum<br>Kulturhus med teater, konserter og utstillinger</p>
                </div>
                <div style="background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.07);">
                    <h3 style="color: #f39c12; margin-bottom: 10px;">🍺 Heilmannparken/Moss Bryggeri</h3>
                    <p style="color: #666;">Henrich Gernersgate 7, Moss<br>Utendørs konserter og festivaler</p>
                </div>
            </div>
        </section>
        
    </main>
    
    <footer class="main-footer">
        <div class="footer-content">
            <div class="footer-grid">
                <div class="footer-section">
                    <h3>Om Moss Kulturkalender</h3>
                    <p style="color: #bdc3c7; line-height: 1.6;">
                        Din komplette oversikt over kulturarrangementer i Moss. 
                        Automatisk oppdatert med data fra Ticketmaster API, Moss Kulturhus og andre kilder.
                    </p>
                    <p style="color: #bdc3c7; margin-top: 15px;">
                        <strong>Sist oppdatert:</strong> {datetime.now().strftime('%d.%m.%Y kl. %H:%M')}
                    </p>
                </div>
                
                <div class="footer-section">
                    <h3>Viktige lenker</h3>
                    <ul>
                        <li><a href="https://www.verketscene.no">Verket Scene</a></li>
                        <li><a href="https://www.mosskulturhus.no">Moss Kulturhus</a></li>
                        <li><a href="https://www.ticketmaster.no">Ticketmaster Norge</a></li>
                        <li><a href="https://www.moss.kommune.no">Moss Kommune</a></li>
                    </ul>
                </div>
                
                <div class="footer-section">
                    <h3>Teknisk informasjon</h3>
                    <ul>
                        <li>📡 Ticketmaster Discovery API</li>
                        <li>🔄 Automatisk oppdatering hver time</li>
                        <li>📱 Mobiloptimalisert design</li>
                        <li>🎯 {len(events)} aktive arrangementer</li>
                    </ul>
                </div>
                
                <div class="footer-section">
                    <h3>Kontakt & Bidrag</h3>
                    <ul>
                        <li>🌐 <a href="mailto:post@herimoss.no">post@herimoss.no</a></li>
                        <li>💡 <a href="#" onclick="openTipForm()" style="color: #f39c12; font-weight: bold;">Tips oss om arrangementer!</a></li>
                        <li>📧 Forslag til forbedringer</li>
                        <li>🐛 Rapporter feil eller manglende info</li>
                    </ul>
                    <div style="margin-top: 20px; padding: 15px; background: rgba(243, 156, 18, 0.1); border-radius: 8px; border-left: 4px solid #f39c12;">
                        <strong style="color: #f39c12;">Kjenner du til et arrangement som mangler?</strong>
                        <p style="margin: 8px 0 0; font-size: 0.9em; color: #bdc3c7;">
                            <a href="#" onclick="openTipForm()" style="color: #f39c12; text-decoration: underline;">Klikk her for å gi oss beskjed!</a>
                        </p>
                    </div>
                </div>
            </div>
            
            <div class="footer-bottom">
                <p>&copy; {datetime.now().year} Moss Kulturkalender. Laget med ❤️ for Moss kulturscene.</p>
                <p style="margin-top: 10px; font-size: 0.9em;">
                    Data fra Ticketmaster API, Moss Kulturhus og andre offentlige kilder. 
                    Alle arrangementer er gjenstand for endringer.
                </p>
            </div>
        </div>
    </footer>
    
    <a href="#" class="back-to-top" id="backToTop">↑</a>
    
    <!-- Tip Form Modal -->
    <div id="tipModal" class="tip-modal">
        <div class="tip-form-container">
            <div class="tip-form-header">
                <button type="button" class="tip-form-close" onclick="closeTipForm()">&times;</button>
                <h2>💡 Tips oss om arrangementer</h2>
                <p>Kjenner du til et arrangement som ikke står i kalenderen? Vi setter stor pris på tips!</p>
            </div>
            <div class="tip-form-body">
                <div id="tip-message"></div>
                <form id="tipForm" action="/submit_tip.php" method="POST">
                    <!-- Spam protection honeypot -->
                    <input type="text" name="website" class="spam-protection" tabindex="-1" autocomplete="off">
                    <input type="hidden" name="timestamp" id="formTimestamp">
                    
                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label" for="tip_name">Ditt navn</label>
                            <input type="text" id="tip_name" name="tip_name" class="form-input" required>
                        </div>
                        <div class="form-group">
                            <label class="form-label" for="tip_email">Din e-post</label>
                            <input type="email" id="tip_email" name="tip_email" class="form-input" required>
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label" for="event_title">Arrangementstittel</label>
                        <input type="text" id="event_title" name="event_title" class="form-input" required 
                               placeholder="F.eks. 'Konsert med Foo Fighters'">
                    </div>
                    
                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label" for="event_date">Dato</label>
                            <input type="date" id="event_date" name="event_date" class="form-input" required>
                        </div>
                        <div class="form-group">
                            <label class="form-label" for="event_time">Tidspunkt</label>
                            <input type="time" id="event_time" name="event_time" class="form-input">
                        </div>
                    </div>
                    
                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label" for="event_venue">Sted/venue</label>
                            <input type="text" id="event_venue" name="event_venue" class="form-input" required 
                                   placeholder="F.eks. 'Verket Scene'">
                        </div>
                        <div class="form-group">
                            <label class="form-label" for="event_price">Billettpris</label>
                            <input type="text" id="event_price" name="event_price" class="form-input" 
                                   placeholder="F.eks. 'kr 350' eller 'Gratis'">
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label" for="event_url">Lenke til arrangement</label>
                        <input type="url" id="event_url" name="event_url" class="form-input" 
                               placeholder="https://...">
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label" for="event_description">Beskrivelse</label>
                        <textarea id="event_description" name="event_description" class="form-textarea" 
                                  placeholder="Fortell oss mer om arrangementet..."></textarea>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label" for="tip_message">Melding til oss</label>
                        <textarea id="tip_message" name="tip_message" class="form-textarea" 
                                  placeholder="Er det noe spesielt vi bør vite om dette arrangementet?"></textarea>
                    </div>
                    
                    <button type="submit" class="form-submit" id="submitTip">
                        🚀 Send inn tips
                    </button>
                </form>
            </div>
        </div>
    </div>
    
    <script>
        // Global variables
        let allEvents = [];
        let filteredEvents = [];
        let currentPage = 1;
        const eventsPerPage = 10;
        let showAllMode = false;
        
        // Initialize events array from DOM
        document.addEventListener('DOMContentLoaded', function() {{
            const eventCards = document.querySelectorAll('.event-card');
            eventCards.forEach((card, index) => {{
                const title = card.querySelector('.event-title').textContent.trim();
                const venue = card.querySelector('.event-venue').textContent.trim();
                const category = card.querySelector('.event-category')?.textContent.trim() || '';
                const description = card.querySelector('.event-description')?.textContent.trim() || '';
                
                allEvents.push({{
                    element: card,
                    title: title.toLowerCase(),
                    venue: venue.toLowerCase(), 
                    category: category.toLowerCase(),
                    description: description.toLowerCase(),
                    searchText: (title + ' ' + venue + ' ' + category + ' ' + description).toLowerCase()
                }});
            }});
            
            filteredEvents = [...allEvents];
            updatePagination();
            showCurrentPage();
        }});
        
        // Search functionality
        function performSearch() {{
            const searchTerm = document.getElementById('searchInput').value.toLowerCase().trim();
            
            if (searchTerm === '') {{
                filteredEvents = [...allEvents];
            }} else {{
                filteredEvents = allEvents.filter(event => 
                    event.searchText.includes(searchTerm)
                );
            }}
            
            currentPage = 1;
            showAllMode = false;
            updateSearchStats(searchTerm);
            updatePagination();
            showCurrentPage();
        }}
        
        // Real-time search
        document.getElementById('searchInput').addEventListener('input', function() {{
            performSearch();
        }});
        
        // Enter key search
        document.getElementById('searchInput').addEventListener('keypress', function(e) {{
            if (e.key === 'Enter') {{
                performSearch();
            }}
        }});
        
        // Update search statistics
        function updateSearchStats(searchTerm) {{
            const statsElement = document.getElementById('searchStats');
            if (searchTerm) {{
                statsElement.textContent = `Viser ${{filteredEvents.length}} av ${{allEvents.length}} arrangementer for "${{searchTerm}}"`;
                statsElement.style.display = 'block';
            }} else {{
                statsElement.style.display = 'none';
            }}
        }}
        
        // Pagination functions
        function updatePagination() {{
            const totalPages = Math.ceil(filteredEvents.length / eventsPerPage);
            const prevBtn = document.getElementById('prevPage');
            const nextBtn = document.getElementById('nextPage');
            const pageNumbers = document.getElementById('pageNumbers');
            const paginationInfo = document.getElementById('paginationInfo');
            const showAllBtn = document.getElementById('showAllBtn');
            
            // Update pagination info
            const start = showAllMode ? 1 : ((currentPage - 1) * eventsPerPage) + 1;
            const end = showAllMode ? filteredEvents.length : Math.min(currentPage * eventsPerPage, filteredEvents.length);
            
            if (showAllMode) {{
                paginationInfo.textContent = `Viser alle ${{filteredEvents.length}} arrangementer`;
                showAllBtn.textContent = 'Vis sider';
            }} else {{
                paginationInfo.textContent = `Viser ${{start}}-${{end}} av ${{filteredEvents.length}} arrangementer`;
                showAllBtn.textContent = 'Vis alle';
            }}
            
            // Update buttons
            prevBtn.disabled = currentPage <= 1 || showAllMode;
            nextBtn.disabled = currentPage >= totalPages || showAllMode;
            
            // Generate page numbers
            pageNumbers.innerHTML = '';
            if (!showAllMode && totalPages > 1) {{
                for (let i = Math.max(1, currentPage - 2); i <= Math.min(totalPages, currentPage + 2); i++) {{
                    const btn = document.createElement('button');
                    btn.textContent = i;
                    btn.className = i === currentPage ? 'active' : '';
                    btn.onclick = () => goToPage(i);
                    pageNumbers.appendChild(btn);
                }}
            }}
        }}
        
        function changePage(direction) {{
            if (showAllMode) return;
            
            const totalPages = Math.ceil(filteredEvents.length / eventsPerPage);
            const newPage = currentPage + direction;
            
            if (newPage >= 1 && newPage <= totalPages) {{
                currentPage = newPage;
                updatePagination();
                showCurrentPage();
            }}
        }}
        
        function goToPage(page) {{
            if (showAllMode) return;
            currentPage = page;
            updatePagination();
            showCurrentPage();
        }}
        
        function showAll() {{
            showAllMode = !showAllMode;
            updatePagination();
            showCurrentPage();
        }}
        
        function showCurrentPage() {{
            // Hide all events first
            allEvents.forEach(event => {{
                event.element.style.display = 'none';
            }});
            
            // Show events based on current page and filter
            if (showAllMode) {{
                filteredEvents.forEach(event => {{
                    event.element.style.display = 'block';
                }});
            }} else {{
                const start = (currentPage - 1) * eventsPerPage;
                const end = start + eventsPerPage;
                
                filteredEvents.slice(start, end).forEach(event => {{
                    event.element.style.display = 'block';
                }});
            }}
            
            // Scroll to events section
            if (currentPage > 1 || showAllMode) {{
                document.getElementById('kommende').scrollIntoView({{ behavior: 'smooth' }});
            }}
        }}
        
        // Back to top functionality
        window.addEventListener('scroll', function() {{
            const backToTop = document.getElementById('backToTop');
            if (window.pageYOffset > 300) {{
                backToTop.classList.add('visible');
            }} else {{
                backToTop.classList.remove('visible');
            }}
        }});
        
        document.getElementById('backToTop').addEventListener('click', function(e) {{
            e.preventDefault();
            window.scrollTo({{ top: 0, behavior: 'smooth' }});
        }});
        
        // Smooth scrolling for navigation links
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {{
            anchor.addEventListener('click', function (e) {{
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {{
                    target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
                }}
            }});
        }});
        
        // Tip Form Functions
        function openTipForm() {{
            const modal = document.getElementById('tipModal');
            const form = document.getElementById('tipForm');
            const messageDiv = document.getElementById('tip-message');
            
            // Reset form and message
            form.reset();
            messageDiv.innerHTML = '';
            
            // Set timestamp for spam protection
            document.getElementById('formTimestamp').value = Date.now();
            
            // Show modal
            modal.classList.add('show');
            document.body.style.overflow = 'hidden';
            
            // Focus first input
            setTimeout(() => {{
                document.getElementById('tip_name').focus();
            }}, 300);
        }}
        
        function closeTipForm() {{
            const modal = document.getElementById('tipModal');
            modal.classList.remove('show');
            document.body.style.overflow = '';
        }}
        
        // Close modal when clicking outside
        document.getElementById('tipModal').addEventListener('click', function(e) {{
            if (e.target === this) {{
                closeTipForm();
            }}
        }});
        
        // Close modal with Escape key
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape' && document.getElementById('tipModal').classList.contains('show')) {{
                closeTipForm();
            }}
        }});
        
        // Form submission handler
        document.getElementById('tipForm').addEventListener('submit', async function(e) {{
            e.preventDefault();
            
            const submitBtn = document.getElementById('submitTip');
            const messageDiv = document.getElementById('tip-message');
            const originalBtnText = submitBtn.innerHTML;
            
            // Disable submit button and show loading
            submitBtn.disabled = true;
            submitBtn.innerHTML = '⏳ Sender...';
            
            try {{
                const formData = new FormData(this);
                
                const response = await fetch('/submit_tip.php', {{
                    method: 'POST',
                    body: formData
                }});
                
                const result = await response.json();
                
                if (result.success) {{
                    messageDiv.innerHTML = `
                        <div class="success-message">
                            ✅ <strong>Takk for tipset!</strong><br>
                            Vi har mottatt informasjonen og vil gjennomgå den så snart som mulig. 
                            Du får en bekreftelse på e-post.
                        </div>
                    `;
                    this.reset();
                    
                    // Auto-close after 3 seconds
                    setTimeout(() => {{
                        closeTipForm();
                    }}, 3000);
                }} else {{
                    messageDiv.innerHTML = `
                        <div class="error-message">
                            ❌ <strong>Oops!</strong><br>
                            ${{result.message || 'Det skjedde en feil ved innsending. Prøv igjen.'}}
                        </div>
                    `;
                }}
            }} catch (error) {{
                messageDiv.innerHTML = `
                    <div class="error-message">
                        ❌ <strong>Nettverksfeil</strong><br>
                        Kunne ikke sende tipset. Sjekk internetttilkoblingen din og prøv igjen.
                    </div>
                `;
                console.error('Tip submission error:', error);
            }} finally {{
                // Re-enable submit button
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalBtnText;
            }}
        }});
    </script>
</body>
</html>
"""
        
        # Write HTML file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(html_content, encoding='utf-8')
    
    async def run_full_pipeline(self) -> Dict[str, Any]:
        """Run the complete crawling and processing pipeline"""
        log_info("🚀 Starting Moss Event Crawler with Ticketmaster integration...")
        
        try:
            if self.dry_run:
                log_info("🔍 Running in dry-run mode - no data will be saved")
            
            # Initialize database
            db = await get_database()
            log_info("📊 Database initialized")
            
            all_events = []
            
            # 1. Crawl Ticketmaster events (primary source)
            tm_events = await self.crawl_ticketmaster_events()
            all_events.extend(tm_events)
            self.stats.sources_attempted += 1
            if tm_events:
                self.stats.sources_succeeded += 1
            
            # 2. Crawl legacy sources (if enabled)
            if self.include_legacy_scrapers:
                legacy_events = await self.crawl_legacy_sources()
                all_events.extend(legacy_events)
            
            log_info(f"📥 Total events collected: {len(all_events)}")
            
            # 3. Deduplicate events
            unique_events = await self.deduplicate_events(all_events)
            
            # 4. Save to database
            db_stats = {'new': 0, 'updated': 0, 'duplicates': 0}
            if not self.dry_run:
                db_stats = await self.save_events_to_database(unique_events)
            
            # 5. Generate HTML output
            html_path = None
            if unique_events:
                html_path = await self.generate_html_output(unique_events)
            
            # Update statistics
            self.stats.end_time = datetime.now()
            self.stats.events_fetched = len(all_events)
            self.stats.events_new = db_stats.get('new', 0)
            self.stats.events_updated = db_stats.get('updated', 0)
            self.stats.events_total = len(unique_events)
            
            # Calculate duration
            duration = (self.stats.end_time - self.stats.start_time).total_seconds()
            
            # Return results
            results = {
                "status": "success",
                "events_crawled": len(all_events),
                "events_unique": len(unique_events),
                "events_new": db_stats.get('new', 0),
                "events_updated": db_stats.get('updated', 0),
                "events_duplicates": db_stats.get('duplicates', 0),
                "ticketmaster_events": len(tm_events),
                "html_generated": html_path is not None,
                "html_path": html_path,
                "dry_run": self.dry_run,
                "duration_seconds": duration,
                "errors": db_stats.get('errors', 0)
            }
            
            log_info(f"✅ Crawler pipeline completed successfully in {duration:.1f}s")
            log_info(f"📊 Results: {results['events_unique']} unique events ({results['ticketmaster_events']} from Ticketmaster)")
            
            return results
            
        except Exception as e:
            log_error("crawler", f"Pipeline failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "events_crawled": 0,
                "events_unique": 0,
                "dry_run": self.dry_run,
                "errors": 1
            }


async def main():
    """Main entry point for the Moss Event Crawler"""
    parser = argparse.ArgumentParser(description="Moss Event Crawler with Ticketmaster Integration")
    parser.add_argument("--dry-run", action="store_true", help="Don't write files, just process")
    parser.add_argument("--max-events", type=int, help="Maximum events to process")
    parser.add_argument("--radius", type=int, default=20, help="Search radius in km around Moss (default: 20)")
    parser.add_argument("--no-legacy", action="store_true", help="Skip legacy scrapers")
    
    args = parser.parse_args()
    
    crawler = MossEventCrawler(
        max_events=args.max_events,
        dry_run=args.dry_run,
        radius_km=args.radius,
        include_legacy_scrapers=not args.no_legacy
    )
    
    results = await crawler.run_full_pipeline()
    
    # Print summary
    if results["status"] == "success":
        print(f"\n🎉 Crawling Complete!")
        print(f"📊 Events: {results['events_unique']} unique ({results['ticketmaster_events']} from Ticketmaster)")
        print(f"💾 Database: {results['events_new']} new, {results['events_updated']} updated")
        if results.get('html_path'):
            print(f"🌐 HTML: {results['html_path']}")
    else:
        print(f"\n❌ Crawling Failed: {results.get('error', 'Unknown error')}")
    
    return 0 if results["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))