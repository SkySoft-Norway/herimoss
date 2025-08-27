#!/bin/bash
#
# Moss Kulturkalender - Production Deployment Script
# Sets up cron jobs and production environment
#

set -euo pipefail

# Configuration
CRAWLER_DIR="/var/www/vhosts/herimoss.no/pythoncrawler"
PYTHON_BIN="$CRAWLER_DIR/.venv/bin/python"
CLI_SCRIPT="$CRAWLER_DIR/cli.py"
LOG_DIR="$CRAWLER_DIR/logs"
DATA_DIR="$CRAWLER_DIR/data"
BACKUP_DIR="$CRAWLER_DIR/backups"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $1"
}

# Check if running as correct user
check_user() {
    local expected_user="herimoss"  # Adjust as needed
    if [[ "$(whoami)" != "$expected_user" && "$(whoami)" != "root" ]]; then
        log_warn "Running as $(whoami), expected $expected_user or root"
    fi
}

# Create necessary directories
setup_directories() {
    log_info "Setting up directory structure..."
    
    for dir in "$LOG_DIR" "$DATA_DIR" "$BACKUP_DIR"; do
        if [[ ! -d "$dir" ]]; then
            mkdir -p "$dir"
            log_info "Created directory: $dir"
        fi
    done
    
    # Set proper permissions
    chmod 755 "$CRAWLER_DIR"
    chmod 755 "$LOG_DIR" "$DATA_DIR" "$BACKUP_DIR"
    
    # Make CLI executable
    chmod +x "$CLI_SCRIPT"
}

# Install system dependencies
install_dependencies() {
    log_info "Checking system dependencies..."
    
    # Check for required system packages
    local required_packages=("python3" "python3-venv" "cron")
    local missing_packages=()
    
    for package in "${required_packages[@]}"; do
        if ! command -v "$package" &> /dev/null; then
            missing_packages+=("$package")
        fi
    done
    
    if [[ ${#missing_packages[@]} -gt 0 ]]; then
        log_warn "Missing packages: ${missing_packages[*]}"
        log_info "Install with: sudo apt-get install ${missing_packages[*]}"
    fi
    
    # Check Python virtual environment
    if [[ ! -f "$PYTHON_BIN" ]]; then
        log_error "Python virtual environment not found at $PYTHON_BIN"
        log_info "Create with: python3 -m venv $CRAWLER_DIR/.venv"
        log_info "Then install requirements: $PYTHON_BIN -m pip install -r $CRAWLER_DIR/requirements.txt"
        exit 1
    fi
}

# Setup cron jobs
setup_cron() {
    log_info "Setting up cron jobs..."
    
    # Backup existing crontab
    local cron_backup="/tmp/crontab_backup_$(date +%Y%m%d_%H%M%S)"
    crontab -l > "$cron_backup" 2>/dev/null || true
    log_info "Backed up existing crontab to $cron_backup"
    
    # Create new crontab entries
    local cron_entries
    read -r -d '' cron_entries << 'EOF' || true
# Moss Kulturkalender Event Crawler
# Main crawl runs every 2 hours during business days
0 */2 * * 1-5 cd /var/www/vhosts/herimoss.no/pythoncrawler && ./.venv/bin/python cli.py cron --max-runtime 1800 >> logs/cron.log 2>&1

# Weekend crawl runs every 4 hours  
0 */4 * * 0,6 cd /var/www/vhosts/herimoss.no/pythoncrawler && ./.venv/bin/python cli.py cron --max-runtime 1800 >> logs/cron.log 2>&1

# Daily cleanup at 2:30 AM
30 2 * * * cd /var/www/vhosts/herimoss.no/pythoncrawler && ./.venv/bin/python cli.py cleanup --days 30 --confirm >> logs/cleanup.log 2>&1

# Weekly analytics report on Sundays at 6:00 AM
0 6 * * 0 cd /var/www/vhosts/herimoss.no/pythoncrawler && ./.venv/bin/python cli.py analytics --days 7 --output-file reports/weekly_$(date +\%Y\%m\%d).json >> logs/analytics.log 2>&1

# Monthly database backup on 1st day at 3:00 AM
0 3 1 * * cd /var/www/vhosts/herimoss.no/pythoncrawler && ./deploy.sh backup >> logs/backup.log 2>&1

# System health check every hour
0 * * * * cd /var/www/vhosts/herimoss.no/pythoncrawler && ./.venv/bin/python cli.py status --quiet || echo "$(date): Health check failed" >> logs/health.log
EOF
    
    # Install cron jobs
    (crontab -l 2>/dev/null || true; echo "$cron_entries") | crontab -
    log_info "Cron jobs installed successfully"
    
    # Show current crontab
    log_info "Current crontab:"
    crontab -l | grep -A 20 "Moss Kulturkalender" || true
}

# Database backup function
backup_database() {
    log_info "Creating database backup..."
    
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="$BACKUP_DIR/events_backup_$timestamp.db"
    
    if [[ -f "$CRAWLER_DIR/events.db" ]]; then
        cp "$CRAWLER_DIR/events.db" "$backup_file"
        gzip "$backup_file"
        log_info "Database backed up to ${backup_file}.gz"
        
        # Keep only last 30 backups
        find "$BACKUP_DIR" -name "events_backup_*.db.gz" -type f | sort | head -n -30 | xargs rm -f
    else
        log_warn "Database file not found: $CRAWLER_DIR/events.db"
    fi
}

# Log rotation setup
setup_log_rotation() {
    log_info "Setting up log rotation..."
    
    local logrotate_config="/etc/logrotate.d/moss-kulturkalender"
    
    if [[ -w "/etc/logrotate.d" ]]; then
        cat > "$logrotate_config" << EOF
$LOG_DIR/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 $(whoami) $(whoami)
    postrotate
        # Signal processes to reopen log files if needed
    endscript
}
EOF
        log_info "Log rotation configured at $logrotate_config"
    else
        log_warn "Cannot write to /etc/logrotate.d - run as root or configure manually"
    fi
}

# System validation
validate_system() {
    log_info "Validating system setup..."
    
    # Check file permissions
    if [[ ! -x "$CLI_SCRIPT" ]]; then
        log_error "CLI script is not executable: $CLI_SCRIPT"
        return 1
    fi
    
    # Check Python environment
    if ! "$PYTHON_BIN" -c "import sys; print(f'Python {sys.version}')" 2>/dev/null; then
        log_error "Python environment test failed"
        return 1
    fi
    
    # Test basic CLI functionality
    if ! "$PYTHON_BIN" "$CLI_SCRIPT" validate --quiet; then
        log_error "System validation failed"
        return 1
    fi
    
    # Check disk space
    local disk_usage=$(df "$CRAWLER_DIR" | awk 'NR==2 {print $5}' | sed 's/%//')
    if [[ $disk_usage -gt 80 ]]; then
        log_warn "Disk usage is high: ${disk_usage}%"
    fi
    
    # Check cron service
    if ! systemctl is-active --quiet cron 2>/dev/null; then
        log_warn "Cron service is not running"
    fi
    
    log_info "✅ System validation completed"
}

# Performance tuning
setup_performance() {
    log_info "Applying performance optimizations..."
    
    # Create performance config
    local perf_config="$CRAWLER_DIR/performance.conf"
    cat > "$perf_config" << EOF
# Performance Configuration for Moss Kulturkalender
# Adjust these values based on your system resources

# Database settings
SQLITE_CACHE_SIZE=10000
SQLITE_SYNCHRONOUS=NORMAL
SQLITE_JOURNAL_MODE=WAL

# HTTP settings
MAX_CONCURRENT_REQUESTS=10
REQUEST_TIMEOUT=30
MAX_RETRIES=3

# Memory settings
MAX_EVENTS_IN_MEMORY=5000
CACHE_SIZE_MB=100

# Logging
LOG_LEVEL=INFO
LOG_ROTATION_SIZE=10M
EOF
    
    log_info "Performance configuration saved to $perf_config"
}

# Security hardening
setup_security() {
    log_info "Applying security configurations..."
    
    # Set restrictive file permissions
    find "$CRAWLER_DIR" -type f -name "*.py" -exec chmod 644 {} \;
    find "$CRAWLER_DIR" -type f -name "*.json" -exec chmod 600 {} \;
    find "$CRAWLER_DIR" -type f -name "*.db" -exec chmod 600 {} \;
    
    # Secure log directory
    chmod 750 "$LOG_DIR"
    
    # Create robots.txt compliance check
    local robots_check="$CRAWLER_DIR/check_robots.py"
    cat > "$robots_check" << 'EOF'
#!/usr/bin/env python3
"""
Check robots.txt compliance for all configured sources
"""
import asyncio
import json
from urllib.robotparser import RobotFileParser
from utils import HttpClient

async def check_all_sources():
    with open('options.json', 'r') as f:
        config = json.load(f)
    
    client = HttpClient()
    issues = []
    
    for source_name, source_config in config.get('sources', {}).items():
        url = source_config.get('url')
        if not url:
            continue
            
        # Check robots.txt
        try:
            base_url = f"{url.split('://')[0]}://{url.split('/')[2]}"
            robots_url = f"{base_url}/robots.txt"
            
            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            
            if not rp.can_fetch('*', url):
                issues.append(f"⚠️  {source_name}: {url} may be disallowed by robots.txt")
                
        except Exception as e:
            print(f"Could not check robots.txt for {source_name}: {e}")
    
    if issues:
        print("🚨 Robots.txt compliance issues found:")
        for issue in issues:
            print(f"  {issue}")
        return False
    else:
        print("✅ All sources comply with robots.txt")
        return True

if __name__ == "__main__":
    asyncio.run(check_all_sources())
EOF
    
    chmod +x "$robots_check"
    log_info "Security configurations applied"
}

# Monitoring setup
setup_monitoring() {
    log_info "Setting up monitoring..."
    
    # Create monitoring script
    local monitor_script="$CRAWLER_DIR/monitor.sh"
    cat > "$monitor_script" << 'EOF'
#!/bin/bash
#
# System monitoring for Moss Kulturkalender
#

CRAWLER_DIR="/var/www/vhosts/herimoss.no/pythoncrawler"
PYTHON_BIN="$CRAWLER_DIR/.venv/bin/python"

# Check if last run was successful
check_last_run() {
    local log_file="$CRAWLER_DIR/logs/cron.log"
    if [[ -f "$log_file" ]]; then
        local last_error=$(tail -100 "$log_file" | grep -i error | tail -1)
        if [[ -n "$last_error" ]]; then
            echo "🚨 Recent error found: $last_error"
            return 1
        fi
    fi
    return 0
}

# Check database health
check_database() {
    if ! "$PYTHON_BIN" -c "
import sqlite3
conn = sqlite3.connect('$CRAWLER_DIR/events.db')
cursor = conn.execute('SELECT COUNT(*) FROM events')
count = cursor.fetchone()[0]
print(f'Database OK: {count} events')
conn.close()
" 2>/dev/null; then
        echo "🚨 Database health check failed"
        return 1
    fi
    return 0
}

# Main monitoring function
main() {
    echo "🔍 System health check - $(date)"
    
    local issues=0
    
    if ! check_last_run; then
        ((issues++))
    fi
    
    if ! check_database; then
        ((issues++))
    fi
    
    if [[ $issues -eq 0 ]]; then
        echo "✅ All checks passed"
    else
        echo "❌ $issues issues found"
        # Could send notification here
    fi
    
    return $issues
}

main "$@"
EOF
    
    chmod +x "$monitor_script"
    log_info "Monitoring script created at $monitor_script"
}

# Generate deployment report
generate_report() {
    log_info "Generating deployment report..."
    
    local report_file="$CRAWLER_DIR/deployment_report_$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$report_file" << EOF
MOSS KULTURKALENDER - DEPLOYMENT REPORT
Generated: $(date)
======================================

SYSTEM INFORMATION:
- OS: $(uname -a)
- User: $(whoami)
- Python: $("$PYTHON_BIN" --version)
- Working Directory: $CRAWLER_DIR

DIRECTORY STRUCTURE:
$(find "$CRAWLER_DIR" -maxdepth 2 -type d | sort)

FILE PERMISSIONS:
$(ls -la "$CRAWLER_DIR"/*.py "$CRAWLER_DIR"/*.json 2>/dev/null | head -10)

CRON JOBS:
$(crontab -l | grep -A 10 "Moss Kulturkalender" || echo "No cron jobs found")

DISK USAGE:
$(df -h "$CRAWLER_DIR")

RECENT LOGS:
$(tail -5 "$LOG_DIR"/*.log 2>/dev/null || echo "No log files found")

VALIDATION RESULTS:
$("$PYTHON_BIN" "$CLI_SCRIPT" validate 2>&1 || echo "Validation failed")

DEPLOYMENT STATUS: COMPLETED
======================================
EOF
    
    log_info "Deployment report saved to $report_file"
}

# Main deployment function
deploy() {
    log_info "🚀 Starting Moss Kulturkalender deployment..."
    
    check_user
    setup_directories
    install_dependencies
    setup_performance
    setup_security
    setup_cron
    setup_log_rotation
    setup_monitoring
    validate_system
    generate_report
    
    log_info "✅ Deployment completed successfully!"
    log_info ""
    log_info "Next steps:"
    log_info "1. Test the CLI: $PYTHON_BIN $CLI_SCRIPT run --dry-run"
    log_info "2. Check logs: tail -f logs/cron.log"
    log_info "3. Monitor system: ./monitor.sh"
    log_info "4. View status: $PYTHON_BIN $CLI_SCRIPT status"
}

# Handle command line arguments
case "${1:-deploy}" in
    deploy)
        deploy
        ;;
    backup)
        backup_database
        ;;
    monitor)
        setup_monitoring
        ;;
    validate)
        validate_system
        ;;
    cron)
        setup_cron
        ;;
    *)
        echo "Usage: $0 {deploy|backup|monitor|validate|cron}"
        echo ""
        echo "Commands:"
        echo "  deploy   - Full deployment setup (default)"
        echo "  backup   - Create database backup"
        echo "  monitor  - Setup monitoring only"
        echo "  validate - Validate system only"
        echo "  cron     - Setup cron jobs only"
        exit 1
        ;;
esac
