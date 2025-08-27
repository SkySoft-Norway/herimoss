"""
Logging system with JSON format and file rotation.
"""
import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path
import pytz
from models import LogEntry, ErrorEntry


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs JSON lines."""
    
    def __init__(self, tz_name: str = "Europe/Oslo"):
        super().__init__()
        self.tz = pytz.timezone(tz_name)
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON line."""
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc)
        local_time = timestamp.astimezone(self.tz)
        
        log_entry = {
            "ts": local_time.isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "source": getattr(record, "source", None),
            "url": getattr(record, "url", None)
        }
        
        # Remove None values
        log_entry = {k: v for k, v in log_entry.items() if v is not None}
        
        return json.dumps(log_entry, ensure_ascii=False)


class RotatingJSONLogger:
    """JSON logger with file rotation when file exceeds max size."""
    
    def __init__(self, 
                 log_file: str,
                 error_file: str,
                 max_size_mb: int = 5,
                 tz_name: str = "Europe/Oslo"):
        
        self.log_file = Path(log_file)
        self.error_file = Path(error_file)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.tz = pytz.timezone(tz_name)
        
        # Ensure directories exist
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.error_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Setup loggers
        self._setup_logger()
    
    def _setup_logger(self):
        """Setup Python logging with JSON formatter."""
        # Main logger
        self.logger = logging.getLogger("moss_kulturkalender")
        self.logger.setLevel(logging.DEBUG)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler for general logs
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(JSONFormatter(self.tz.zone))
        self.logger.addHandler(file_handler)
    
    def _rotate_if_needed(self, file_path: Path):
        """Rotate log file if it exceeds max size."""
        if file_path.exists() and file_path.stat().st_size > self.max_size_bytes:
            backup_path = file_path.with_suffix(f"{file_path.suffix}.1")
            if backup_path.exists():
                backup_path.unlink()
            file_path.rename(backup_path)
    
    def log(self, level: str, message: str, source: Optional[str] = None, url: Optional[str] = None):
        """Log a message."""
        self._rotate_if_needed(self.log_file)
        
        # Add extra fields to record
        extra = {}
        if source:
            extra["source"] = source
        if url:
            extra["url"] = url
        
        log_level = getattr(logging, level.upper(), logging.INFO)
        self.logger.log(log_level, message, extra=extra)
    
    def error(self, source: str, message: str, url: Optional[str] = None, 
              severity: str = "ERROR", stack: Optional[str] = None):
        """Log an error to the error file."""
        self._rotate_if_needed(self.error_file)
        
        timestamp = datetime.now(self.tz)
        
        error_entry = ErrorEntry(
            ts=timestamp,
            source=source,
            severity=severity,
            message=message,
            url=url,
            stack=stack
        )
        
        # Write to error file
        with open(self.error_file, 'a', encoding='utf-8') as f:
            # Use model_dump(mode='json') to ensure datetime is serialized as ISO string
            f.write(json.dumps(error_entry.model_dump(mode='json'), ensure_ascii=False) + '\n')
        
        # Also log to main logger
        self.log("ERROR", f"[{source}] {message}", source=source, url=url)
    
    def info(self, message: str, source: Optional[str] = None, url: Optional[str] = None):
        """Log info message."""
        self.log("INFO", message, source=source, url=url)
    
    def warning(self, message: str, source: Optional[str] = None, url: Optional[str] = None):
        """Log warning message."""
        self.log("WARN", message, source=source, url=url)
    
    def debug(self, message: str, source: Optional[str] = None, url: Optional[str] = None):
        """Log debug message."""
        self.log("DEBUG", message, source=source, url=url)


# Global logger instance
_logger: Optional[RotatingJSONLogger] = None


def init_logging(log_file: str = "log.json", 
                error_file: str = "feil.json",
                max_size_mb: int = 5,
                tz_name: str = "Europe/Oslo") -> RotatingJSONLogger:
    """Initialize global logger."""
    global _logger
    _logger = RotatingJSONLogger(log_file, error_file, max_size_mb, tz_name)
    return _logger


def get_logger() -> RotatingJSONLogger:
    """Get global logger instance."""
    if _logger is None:
        raise RuntimeError("Logger not initialized. Call init_logging() first.")
    return _logger


def log_info(message: str, source: Optional[str] = None, url: Optional[str] = None):
    """Log info message using global logger."""
    get_logger().info(message, source=source, url=url)


def log_warning(message: str, source: Optional[str] = None, url: Optional[str] = None):
    """Log warning message using global logger."""
    get_logger().warning(message, source=source, url=url)


def log_error(source: str, message: str, url: Optional[str] = None, 
              severity: str = "ERROR", stack: Optional[str] = None):
    """Log error message using global logger."""
    get_logger().error(source, message, url=url, severity=severity, stack=stack)


def log_debug(message: str, source: Optional[str] = None, url: Optional[str] = None):
    """Log debug message using global logger."""
    get_logger().debug(message, source=source, url=url)
