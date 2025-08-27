#!/usr/bin/env python3
"""
Environment Configuration Manager for Moss Kulturkalender
Handles loading and validation of environment variables
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any

class MossConfig:
    """Configuration manager for Moss Kulturkalender"""
    
    def __init__(self, env_file: str = ".env"):
        self.env_file = env_file
        self.config = {}
        self.load_environment()
    
    def load_environment(self):
        """Load environment variables from .env file"""
        
        env_path = Path(__file__).parent / self.env_file
        
        if env_path.exists():
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        self.config[key.strip()] = value.strip()
                        # Also set as environment variable
                        os.environ[key.strip()] = value.strip()
        else:
            logging.warning(f"Environment file {env_path} not found")
    
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get configuration value"""
        return self.config.get(key, os.environ.get(key, default))
    
    def get_int(self, key: str, default: int = 0) -> int:
        """Get configuration value as integer"""
        value = self.get(key)
        try:
            return int(value) if value else default
        except ValueError:
            return default
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get configuration value as boolean"""
        value = self.get(key, '').lower()
        return value in ('true', '1', 'yes', 'on')
    
    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get configuration value as float"""
        value = self.get(key)
        try:
            return float(value) if value else default
        except ValueError:
            return default
    
    def validate_ticketmaster_config(self) -> Dict[str, Any]:
        """Validate Ticketmaster API configuration"""
        
        validation = {
            'valid': True,
            'errors': [],
            'config': {}
        }
        
        # Required Ticketmaster settings
        api_key = self.get('TICKETMASTER_API_KEY')
        if not api_key or api_key == 'YOUR_TICKETMASTER_API_KEY_HERE':
            validation['errors'].append('TICKETMASTER_API_KEY not set or using placeholder')
            validation['valid'] = False
        
        base_url = self.get('TICKETMASTER_BASE_URL', 'https://app.ticketmaster.com/discovery/v2')
        rate_limit = self.get_int('TICKETMASTER_RATE_LIMIT', 5000)
        
        validation['config'] = {
            'api_key': api_key,
            'base_url': base_url,
            'rate_limit': rate_limit,
            'has_secret': bool(self.get('TICKETMASTER_API_SECRET'))
        }
        
        return validation
    
    def validate_database_config(self) -> Dict[str, Any]:
        """Validate database configuration"""
        
        validation = {
            'valid': True,
            'errors': [],
            'config': {}
        }
        
        db_path = self.get('DATABASE_PATH', '/var/www/vhosts/herimoss.no/pythoncrawler/events.db')
        
        # Check if database directory exists
        db_dir = Path(db_path).parent
        if not db_dir.exists():
            validation['errors'].append(f'Database directory does not exist: {db_dir}')
            validation['valid'] = False
        
        validation['config'] = {
            'database_path': db_path,
            'backup_path': self.get('BACKUP_DATABASE_PATH'),
            'database_exists': Path(db_path).exists()
        }
        
        return validation
    
    def validate_all(self) -> Dict[str, Any]:
        """Validate all configuration"""
        
        result = {
            'overall_valid': True,
            'ticketmaster': self.validate_ticketmaster_config(),
            'database': self.validate_database_config()
        }
        
        if not result['ticketmaster']['valid'] or not result['database']['valid']:
            result['overall_valid'] = False
        
        return result
    
    def setup_logging(self):
        """Setup logging based on configuration"""
        
        log_level = self.get('LOG_LEVEL', 'INFO').upper()
        log_file = self.get('LOG_FILE')
        
        # Create logs directory if it doesn't exist
        if log_file:
            log_dir = Path(log_file).parent
            log_dir.mkdir(parents=True, exist_ok=True)
        
        logging.basicConfig(
            level=getattr(logging, log_level, logging.INFO),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(log_file) if log_file else logging.NullHandler()
            ]
        )
    
    def get_ticketmaster_config(self) -> Dict[str, Any]:
        """Get complete Ticketmaster configuration"""
        
        return {
            'api_key': self.get('TICKETMASTER_API_KEY'),
            'api_secret': self.get('TICKETMASTER_API_SECRET'),
            'base_url': self.get('TICKETMASTER_BASE_URL', 'https://app.ticketmaster.com/discovery/v2'),
            'rate_limit': self.get_int('TICKETMASTER_RATE_LIMIT', 5000),
            'rate_limit_window': self.get_int('TICKETMASTER_RATE_LIMIT_WINDOW', 86400)
        }
    
    def get_scraping_config(self) -> Dict[str, Any]:
        """Get web scraping configuration"""
        
        return {
            'user_agent': self.get('USER_AGENT', 'Mozilla/5.0 (compatible; MossKalender/1.0)'),
            'request_timeout': self.get_float('REQUEST_TIMEOUT', 10.0),
            'request_delay': self.get_float('REQUEST_DELAY', 1.0),
            'max_retries': self.get_int('MAX_RETRIES', 3)
        }

# Global configuration instance
config = MossConfig()

def main():
    """Test and validate configuration"""
    
    print("🔧 MOSS KULTURKALENDER CONFIGURATION VALIDATION")
    print("=" * 55)
    
    # Load configuration
    config.setup_logging()
    
    # Validate all settings
    validation = config.validate_all()
    
    print(f"\n✅ OVERALL VALIDATION: {'PASSED' if validation['overall_valid'] else 'FAILED'}")
    
    # Ticketmaster validation
    print(f"\n🎫 TICKETMASTER CONFIGURATION:")
    tm_validation = validation['ticketmaster']
    print(f"Status: {'✅ VALID' if tm_validation['valid'] else '❌ INVALID'}")
    
    if tm_validation['errors']:
        print("Errors:")
        for error in tm_validation['errors']:
            print(f"  • {error}")
    
    tm_config = tm_validation['config']
    print(f"API Key: {'✅ Set' if tm_config['api_key'] != 'YOUR_TICKETMASTER_API_KEY_HERE' else '❌ Not set'}")
    print(f"Base URL: {tm_config['base_url']}")
    print(f"Rate Limit: {tm_config['rate_limit']} requests/day")
    print(f"Has Secret: {'✅ Yes' if tm_config['has_secret'] else '❌ No'}")
    
    # Database validation
    print(f"\n💾 DATABASE CONFIGURATION:")
    db_validation = validation['database']
    print(f"Status: {'✅ VALID' if db_validation['valid'] else '❌ INVALID'}")
    
    if db_validation['errors']:
        print("Errors:")
        for error in db_validation['errors']:
            print(f"  • {error}")
    
    db_config = db_validation['config']
    print(f"Database Path: {db_config['database_path']}")
    print(f"Database Exists: {'✅ Yes' if db_config['database_exists'] else '❌ No'}")
    print(f"Backup Path: {db_config['backup_path'] or 'Not set'}")
    
    # Show sample configuration
    print(f"\n🛠️  SCRAPING CONFIGURATION:")
    scraping_config = config.get_scraping_config()
    for key, value in scraping_config.items():
        print(f"{key}: {value}")
    
    print(f"\n📋 NEXT STEPS:")
    if not validation['overall_valid']:
        print("1. Fix configuration errors above")
        print("2. Update .env file with your actual API keys")
        print("3. Run validation again")
    else:
        print("1. ✅ Configuration is valid!")
        print("2. Ready to integrate Ticketmaster API")
        print("3. Test API connection with ticketmaster_client.py")

if __name__ == "__main__":
    main()
