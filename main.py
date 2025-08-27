#!/usr/bin/env python3
"""
Main crawler application
"""

import asyncio
import signal
import sys
from datetime import datetime
from logging_utils import log_info, log_error, log_warning
from crawlers.oslo_kommune import OsloKommuneCrawler
from crawlers.visitoslo import VisitOsloCrawler
from crawlers.oslo_kulturnatt import OsloKulturNattCrawler
from crawlers.ticketmaster import TicketmasterCrawler
from crawlers.eventbrite import EventbriteCrawler
from crawlers.facebook_events import FacebookEventsCrawler
from dedupe_advanced import get_deduplication_engine
from database import get_database
from config import CrawlerConfig
from ml_categorization import get_ml_categorizer
from performance import get_performance_monitor
from analytics import get_analytics


async def load_config(config_path: str) -> Config:
    """Load configuration from JSON file."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        # Convert source configs to proper format
        from models import SourceConfig
        sources = {}
        for name, source_data in config_data.get("sources", {}).items():
            sources[name] = SourceConfig(**source_data)
        config_data["sources"] = sources
        
        config = Config(**config_data)
        log_info(f"Loaded configuration from {config_path}")
        return config
        
    except Exception as e:
        log_error("config", f"Failed to load config: {e}", url=config_path)
        raise


async def scrape_all_sources(config: Config, only_sources: List[str] = None) -> List[Event]:
    """Scrape events from all enabled sources."""
    all_events = []
    stats = {
        "sources_attempted": 0,
        "sources_succeeded": 0,
        "sources_failed": 0
    }
    
    # Configure HTTP client
    http_config = config.http
    async with HttpClient(
        timeout=http_config.timeout_sec,
        max_concurrency=http_config.max_concurrency,
        rate_limit_per_sec=http_config.rate_limit_per_host_per_sec
    ) as client:
        
        # Process each source
        for source_name, source_config in config.sources.items():
            if not source_config.enabled:
                continue
            
            if only_sources and source_name not in only_sources:
                continue
            
            stats["sources_attempted"] += 1
            
            try:
                log_info(f"Starting scrape of {source_name}")
                
                events = []
                if source_name == "moss_kommune":
                    events = await scrape_moss_kommune(source_config.model_dump(), client)
                elif source_name == "moss_kulturhus":
                    events = await scrape_moss_kulturhus(source_config.model_dump(), client)
                elif source_name == "verket_scene":
                    events = await scrape_verket_scene(source_config.model_dump(), client)
                elif source_name == "google_calendar":
                    events = await scrape_google_calendar(source_config.model_dump(), client)
                elif source_name == "meetup_api":
                    events = await call_api_with_fallback(
                        "meetup", scrape_meetup_events, source_config.model_dump(), client
                    )
                elif source_name == "bandsintown_api":
                    events = await call_api_with_fallback(
                        "bandsintown", scrape_bandsintown_events, source_config.model_dump(), client
                    )
                elif source_name == "songkick_api":
                    events = await call_api_with_fallback(
                        "songkick", scrape_songkick_events, source_config.model_dump(), client
                    )
                elif source_name == "ticketco_events":
                    events = await scrape_ticketco_events(source_config.model_dump(), client)
                elif source_name == "eventim_oslo":
                    events = await scrape_eventim_events(source_config.model_dump(), client)
                elif source_name in ["moss_avis_kultur", "ostlendingen_kultur"]:
                    events = await scrape_local_news_events(source_config.model_dump(), client)
                elif source_name in ["verket_booking_widget", "moss_kulturhus_api"]:
                    events = await scrape_booking_widget_events(source_config.model_dump(), client)
                else:
                    log_info(f"Scraper for {source_name} not implemented yet")
                
                all_events.extend(events)
                stats["sources_succeeded"] += 1
                
                log_info(f"Completed {source_name}: {len(events)} events")
                
            except Exception as e:
                log_error(source_name, f"Scrape failed: {e}")
                stats["sources_failed"] += 1
    
    log_info(f"Scraping completed: {stats['sources_succeeded']}/{stats['sources_attempted']} sources successful, {len(all_events)} total events")
    return all_events


async def process_events(events: List[Event], config: Config, state_manager, dry_run: bool = False) -> Dict[str, int]:
    """Process events through the complete pipeline with ML categorization and performance monitoring."""
    log_info("🔄 Starting advanced event processing pipeline...")
    
    # Initialize advanced components
    ml_categorizer = get_ml_categorizer()
    performance_monitor = get_performance_monitor()
    analytics = get_analytics()
    
    # Start performance monitoring
    await performance_monitor.start_monitoring()
    processing_session = await performance_monitor.start_processing_session(len(events))
    
    try:
        stats = {
            "events_fetched": len(events),
            "events_new": 0,
            "events_updated": 0,
            "events_archived": 0,
            "duplicates_found": 0
        }
        
        # Step 1: ML categorization and enhancement
        log_info(f"🧠 Applying ML categorization to {len(events)} events...")
        
        categorized_events = []
        for event in events:
            try:
                # Apply ML categorization
                enhanced_event = await ml_categorizer.categorize_event(event)
                categorized_events.append(enhanced_event)
            except Exception as e:
                log_error("ml_categorization", f"Failed to categorize event {event.title}: {e}")
                categorized_events.append(event)  # Use original event
        
        log_info(f"✅ ML categorization completed for {len(categorized_events)} events")
        
        # Step 2: Advanced deduplication
        log_info("🔍 Running advanced deduplication...")
        
        # Initialize deduplication engine
        dedupe_engine = get_deduplication_engine()
        
        # Find duplicates
        unique_events, duplicates_found = await dedupe_engine.deduplicate_events(categorized_events)
        stats["duplicates_found"] = duplicates_found
        
        log_info(f"🎯 Deduplication completed: {len(unique_events)} unique events, {duplicates_found} duplicates removed")
        
        # Step 3: Database operations with improved performance
        log_info("💾 Saving events to database...")
        
        db = await get_database()
        
        # Use smart caching for database operations
        total_db_stats = {"new": 0, "updated": 0, "duplicates": 0}
        batch_size = 50  # Process in batches for better performance
        
        for i in range(0, len(unique_events), batch_size):
            batch = unique_events[i:i + batch_size]
            
            # Save batch with performance monitoring
            batch_start = datetime.now()
            
            for event in batch:
                db_stats = await db.save_event(event)
                total_db_stats["new"] += db_stats["new"]
                total_db_stats["updated"] += db_stats["updated"]
                total_db_stats["duplicates"] += db_stats["duplicates"]
            
            batch_duration = (datetime.now() - batch_start).total_seconds()
            log_info(f"📊 Processed batch {i//batch_size + 1}: {len(batch)} events in {batch_duration:.2f}s")
        
        stats["events_new"] = total_db_stats["new"]
        stats["events_updated"] = total_db_stats["updated"]
        log_info(f"Database stats: {total_db_stats['new']} new, {total_db_stats['updated']} updated, {total_db_stats['duplicates']} database duplicates")
        
        # Step 4: Generate analytics insights
        log_info("📈 Generating analytics insights...")
        
        try:
            # Generate trends and insights
            trends = await analytics.analyze_trends(days=30)
            insights = await analytics.generate_insights(unique_events)
            
            log_info(f"✅ Generated {len(trends)} trends and {len(insights)} insights")
            
            # Export analytics report if we have significant data
            if len(unique_events) > 10:
                report_path = f"analytics_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                await analytics.export_analytics_report(report_path, days=30)
        
        except Exception as e:
            log_error("analytics", f"Analytics generation failed: {e}")
        
        # Step 5: Legacy deduplication and state management for backwards compatibility
        log_info("Running legacy deduplication for state management...")
        existing_hashes = state_manager.load_seen_hashes()
        legacy_unique_events, updated_hashes, duplicate_mappings = deduplicate_event_list(
            unique_events, 
            existing_hashes,
            fuzzy_threshold=90
        )
        
        if dry_run:
            log_info("Dry run mode - not updating state")
            return stats
        
        # Step 6: Update legacy state
        log_info("Updating legacy state...")
        state_stats = state_manager.full_state_update(
            legacy_unique_events, 
            config.rules.archive_if_ended_before_hours
        )
        
        # Save updated hashes
        state_manager.save_seen_hashes(updated_hashes)
        
        # Update archive stats
        stats["events_archived"] = state_stats["archived_events"]
        
        # Complete performance monitoring
        await performance_monitor.complete_processing_session(processing_session)
        
        log_info(f"🎉 Processing complete: {stats['events_new']} new, {stats['events_updated']} updated, {stats['events_archived']} archived, {stats['duplicates_found']} duplicates removed")
        
        return stats
    
    except Exception as e:
        log_error("processing", f"Event processing failed: {e}")
        await performance_monitor.complete_processing_session(processing_session, error=str(e))
        raise
    
    finally:
        # Clean up
        await performance_monitor.stop_monitoring()


async def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Moss Kulturkalender Event Crawler")
    parser.add_argument("--config", default="options.json", help="Configuration file")
    parser.add_argument("--dry-run", action="store_true", help="Don't write files, just process")
    parser.add_argument("--rebuild-html-only", action="store_true", help="Only rebuild HTML from existing state")
    parser.add_argument("--only", help="Comma-separated list of sources to process")
    parser.add_argument("--since-days", type=int, help="Limit to events since N days ago")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARN", "ERROR"], default="INFO")
    
    args = parser.parse_args()
    
    # Initialize logging
    log_file = Path("log.json")
    error_file = Path("feil.json")
    init_logging(str(log_file), str(error_file))
    
    try:
        # Load configuration
        config = await load_config(args.config)
        
        # Validate API keys and connectivity for Phase 4
        log_info("Validating API configuration...")
        api_keys = await validate_api_keys()
        
        # Initialize state manager
        state_manager = StateManager("state")
        
        # Initialize database
        log_info("Initializing database...")
        db = await get_database()
        log_info("Database ready")
        
        # Parse only sources
        only_sources = None
        if args.only:
            only_sources = [s.strip() for s in args.only.split(",")]
            log_info(f"Processing only sources: {only_sources}")
        
        # Start processing
        log_info("Starting event crawling")
        start_time = datetime.now(timezone.utc)
        
        if args.rebuild_html_only:
            log_info("Rebuild HTML only mode - not implemented yet")
            return 0
        
        # Create statistics
        stats = Statistics(
            start_time=start_time,
            sources_attempted=0,
            sources_succeeded=0,
            sources_failed=0
        )
        
        # Scrape events
        events = await scrape_all_sources(config, only_sources)
        
        # Process events
        process_stats = await process_events(events, config, state_manager, args.dry_run)
        
        # Update statistics
        stats.events_fetched = process_stats["events_fetched"]
        stats.events_new = process_stats["events_new"]
        stats.events_updated = process_stats["events_updated"]
        stats.events_archived = process_stats["events_archived"]
        stats.events_total = process_stats.get("total_events", 0)
        stats.end_time = datetime.now(timezone.utc)
        
        # Save run statistics
        if not args.dry_run:
            state_manager.save_last_run(stats)
        
        # Calculate duration
        duration = (stats.end_time - stats.start_time).total_seconds()
        
        # Determine exit code
        exit_code = 0
        if stats.sources_failed > 0 and stats.sources_succeeded == 0:
            exit_code = 2  # Full failure
        elif stats.sources_failed > 0:
            exit_code = 1  # Partial failure
        
        log_info(f"Crawling completed in {duration:.1f} seconds")
        log_info(f"Summary: {stats.events_fetched} fetched, {stats.events_new} new, {stats.events_updated} updated, {stats.events_archived} archived")
        
        return exit_code
        
    except Exception as e:
        log_error("main", f"Fatal error: {e}")
        return 2
    finally:
        # Clean up database connections
        await close_database()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
