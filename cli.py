#!/usr/bin/env python3
"""
Production CLI for Moss Kulturkalender Event Crawler
Comprehensive command-line interface for production deployment
"""

import sys
import os
import argparse
import asyncio
import json
import signal
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simple_crawler import EventCrawler
from logging_utils import init_logging, log_info, log_error
from database import get_database
from performance import get_performance_monitor
from analytics import get_analytics
from models import Statistics


class ProductionCLI:
    """Production-ready CLI for the event crawler"""
    
    def __init__(self):
        self.crawler = None
        self.stats = Statistics(start_time=datetime.now())
        self.shutdown_requested = False
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print(f"\n🛑 Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True
        if self.crawler:
            self.crawler.shutdown_requested = True
    
    def create_parser(self) -> argparse.ArgumentParser:
        """Create comprehensive argument parser"""
        parser = argparse.ArgumentParser(
            description="Moss Kulturkalender - Production Event Crawler",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  %(prog)s run                    # Run full crawl with default config
  %(prog)s run --sources api,html # Run only specific source types
  %(prog)s run --max-events 100   # Limit number of events
  %(prog)s run --dry-run          # Test run without saving
  %(prog)s status                 # Show system status
  %(prog)s cleanup                # Clean old data
  %(prog)s analytics              # Generate analytics report
  %(prog)s validate               # Validate system configuration
  %(prog)s cron                   # Run in cron mode (silent unless errors)
            """
        )
        
        # Global options
        parser.add_argument(
            "--config", "-c", 
            default="options.json",
            help="Configuration file path (default: options.json)"
        )
        parser.add_argument(
            "--log-level", 
            choices=["DEBUG", "INFO", "WARN", "ERROR"],
            default="INFO",
            help="Logging level (default: INFO)"
        )
        parser.add_argument(
            "--quiet", "-q", 
            action="store_true",
            help="Suppress non-error output"
        )
        parser.add_argument(
            "--verbose", "-v", 
            action="count", 
            default=0,
            help="Increase verbosity (-v, -vv, -vvv)"
        )
        
        # Subcommands
        subparsers = parser.add_subparsers(dest="command", help="Available commands")
        
        # Run command
        run_parser = subparsers.add_parser("run", help="Run the event crawler")
        run_parser.add_argument(
            "--sources", 
            help="Comma-separated list of source types (ical,rss,html,api,email)"
        )
        run_parser.add_argument(
            "--max-events", 
            type=int,
            help="Maximum number of events to process"
        )
        run_parser.add_argument(
            "--dry-run", 
            action="store_true",
            help="Run without saving data (test mode)"
        )
        run_parser.add_argument(
            "--force", 
            action="store_true",
            help="Ignore rate limits and recent run checks"
        )
        run_parser.add_argument(
            "--output", 
            choices=["json", "text", "html"],
            default="text",
            help="Output format for results"
        )
        
        # Status command
        status_parser = subparsers.add_parser("status", help="Show system status")
        status_parser.add_argument(
            "--detailed", 
            action="store_true",
            help="Show detailed status information"
        )
        
        # Cleanup command
        cleanup_parser = subparsers.add_parser("cleanup", help="Clean old data")
        cleanup_parser.add_argument(
            "--days", 
            type=int, 
            default=30,
            help="Remove events older than N days (default: 30)"
        )
        cleanup_parser.add_argument(
            "--logs", 
            action="store_true",
            help="Also clean old log files"
        )
        cleanup_parser.add_argument(
            "--confirm", 
            action="store_true",
            help="Skip confirmation prompt"
        )
        
        # Analytics command
        analytics_parser = subparsers.add_parser("analytics", help="Generate analytics report")
        analytics_parser.add_argument(
            "--days", 
            type=int, 
            default=30,
            help="Analysis period in days (default: 30)"
        )
        analytics_parser.add_argument(
            "--output-file", 
            help="Save report to file instead of stdout"
        )
        analytics_parser.add_argument(
            "--format", 
            choices=["json", "text", "html"],
            default="text",
            help="Output format (default: text)"
        )
        
        # Validate command
        subparsers.add_parser("validate", help="Validate system configuration")
        
        # Cron command (silent mode)
        cron_parser = subparsers.add_parser("cron", help="Run in cron mode")
        cron_parser.add_argument(
            "--max-runtime", 
            type=int, 
            default=1800,  # 30 minutes
            help="Maximum runtime in seconds (default: 1800)"
        )
        
        # Database commands
        db_parser = subparsers.add_parser("db", help="Database operations")
        db_subparsers = db_parser.add_subparsers(dest="db_command")
        
        db_subparsers.add_parser("init", help="Initialize database")
        db_subparsers.add_parser("backup", help="Backup database")
        db_subparsers.add_parser("restore", help="Restore database")
        db_subparsers.add_parser("stats", help="Show database statistics")
        
        return parser
    
    async def run_crawler(self, args) -> int:
        """Run the main crawler"""
        try:
            log_info("🚀 Starting Moss Kulturkalender crawler...")
            
            # Initialize crawler
            self.crawler = EventCrawler(
                config_path=args.config,
                max_events=args.max_events,
                dry_run=args.dry_run,
                force=args.force
            )
            
            # Filter sources if specified
            if args.sources:
                source_types = [s.strip() for s in args.sources.split(',')]
                self.crawler.filter_sources(source_types)
            
            # Run crawler
            results = await self.crawler.run_full_pipeline()
            
            if not args.quiet:
                self._print_results(results, args.output)
            
            # Return appropriate exit code
            if results.get('errors', 0) > 0:
                return 2  # Partial success
            return 0  # Full success
            
        except Exception as e:
            log_error("cli", f"Crawler run failed: {e}")
            return 1  # Failure
    
    async def show_status(self, args) -> int:
        """Show system status"""
        try:
            db = await get_database()
            
            # Basic status
            status = {
                "timestamp": datetime.now().isoformat(),
                "database": {
                    "path": str(db.db_path),
                    "exists": db.db_path.exists(),
                    "size_mb": round(db.db_path.stat().st_size / 1024 / 1024, 2) if db.db_path.exists() else 0
                }
            }
            
            if db.db_path.exists():
                # Get event counts
                events = await db.get_events(limit=1)
                total_events = len(await db.get_events(limit=10000))
                upcoming_events = len(await db.get_events(
                    start_date=datetime.now(),
                    limit=10000
                ))
                
                status["events"] = {
                    "total": total_events,
                    "upcoming": upcoming_events,
                    "archived": total_events - upcoming_events
                }
                
                if args.detailed:
                    # Performance metrics
                    perf_monitor = get_performance_monitor()
                    await perf_monitor.start_monitoring()
                    
                    import psutil
                    status["system"] = {
                        "cpu_percent": psutil.cpu_percent(),
                        "memory_percent": psutil.virtual_memory().percent,
                        "disk_usage": psutil.disk_usage('/').percent
                    }
                    
                    await perf_monitor.stop_monitoring()
            
            # Print status
            if not args.quiet:
                self._print_status(status, detailed=args.detailed)
            
            return 0
            
        except Exception as e:
            log_error("cli", f"Status check failed: {e}")
            return 1
    
    async def cleanup_data(self, args) -> int:
        """Clean old data"""
        try:
            if not args.confirm and not args.quiet:
                response = input(f"This will remove events older than {args.days} days. Continue? [y/N]: ")
                if response.lower() not in ['y', 'yes']:
                    print("Cleanup cancelled.")
                    return 0
            
            db = await get_database()
            removed_count = await db.cleanup_old_events(args.days)
            
            if not args.quiet:
                print(f"✅ Removed {removed_count} old events")
            
            if args.logs:
                # Clean log files
                log_dir = Path(".")
                cleaned_logs = 0
                cutoff_date = datetime.now() - timedelta(days=args.days)
                
                for log_file in log_dir.glob("*.log*"):
                    if log_file.stat().st_mtime < cutoff_date.timestamp():
                        log_file.unlink()
                        cleaned_logs += 1
                
                if not args.quiet:
                    print(f"✅ Removed {cleaned_logs} old log files")
            
            return 0
            
        except Exception as e:
            log_error("cli", f"Cleanup failed: {e}")
            return 1
    
    async def generate_analytics(self, args) -> int:
        """Generate analytics report"""
        try:
            analytics = get_analytics()
            
            # Generate report
            if args.output_file:
                await analytics.export_analytics_report(args.output_file, days=args.days)
                if not args.quiet:
                    print(f"✅ Analytics report saved to {args.output_file}")
            else:
                # Generate and display
                trends = await analytics.analyze_trends(days=args.days)
                
                if args.format == "json":
                    import json
                    print(json.dumps([trend.__dict__ for trend in trends], indent=2, default=str))
                else:
                    self._print_analytics(trends)
            
            return 0
            
        except Exception as e:
            log_error("cli", f"Analytics generation failed: {e}")
            return 1
    
    async def validate_system(self, args) -> int:
        """Validate system configuration"""
        try:
            # Run validation script
            import subprocess
            result = subprocess.run([
                sys.executable, "validate_phase7.py"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                if not args.quiet:
                    print("✅ System validation passed")
                return 0
            else:
                if not args.quiet:
                    print("❌ System validation failed")
                    print(result.stdout)
                    print(result.stderr)
                return 1
                
        except Exception as e:
            log_error("cli", f"Validation failed: {e}")
            return 1
    
    async def run_cron_mode(self, args) -> int:
        """Run in cron mode (silent unless errors)"""
        try:
            # Set up timeout
            start_time = datetime.now()
            
            # Run with minimal output
            original_quiet = args.quiet
            args.quiet = True
            
            result = await self.run_crawler(args)
            
            # Check runtime
            runtime = (datetime.now() - start_time).total_seconds()
            if runtime > args.max_runtime:
                log_error("cli", f"Cron run exceeded max runtime: {runtime}s > {args.max_runtime}s")
                return 1
            
            return result
            
        except Exception as e:
            log_error("cli", f"Cron run failed: {e}")
            return 1
    
    def _print_results(self, results: Dict[str, Any], output_format: str):
        """Print crawler results"""
        if output_format == "json":
            print(json.dumps(results, indent=2, default=str))
        else:
            print("\n" + "="*50)
            print("CRAWLER RESULTS")
            print("="*50)
            
            for key, value in results.items():
                if isinstance(value, dict):
                    print(f"{key.title()}:")
                    for subkey, subvalue in value.items():
                        print(f"  {subkey}: {subvalue}")
                else:
                    print(f"{key}: {value}")
    
    def _print_status(self, status: Dict[str, Any], detailed: bool = False):
        """Print system status"""
        print("\n" + "="*50)
        print("SYSTEM STATUS")
        print("="*50)
        print(f"Timestamp: {status['timestamp']}")
        
        db_info = status['database']
        print(f"\nDatabase:")
        print(f"  Path: {db_info['path']}")
        print(f"  Exists: {'✅' if db_info['exists'] else '❌'}")
        print(f"  Size: {db_info['size_mb']} MB")
        
        if 'events' in status:
            events = status['events']
            print(f"\nEvents:")
            print(f"  Total: {events['total']}")
            print(f"  Upcoming: {events['upcoming']}")
            print(f"  Archived: {events['archived']}")
        
        if detailed and 'system' in status:
            sys_info = status['system']
            print(f"\nSystem:")
            print(f"  CPU: {sys_info['cpu_percent']}%")
            print(f"  Memory: {sys_info['memory_percent']}%")
            print(f"  Disk: {sys_info['disk_usage']}%")
    
    def _print_analytics(self, trends: List):
        """Print analytics in text format"""
        print("\n" + "="*50)
        print("ANALYTICS REPORT")
        print("="*50)
        
        if not trends:
            print("No trends found in the analysis period.")
            return
        
        for trend in trends:
            print(f"\n{trend.trend_type.title()} Trend:")
            print(f"  Period: {trend.period}")
            print(f"  Direction: {trend.trend_direction}")
            print(f"  Growth Rate: {trend.growth_rate:.1f}%")
            print(f"  Data Points: {len(trend.data_points)}")
            
            if trend.insights:
                print("  Insights:")
                for insight in trend.insights:
                    print(f"    • {insight}")
    
    async def run(self) -> int:
        """Main CLI entry point"""
        parser = self.create_parser()
        args = parser.parse_args()
        
        # Setup logging
        if args.verbose >= 2:
            log_level = "DEBUG"
        elif args.verbose == 1:
            log_level = "INFO"
        else:
            log_level = args.log_level
        
        init_logging()
        
        # Default to run command if no command specified
        if not args.command:
            args.command = "run"
        
        try:
            # Route to appropriate handler
            if args.command == "run":
                return await self.run_crawler(args)
            elif args.command == "status":
                return await self.show_status(args)
            elif args.command == "cleanup":
                return await self.cleanup_data(args)
            elif args.command == "analytics":
                return await self.generate_analytics(args)
            elif args.command == "validate":
                return await self.validate_system(args)
            elif args.command == "cron":
                return await self.run_cron_mode(args)
            else:
                parser.print_help()
                return 1
                
        except KeyboardInterrupt:
            if not args.quiet:
                print("\n🛑 Operation cancelled by user")
            return 130  # Standard exit code for SIGINT


def main():
    """CLI main function"""
    cli = ProductionCLI()
    return asyncio.run(cli.run())


if __name__ == "__main__":
    sys.exit(main())
