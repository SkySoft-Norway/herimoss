#!/bin/bash

# Moss Event Crawler - Automatisk nattlig oppdatering
# Kjøres kl. 02:34 hver natt

# Sett working directory
cd /var/www/vhosts/herimoss.no/pythoncrawler

# Log start av oppdatering
echo "$(date): Starting automatic Moss event update..." >> /var/www/vhosts/herimoss.no/pythoncrawler/logs/auto_update.log

# Kjør event crawler
python3 moss_event_crawler.py >> /var/www/vhosts/herimoss.no/pythoncrawler/logs/auto_update.log 2>&1

# Log slutt av oppdatering
echo "$(date): Automatic update completed" >> /var/www/vhosts/herimoss.no/pythoncrawler/logs/auto_update.log
echo "----------------------------------------" >> /var/www/vhosts/herimoss.no/pythoncrawler/logs/auto_update.log