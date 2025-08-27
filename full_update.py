#!/usr/bin/env python3
"""
Complete workflow: Scrape events and update calendar webpage.
"""
import asyncio
import subprocess
import sys
from pathlib import Path

# Add the pythoncrawler directory to the path
sys.path.insert(0, '/var/www/vhosts/herimoss.no/pythoncrawler')

from logging_utils import init_logging, log_info

async def full_update():
    """Complete update: scrape events and regenerate calendar."""
    
    init_logging()
    log_info("🚀 Starting full Moss Kulturkalender update...")
    
    try:
        # Step 1: Scrape new events
        log_info("📥 Step 1: Scraping events from Moss Kulturhus...")
        result = subprocess.run([
            'python3', '/var/www/vhosts/herimoss.no/pythoncrawler/direct_moss_scraper.py'
        ], capture_output=True, text=True, cwd='/var/www/vhosts/herimoss.no/pythoncrawler')
        
        if result.returncode != 0:
            log_info(f"⚠️ Scraping had issues but continuing: {result.stderr}")
        else:
            log_info("✅ Events scraped successfully")
        
        # Step 2: Generate calendar HTML
        log_info("🎨 Step 2: Generating calendar webpage...")
        result = subprocess.run([
            'python3', '/var/www/vhosts/herimoss.no/pythoncrawler/generate_calendar.py'
        ], capture_output=True, text=True, cwd='/var/www/vhosts/herimoss.no/pythoncrawler')
        
        if result.returncode == 0:
            log_info("✅ Calendar webpage generated successfully")
            log_info("🌐 Moss Kulturkalender is now live at https://herimoss.no")
        else:
            log_info(f"❌ Calendar generation failed: {result.stderr}")
            return False
        
        # Step 3: Check database status
        log_info("📊 Step 3: Checking system status...")
        result = subprocess.run([
            'python3', '/var/www/vhosts/herimoss.no/pythoncrawler/cli.py', 'status'
        ], capture_output=True, text=True, cwd='/var/www/vhosts/herimoss.no/pythoncrawler')
        
        if result.returncode == 0:
            status_lines = result.stdout.split('\n')
            for line in status_lines:
                if 'Total:' in line or 'Upcoming:' in line:
                    log_info(f"📈 {line.strip()}")
        
        log_info("🎉 Full update completed successfully!")
        return True
        
    except Exception as e:
        log_info(f"❌ Error during full update: {e}")
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(full_update())
        if success:
            print("🎉 Full update completed! Check https://herimoss.no")
        else:
            print("❌ Update failed")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
