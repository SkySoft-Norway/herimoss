"""
Advanced Performance Monitoring and Optimization
Comprehensive performance tracking, caching and optimization for event crawler
"""

import asyncio
import time
import json
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from pathlib import Path
from collections import defaultdict, deque
import functools
import threading

from logging_utils import log_info, log_warning, log_error


@dataclass
class PerformanceMetric:
    """Single performance measurement"""
    timestamp: datetime
    operation: str
    duration: float
    memory_usage: float
    cpu_usage: float
    status: str  # 'success', 'error', 'timeout'
    details: Dict[str, Any]


@dataclass  
class PerformanceReport:
    """Comprehensive performance report"""
    start_time: datetime
    end_time: datetime
    total_operations: int
    successful_operations: int
    failed_operations: int
    avg_duration: float
    max_duration: float
    min_duration: float
    avg_memory: float
    avg_cpu: float
    bottlenecks: List[str]
    recommendations: List[str]


class PerformanceMonitor:
    """Advanced performance monitoring system"""
    
    def __init__(self, max_history: int = 10000):
        self.metrics_history = deque(maxlen=max_history)
        self.operation_stats = defaultdict(list)
        self.alerts = []
        self.monitoring_active = True
        
        # Performance thresholds
        self.thresholds = {
            'max_duration': 30.0,      # seconds
            'max_memory': 512 * 1024 * 1024,  # 512MB
            'max_cpu': 80.0,           # percentage
            'min_success_rate': 0.95   # 95%
        }
        
        # Start background monitoring
        self._start_background_monitoring()
    
    async def initialize(self):
        """Initialize performance monitoring"""
        log_info("🚀 Performance monitoring initialized")
    
    async def start_monitoring(self):
        """Start monitoring"""
        self.monitoring_active = True
        log_info("📊 Performance monitoring started")
    
    async def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring_active = False
        log_info("⏹️ Performance monitoring stopped")
    
    async def get_current_metrics(self) -> Dict[str, Any]:
        """Get current system metrics"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            
            return {
                'cpu_percent': process.cpu_percent(),
                'memory_percent': process.memory_percent(),
                'memory_mb': memory_info.rss / 1024 / 1024,
                'disk_usage': psutil.disk_usage('/').percent,
                'active_connections': len(process.connections())
            }
        except Exception as e:
            log_error("monitor", f"Failed to get metrics: {e}")
            return {}
    
    async def start_processing_session(self, item_count: int) -> str:
        """Start a processing session"""
        session_id = f"session_{int(time.time())}"
        log_info(f"🔄 Started processing session {session_id} with {item_count} items")
        return session_id
    
    async def complete_processing_session(self, session_id: str, error: str = None):
        """Complete a processing session"""
        if error:
            log_error("session", f"Session {session_id} completed with error: {error}")
        else:
            log_info(f"✅ Session {session_id} completed successfully")
    
    def get_cache(self):
        """Get cache instance"""
        return get_cache()
    
    def _start_background_monitoring(self):
        """Start background system monitoring"""
        def monitor_system():
            while self.monitoring_active:
                try:
                    # Monitor system resources
                    process = psutil.Process()
                    memory_info = process.memory_info()
                    cpu_percent = process.cpu_percent()
                    
                    # Log system metrics every 60 seconds
                    metric = PerformanceMetric(
                        timestamp=datetime.now(),
                        operation='system_monitor',
                        duration=0.0,
                        memory_usage=memory_info.rss,
                        cpu_usage=cpu_percent,
                        status='success',
                        details={
                            'memory_mb': memory_info.rss / 1024 / 1024,
                            'cpu_percent': cpu_percent,
                            'threads': threading.active_count()
                        }
                    )
                    
                    self._add_metric(metric)
                    self._check_alerts(metric)
                    
                    time.sleep(60)  # Monitor every minute
                    
                except Exception as e:
                    log_error("monitor", f"System monitoring error: {e}")
                    time.sleep(60)
        
        monitor_thread = threading.Thread(target=monitor_system, daemon=True)
        monitor_thread.start()
    
    def _add_metric(self, metric: PerformanceMetric):
        """Add metric to history"""
        self.metrics_history.append(metric)
        self.operation_stats[metric.operation].append(metric)
    
    def _check_alerts(self, metric: PerformanceMetric):
        """Check for performance alerts"""
        alerts = []
        
        if metric.duration > self.thresholds['max_duration']:
            alerts.append(f"Slow operation: {metric.operation} took {metric.duration:.2f}s")
        
        if metric.memory_usage > self.thresholds['max_memory']:
            memory_mb = metric.memory_usage / 1024 / 1024
            alerts.append(f"High memory usage: {memory_mb:.1f}MB during {metric.operation}")
        
        if metric.cpu_usage > self.thresholds['max_cpu']:
            alerts.append(f"High CPU usage: {metric.cpu_usage:.1f}% during {metric.operation}")
        
        for alert in alerts:
            self.alerts.append({
                'timestamp': metric.timestamp,
                'severity': 'warning',
                'message': alert
            })
            log_warning(alert)


class SmartCache:
    """Intelligent caching system with adaptive TTL and memory management"""
    
    def __init__(self, max_memory_mb: int = 100):
        self.cache = {}
        self.access_times = {}
        self.hit_counts = defaultdict(int)
        self.max_memory = max_memory_mb * 1024 * 1024  # Convert to bytes
        self.current_memory = 0
        
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'memory_cleanups': 0
        }
    
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache"""
        if key in self.cache:
            entry = self.cache[key]
            
            # Check if expired
            if isinstance(entry, dict) and 'expires' in entry:
                if entry['expires'] and time.time() > entry['expires']:
                    self.delete(key)
                    self.stats['misses'] += 1
                    return None
                value = entry['value'] if 'value' in entry else entry
            else:
                value = entry
            
            self.access_times[key] = time.time()
            self.hit_counts[key] += 1
            self.stats['hits'] += 1
            return value
        
        self.stats['misses'] += 1
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set item in cache with optional TTL"""
        # Store with TTL information
        cache_entry = {
            'value': value,
            'expires': time.time() + ttl if ttl else None
        }
        
        self.cache[key] = cache_entry
        self.access_times[key] = time.time()
    
    def delete(self, key: str):
        """Delete item from cache"""
        if key in self.cache:
            del self.cache[key]
            if key in self.access_times:
                del self.access_times[key]
            if key in self.hit_counts:
                del self.hit_counts[key]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = self.stats['hits'] / max(total_requests, 1)
        
        return {
            'total_items': len(self.cache),
            'memory_usage': len(str(self.cache).encode('utf-8')),  # Rough estimate
            'hit_rate': hit_rate,
            'total_hits': self.stats['hits'],
            'total_misses': self.stats['misses']
        }


# Global instances
_monitor: Optional[PerformanceMonitor] = None
_cache: Optional[SmartCache] = None

def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor instance"""
    return get_monitor()

def get_monitor() -> PerformanceMonitor:
    """Get global monitor instance"""
    global _monitor
    if _monitor is None:
        _monitor = PerformanceMonitor()
    return _monitor

def get_cache() -> SmartCache:
    """Get global cache instance"""
    global _cache
    if _cache is None:
        _cache = SmartCache()
    return _cache
