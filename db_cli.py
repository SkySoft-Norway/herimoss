#!/usr/bin/env python3
"""
Database CLI Tool for Moss Kulturkalender
Command-line interface for database operations, stats, and maintenance
"""

import asyncio
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from database import get_database, close_database
from logging_utils import init_logging, log_info, log_error


async def cmd_stats(args):
    """Show database statistics"""
    log_info("📊 Henter database statistikk...")
    
    db = await get_database()
    stats = await db.get_database_stats()
    
    print("\n" + "="*60)
    print("🗄️  MOSS KULTURKALENDER - DATABASE STATISTIKK")
    print("="*60)
    
    print(f"📍 Database sti: {stats['database_path']}")
    print(f"📋 Schema versjon: {stats['schema_version']}")
    print(f"📈 Totalt events: {stats['total_events']}")
    print(f"✅ Aktive events: {stats['active_events']}")
    
    print("\n📊 Event status:")
    for status, count in stats['event_counts'].items():
        print(f"   • {status}: {count}")
    
    print("\n🔄 Kilder:")
    for source in stats['sources'][:10]:  # Top 10 sources
        print(f"   • {source['name']}: {source['total_events']} events ({source['success_rate']:.1%} success, {source['status']})")
    
    if len(stats['sources']) > 10:
        print(f"   ... og {len(stats['sources']) - 10} flere kilder")
    
    print("\n📅 Siste 7 dager aktivitet:")
    for activity in stats['daily_activity'][:7]:
        print(f"   • {activity['date']}: {activity['count']} nye events")
    
    print("\n" + "="*60)


async def cmd_cleanup(args):
    """Clean up old events"""
    days = args.days or 30
    log_info(f"🧹 Rydder opp events eldre enn {days} dager...")
    
    db = await get_database()
    deleted_count = await db.cleanup_old_events(days)
    
    log_info(f"✅ Ryddet opp {deleted_count} gamle events")


async def cmd_search(args):
    """Search for events"""
    log_info(f"🔍 Søker etter events...")
    
    db = await get_database()
    
    # Build search parameters
    search_params = {
        'limit': args.limit or 50,
        'offset': args.offset or 0
    }
    
    if args.source:
        search_params['source'] = args.source
    
    if args.since:
        search_params['start_date'] = datetime.now() - timedelta(days=args.since)
    
    if args.until:
        search_params['end_date'] = datetime.now() + timedelta(days=args.until)
    
    events = await db.get_events(**search_params)
    
    print(f"\n🎯 Fant {len(events)} events:")
    print("-" * 80)
    
    for event in events:
        start_time = event['start_time'][:16] if event['start_time'] else 'N/A'
        print(f"📅 {start_time} | {event['title'][:50]}")
        if event['venue']:
            print(f"   📍 {event['venue']}")
        if event['source']:
            print(f"   🔗 {event['source']}")
        print()


async def cmd_export(args):
    """Export events to JSON"""
    log_info(f"📤 Eksporterer events til {args.output}...")
    
    db = await get_database()
    events = await db.get_events(limit=args.limit or 1000)
    
    import json
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(events, f, ensure_ascii=False, indent=2, default=str)
    
    log_info(f"✅ Eksporterte {len(events)} events til {args.output}")


async def cmd_sources(args):
    """Show source statistics"""
    log_info("📡 Henter kilde statistikk...")
    
    db = await get_database()
    stats = await db.get_database_stats()
    
    print("\n" + "="*80)
    print("📡 KILDE STATISTIKK")
    print("="*80)
    
    for source in stats['sources']:
        status_emoji = {"active": "✅", "error": "❌", "disabled": "⏸️"}.get(source['status'], "❓")
        print(f"{status_emoji} {source['name']}")
        print(f"   📊 Events: {source['total_events']}")
        print(f"   📈 Success rate: {source['success_rate']:.1%}")
        print(f"   🔄 Status: {source['status']}")
        print()


async def cmd_metrics(args):
    """Show scraping metrics"""
    log_info("📈 Henter scraping metrics...")
    
    # This would require implementing metrics querying in database.py
    print("📈 Metrics funksjonen er ikke implementert ennå")


def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(description="Moss Kulturkalender Database CLI")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show database statistics')
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up old events')
    cleanup_parser.add_argument('--days', type=int, default=30, 
                               help='Delete events older than N days (default: 30)')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search for events')
    search_parser.add_argument('--source', help='Filter by source')
    search_parser.add_argument('--since', type=int, help='Events since N days ago')
    search_parser.add_argument('--until', type=int, help='Events until N days from now')
    search_parser.add_argument('--limit', type=int, default=50, help='Maximum results')
    search_parser.add_argument('--offset', type=int, default=0, help='Results offset')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export events to JSON')
    export_parser.add_argument('output', help='Output file path')
    export_parser.add_argument('--limit', type=int, help='Maximum events to export')
    
    # Sources command
    sources_parser = subparsers.add_parser('sources', help='Show source statistics')
    
    # Metrics command
    metrics_parser = subparsers.add_parser('metrics', help='Show scraping metrics')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Initialize logging
    init_logging()
    
    # Command dispatch
    commands = {
        'stats': cmd_stats,
        'cleanup': cmd_cleanup,
        'search': cmd_search,
        'export': cmd_export,
        'sources': cmd_sources,
        'metrics': cmd_metrics
    }
    
    try:
        command_func = commands[args.command]
        result = asyncio.run(command_func(args))
        return result or 0
    except KeyboardInterrupt:
        log_info("Avbrutt av bruker")
        return 1
    except Exception as e:
        log_error(f"Kommando feilet: {e}")
        return 2
    finally:
        asyncio.run(close_database())


if __name__ == "__main__":
    sys.exit(main())
