# Moss Kulturkalender - Event Aggregation System

A comprehensive cultural events aggregation system for Moss, Norway. This Python-based crawler automatically discovers, collects, and publishes cultural events from multiple sources across the region.

🌐 **Live Site**: [herimoss.no](https://herimoss.no)

## Overview

The Moss Kulturkalender is a sophisticated event aggregation platform that automatically crawls and consolidates cultural events from multiple sources in Moss, Norway and surrounding areas. It features advanced deduplication, ML-powered categorization, and generates a beautiful web calendar that serves as a central hub for the local cultural scene.

## Key Features

- **Multi-Source Data Collection**: Aggregates events from 20+ different sources including:
  - Municipal websites (Moss Kommune)
  - Cultural venues (Moss Kulturhus, Verket Scene)
  - Ticketing platforms (Ticketmaster, TicketCo, Eventim)
  - Social media (Facebook, Instagram)
  - News sources (Moss Avis, Østlendingen)
  - API integrations (Meetup, Bandsintown, Songkick)

- **Intelligent Processing**:
  - Advanced deduplication using ML and fuzzy matching
  - Automated event categorization with OpenAI integration
  - Geographic normalization and venue matching
  - Smart date/time parsing with timezone handling

- **Production-Ready Architecture**:
  - Async/await throughout for high performance
  - Comprehensive error handling and logging
  - Database abstraction (SQLite + MariaDB support)
  - Automated testing and validation
  - Performance monitoring and analytics

- **Web Output**:
  - Beautiful responsive HTML calendar
  - SEO-optimized event pages
  - Mobile-friendly design
  - Structured data markup for search engines

## System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Data Sources  │    │   Core System    │    │     Outputs     │
│                 │    │                  │    │                 │
│ • Municipal     │───▶│  Event Crawler   │───▶│  HTML Calendar  │
│ • Venues        │    │  (main.py)       │    │  (index.html)   │
│ • Ticketing     │    │                  │    │                 │
│ • Social Media  │    │ ┌──────────────┐ │    │ • Event Pages   │
│ • News Sources  │    │ │ Deduplication│ │    │ • RSS Feeds     │
│ • APIs          │    │ │   Engine     │ │    │ • JSON API      │
└─────────────────┘    │ └──────────────┘ │    │ • Analytics     │
                       │                  │    └─────────────────┘
                       │ ┌──────────────┐ │
                       │ │   Database   │ │
                       │ │(SQLite/Maria)│ │
                       │ └──────────────┘ │
                       └──────────────────┘
```

## Installation & Setup

### Prerequisites

- Python 3.10 or higher
- MySQL/MariaDB (optional, SQLite works for development)
- Web server with PHP support (for production deployment)

### Quick Start

1. **Clone the repository**:
   ```bash
   git clone https://github.com/SkySoft-Norway/herimoss.git
   cd herimoss
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

4. **Initialize the database**:
   ```bash
   python3 cli.py init-db
   ```

5. **Run your first crawl**:
   ```bash
   python3 cli.py run --dry-run
   ```

6. **Generate the calendar**:
   ```bash
   python3 generate_enhanced_calendar.py
   ```

## Configuration

The system is configured via `options.json`:

### Data Sources Configuration

```json
{
  "sources": {
    "moss_kommune": {
      "enabled": true,
      "ical_urls": ["https://moss.kommune.no/.../kalender.ics"],
      "rss_urls": ["https://moss.kommune.no/.../rss/"],
      "html_urls": ["https://moss.kommune.no/.../arrangementer/"]
    },
    "moss_kulturhus": {
      "enabled": true,
      "html_urls": ["https://www.mosskulturhus.no/program"]
    },
    "verket_scene": {
      "enabled": true,
      "html_urls": ["https://www.verketscene.no/program"]
    }
  }
}
```

### Processing Rules

```json
{
  "rules": {
    "archive_if_ended_before_hours": 1,
    "default_city": "Moss",
    "category_keywords": {
      "Musikk": ["konsert", "band", "dj", "live", "gig"],
      "Teater": ["teater", "standup", "improv", "forestilling"],
      "Familie": ["familie", "barn", "barne", "familiedag"],
      "Utstilling": ["utstilling", "vernissage", "galleri"]
    }
  }
}
```

## Usage

### Command Line Interface

The system includes a comprehensive CLI for all operations:

```bash
# Run full crawl and update
python3 cli.py run

# Dry run (no changes)
python3 cli.py run --dry-run

# Crawl specific sources only
python3 cli.py run --only moss_kommune,verket_scene

# Show system status
python3 cli.py status

# Clean up old data
python3 cli.py cleanup --days 90

# Generate analytics report
python3 cli.py analytics --days 30

# Validate system integrity
python3 cli.py validate
```

### Programmatic Usage

```python
import asyncio
from main import load_config, scrape_all_sources, process_events
from state_manager import StateManager

async def run_crawl():
    # Load configuration
    config = await load_config("options.json")
    
    # Initialize state manager
    state_manager = StateManager("state")
    
    # Scrape all sources
    events = await scrape_all_sources(config)
    
    # Process and deduplicate
    stats = await process_events(events, config, state_manager)
    
    print(f"Found {stats['events_new']} new events")

# Run the crawler
asyncio.run(run_crawl())
```

## Data Sources

### Currently Supported Sources

| Source Type | Examples | Method |
|-------------|----------|--------|
| **Municipal** | Moss Kommune | iCal, RSS, HTML |
| **Venues** | Moss Kulturhus, Verket Scene | HTML scraping, APIs |
| **Ticketing** | Ticketmaster, TicketCo, Eventim | API, HTML |
| **Social Media** | Facebook Pages, Instagram | Graph API, scraping |
| **News** | Moss Avis, Østlendingen | RSS, HTML |
| **Event Platforms** | Meetup, Bandsintown, Songkick | REST APIs |
| **Calendars** | Google Calendar | iCal feeds |

### Adding New Sources

1. **Create a scraper** in `scrapers/`:
   ```python
   async def scrape_new_source(config, client):
       events = []
       # Scraping logic here
       return events
   ```

2. **Update configuration** in `options.json`:
   ```json
   "new_source": {
     "enabled": true,
     "type": "html",
     "url": "https://example.com/events"
   }
   ```

3. **Add to main crawler** in `main.py`:
   ```python
   elif source_name == "new_source":
       events = await scrape_new_source(source_config.model_dump(), client)
   ```

## Database Schema

### Events Table

```sql
CREATE TABLE events (
    id VARCHAR(255) PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    url TEXT,
    ticket_url TEXT,
    image_url TEXT,
    venue VARCHAR(255),
    address VARCHAR(500),
    city VARCHAR(100) DEFAULT 'Moss',
    lat DECIMAL(10, 8),
    lon DECIMAL(11, 8),
    category VARCHAR(100),
    start_time DATETIME NOT NULL,
    end_time DATETIME,
    price VARCHAR(100),
    source VARCHAR(100) NOT NULL,
    source_type VARCHAR(20) NOT NULL,
    source_url TEXT,
    first_seen DATETIME NOT NULL,
    last_seen DATETIME NOT NULL,
    status VARCHAR(20) DEFAULT 'upcoming',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_start_time (start_time),
    INDEX idx_status (status),
    INDEX idx_source (source),
    INDEX idx_category (category),
    INDEX idx_city (city)
);
```

## Advanced Features

### Machine Learning Categorization

The system uses OpenAI's API for intelligent event categorization:

```python
from ml_categorization import get_ml_categorizer

categorizer = get_ml_categorizer()
enhanced_event = await categorizer.categorize_event(event)
```

### Advanced Deduplication

Multiple deduplication strategies work together:

1. **Hash-based**: Exact content matching
2. **Fuzzy matching**: Title/venue/date similarity
3. **ML-powered**: Semantic similarity detection
4. **Geographic**: Location-based duplicate detection

```python
from dedupe_advanced import get_deduplication_engine

dedupe_engine = get_deduplication_engine()
unique_events, duplicates = await dedupe_engine.deduplicate_events(events)
```

### Analytics & Insights

Built-in analytics provide insights into cultural trends:

```python
from analytics import get_analytics

analytics = get_analytics()
trends = await analytics.analyze_trends(days=30)
insights = await analytics.generate_insights(events)
```

### Performance Monitoring

Real-time performance monitoring tracks system health:

```python
from performance import get_performance_monitor

monitor = get_performance_monitor()
await monitor.start_monitoring()
session = await monitor.start_processing_session(event_count)
```

## Production Deployment

### Automated Deployment

Use the included deployment script:

```bash
chmod +x deploy.sh
sudo ./deploy.sh
```

This sets up:
- Directory structure
- File permissions
- Cron jobs
- Log rotation
- Health monitoring

### Cron Configuration

The system runs automatically via cron:

```bash
# Every 4 hours - full update
0 */4 * * * /var/www/vhosts/herimoss.no/pythoncrawler/auto_update.sh

# Daily at 2 AM - cleanup and analytics
0 2 * * * /var/www/vhosts/herimoss.no/pythoncrawler/cli.py cleanup

# Weekly on Sunday - validation
0 3 * * 0 /var/www/vhosts/herimoss.no/pythoncrawler/cli.py validate
```

### Web Server Configuration

For Apache, add to `.htaccess`:

```apache
RewriteEngine On
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule ^api/(.*)$ api.php?endpoint=$1 [L,QSA]
```

## Monitoring & Maintenance

### Log Files

- `logs/crawler_log.json` - Main application logs
- `logs/crawler_errors.json` - Error logs
- `logs/auto_update.log` - Cron job logs
- `logs/performance.json` - Performance metrics

### Health Checks

```bash
# System status
python3 cli.py status

# Validate data integrity  
python3 cli.py validate

# Performance report
python3 cli.py analytics --performance
```

### Common Maintenance Tasks

1. **Clean old data**:
   ```bash
   python3 cli.py cleanup --days 90
   ```

2. **Rebuild HTML**:
   ```bash
   python3 generate_enhanced_calendar.py
   ```

3. **Database optimization**:
   ```bash
   python3 cli.py optimize-db
   ```

4. **Update dependencies**:
   ```bash
   pip install -U -r requirements.txt
   ```

## API Documentation

### REST Endpoints

- `GET /api/events` - List all upcoming events
- `GET /api/events/{id}` - Get specific event
- `GET /api/categories` - List event categories
- `GET /api/venues` - List venues
- `GET /api/stats` - System statistics

### Response Format

```json
{
  "events": [
    {
      "id": "abc123",
      "title": "Konsert med lokalt band",
      "description": "En fantastisk kveld med musikk",
      "start": "2024-01-15T19:00:00+01:00",
      "venue": "Verket Scene",
      "category": "Musikk",
      "url": "https://example.com/event"
    }
  ],
  "total": 42,
  "page": 1
}
```

## Development

### Project Structure

```
/var/www/vhosts/herimoss.no/pythoncrawler/
├── main.py                 # Main crawler application
├── cli.py                  # Command-line interface
├── models.py               # Data models (Pydantic)
├── database.py             # Database operations
├── options.json            # Configuration
├── requirements.txt        # Python dependencies
│
├── scrapers/              # Source-specific scrapers
│   ├── moss_kommune.py
│   ├── ticketmaster_api.py
│   └── ...
│
├── templates/             # HTML templates
├── static/               # CSS, JS, images
├── logs/                 # Log files
├── state/                # State management
├── cache/                # Temporary cache
└── tests/                # Test suite
```

### Code Style

- **PEP 8** compliance
- **Type hints** throughout
- **Async/await** for I/O operations
- **Pydantic models** for data validation
- **Structured logging** with JSON format

### Testing

```bash
# Run all tests
python3 -m pytest tests/

# Test specific source
python3 test_moss_venues.py

# Integration tests
python3 validate_phase8.py
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Environment Variables

Create `.env` file with:

```bash
# OpenAI API (for ML categorization)
OPENAI_API_KEY=your_openai_api_key

# Database (if using MariaDB)
DB_HOST=localhost
DB_PORT=3306
DB_NAME=moss_events
DB_USER=events_user
DB_PASSWORD=secure_password

# API Keys
MEETUP_API_KEY=your_meetup_key
SONGKICK_API_KEY=your_songkick_key
BANDSINTOWN_APP_ID=your_app_id

# Facebook Graph API (optional)
FACEBOOK_ACCESS_TOKEN=your_fb_token
```

## Troubleshooting

### Common Issues

1. **Permission Denied**:
   ```bash
   sudo chown -R www-data:www-data /var/www/vhosts/herimoss.no/
   chmod -R 755 /var/www/vhosts/herimoss.no/pythoncrawler/
   ```

2. **Database Connection Failed**:
   ```bash
   # Check SQLite permissions
   ls -la events.db
   
   # Or create new database
   python3 cli.py init-db
   ```

3. **HTTP Timeout Errors**:
   ```json
   {
     "http": {
       "timeout_sec": 30,
       "rate_limit_per_host_per_sec": 0.5
     }
   }
   ```

4. **Memory Issues**:
   ```bash
   # Process in smaller batches
   python3 cli.py run --batch-size 25
   ```

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
python3 cli.py run --verbose
```

## Performance

### Optimization Tips

1. **Use batch processing** for large datasets
2. **Enable caching** for repeated requests
3. **Tune rate limits** based on source capacity
4. **Regular database maintenance**
5. **Monitor memory usage** during large crawls

### Benchmarks

Typical performance on modest hardware:
- **500 events/minute** processing rate
- **20+ sources** in under 10 minutes
- **<100MB RAM** usage during normal operation
- **Sub-second** HTML generation

## Security

### Best Practices

1. **API keys** stored in environment variables
2. **Input validation** via Pydantic models
3. **SQL injection** prevention with parameterized queries
4. **Rate limiting** to prevent abuse
5. **HTTPS only** for all external requests

### Data Privacy

- **No personal data** collection
- **Public events** only
- **GDPR compliant** (public information aggregation)
- **Opt-out mechanism** available for venues

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Changelog

### Version 2.0.0 (Current)
- Complete rewrite with async architecture
- ML-powered categorization and deduplication
- Comprehensive CLI and production deployment
- Multi-database support (SQLite + MariaDB)
- Advanced analytics and performance monitoring

### Version 1.0.0
- Initial release
- Basic scraping and HTML generation
- SQLite database
- Manual configuration

## Support

For issues, questions, or contributions:

1. **GitHub Issues**: [Report bugs or request features](https://github.com/SkySoft-Norway/herimoss/issues)
2. **Documentation**: Check this README and inline code comments
3. **Community**: Join local tech meetups in Moss/Oslo area

---

**Powered by**: Python 3.10+, AsyncIO, Pydantic, BeautifulSoup, OpenAI API, and ❤️ for the Moss cultural community.

**Maintained by**: SkySoft Norway - Building digital solutions for local communities since 2020.