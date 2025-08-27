#!/bin/bash
# Moss Kulturkalender Auto-Update Script
# Add to crontab with: 0 */4 * * * /var/www/vhosts/herimoss.no/pythoncrawler/auto_update.sh

cd /var/www/vhosts/herimoss.no/pythoncrawler

# Run full update
python3 full_update.py > /var/www/vhosts/herimoss.no/logs/calendar_update.log 2>&1

# Log timestamp
echo "$(date): Calendar update completed" >> /var/www/vhosts/herimoss.no/logs/calendar_cron.log
