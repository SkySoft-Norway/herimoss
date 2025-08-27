"""
Advanced Performance Monitoring    return _monitor


@dataclass
class PerformanceMetric:
    """Single performance measurement"""ation
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
class PerformanceMetric# Global instances
_monitor: Optional[PerformanceMonitor] = None
_cache: Optional[SmartCache] = None
_optimizer: Optional[ProcessingOptimizer] = None

def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor instance (alias for compatibility)"""
    return get_monitor()

def get_monitor() -> PerformanceMonitor:
    """Get global monitor instance"""
    global _monitor
    if _monitor is None:
        _monitor = PerformanceMonitor()
    return _monitorngle performance measurement"""
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
                    
                    # Check for alerts
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
    
    def measure_performance(self, operation_name: str):
        """Decorator for measuring function performance"""
        def decorator(func: Callable):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                process = psutil.Process()
                start_memory = process.memory_info().rss
                start_cpu = process.cpu_percent()
                
                status = 'success'
                details = {}
                
                try:
                    result = await func(*args, **kwargs)
                    return result
                    
                except Exception as e:
                    status = 'error'
                    details['error'] = str(e)
                    raise
                    
                finally:
                    end_time = time.time()
                    end_memory = process.memory_info().rss
                    end_cpu = process.cpu_percent()
                    
                    duration = end_time - start_time
                    memory_usage = max(start_memory, end_memory)
                    cpu_usage = max(start_cpu, end_cpu)
                    
                    metric = PerformanceMetric(
                        timestamp=datetime.now(),
                        operation=operation_name,
                        duration=duration,
                        memory_usage=memory_usage,
                        cpu_usage=cpu_usage,
                        status=status,
                        details=details
                    )
                    
                    self._add_metric(metric)
                    self._check_alerts(metric)
            
            return wrapper
        return decorator
    
    def get_performance_report(self, hours: int = 24) -> PerformanceReport:
        """Generate comprehensive performance report"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_metrics = [m for m in self.metrics_history if m.timestamp >= cutoff_time]
        
        if not recent_metrics:
            return PerformanceReport(
                start_time=cutoff_time,
                end_time=datetime.now(),
                total_operations=0,
                successful_operations=0,
                failed_operations=0,
                avg_duration=0.0,
                max_duration=0.0,
                min_duration=0.0,
                avg_memory=0.0,
                avg_cpu=0.0,
                bottlenecks=[],
                recommendations=[]
            )
        
        # Calculate statistics
        durations = [m.duration for m in recent_metrics if m.duration > 0]
        memory_usage = [m.memory_usage for m in recent_metrics]
        cpu_usage = [m.cpu_usage for m in recent_metrics]
        
        successful = sum(1 for m in recent_metrics if m.status == 'success')
        failed = sum(1 for m in recent_metrics if m.status == 'error')
        
        # Identify bottlenecks
        bottlenecks = self._identify_bottlenecks(recent_metrics)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(recent_metrics, bottlenecks)
        
        return PerformanceReport(
            start_time=cutoff_time,
            end_time=datetime.now(),
            total_operations=len(recent_metrics),
            successful_operations=successful,
            failed_operations=failed,
            avg_duration=sum(durations) / len(durations) if durations else 0.0,
            max_duration=max(durations) if durations else 0.0,
            min_duration=min(durations) if durations else 0.0,
            avg_memory=sum(memory_usage) / len(memory_usage) if memory_usage else 0.0,
            avg_cpu=sum(cpu_usage) / len(cpu_usage) if cpu_usage else 0.0,
            bottlenecks=bottlenecks,
            recommendations=recommendations
        )
    
    def _identify_bottlenecks(self, metrics: List[PerformanceMetric]) -> List[str]:
        """Identify performance bottlenecks"""
        bottlenecks = []
        
        # Group by operation
        operations = defaultdict(list)
        for metric in metrics:
            operations[metric.operation].append(metric)
        
        # Find slow operations
        for operation, op_metrics in operations.items():
            if len(op_metrics) < 2:
                continue
                
            avg_duration = sum(m.duration for m in op_metrics) / len(op_metrics)
            if avg_duration > 5.0:  # More than 5 seconds average
                bottlenecks.append(f"Slow operation: {operation} (avg: {avg_duration:.2f}s)")
        
        # Find memory-intensive operations
        for operation, op_metrics in operations.items():
            avg_memory = sum(m.memory_usage for m in op_metrics) / len(op_metrics)
            if avg_memory > 256 * 1024 * 1024:  # More than 256MB average
                memory_mb = avg_memory / 1024 / 1024
                bottlenecks.append(f"Memory-intensive: {operation} (avg: {memory_mb:.1f}MB)")
        
        # Find operations with high failure rate
        for operation, op_metrics in operations.items():
            if len(op_metrics) < 5:
                continue
                
            failures = sum(1 for m in op_metrics if m.status == 'error')
            failure_rate = failures / len(op_metrics)
            if failure_rate > 0.1:  # More than 10% failure rate
                bottlenecks.append(f"High failure rate: {operation} ({failure_rate:.1%})")
        
        return bottlenecks
    
    def _generate_recommendations(self, metrics: List[PerformanceMetric], bottlenecks: List[str]) -> List[str]:
        """Generate performance improvement recommendations"""
        recommendations = []
        
        # Analyze patterns
        total_metrics = len(metrics)
        if total_metrics == 0:
            return recommendations
        
        # Memory recommendations
        avg_memory = sum(m.memory_usage for m in metrics) / total_metrics
        memory_mb = avg_memory / 1024 / 1024
        
        if memory_mb > 200:
            recommendations.append("Consider implementing memory optimization strategies")
        if memory_mb > 400:
            recommendations.append("High memory usage detected - implement caching with TTL")
        
        # Duration recommendations
        durations = [m.duration for m in metrics if m.duration > 0]
        if durations:
            avg_duration = sum(durations) / len(durations)
            if avg_duration > 3.0:
                recommendations.append("Consider implementing async processing for slow operations")
            if max(durations) > 30.0:
                recommendations.append("Implement timeout handling for long-running operations")
        
        # Error rate recommendations
        errors = sum(1 for m in metrics if m.status == 'error')
        error_rate = errors / total_metrics
        if error_rate > 0.05:  # More than 5% error rate
            recommendations.append("Implement better error handling and retry mechanisms")
        
        # Bottleneck-specific recommendations
        if any('Slow operation' in b for b in bottlenecks):
            recommendations.append("Optimize slow operations with caching or parallel processing")
        
        if any('Memory-intensive' in b for b in bottlenecks):
            recommendations.append("Implement memory pooling and garbage collection optimization")
        
        if any('High failure rate' in b for b in bottlenecks):
            recommendations.append("Add circuit breaker pattern for unreliable operations")
        
        return recommendations
    
    def export_metrics(self, filepath: str, hours: int = 24):
        """Export metrics to JSON file"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_metrics = [m for m in self.metrics_history if m.timestamp >= cutoff_time]
        
        export_data = {
            'export_time': datetime.now().isoformat(),
            'period_hours': hours,
            'total_metrics': len(recent_metrics),
            'metrics': [asdict(m) for m in recent_metrics],
            'alerts': [a for a in self.alerts if a['timestamp'] >= cutoff_time]
        }
        
        # Convert datetime objects to strings
        for metric in export_data['metrics']:
            metric['timestamp'] = metric['timestamp'].isoformat()
        
        for alert in export_data['alerts']:
            alert['timestamp'] = alert['timestamp'].isoformat()
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        log_info(f"Performance metrics exported to {filepath}")


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
    
    def _estimate_size(self, obj: Any) -> int:
        """Estimate memory size of an object"""
        try:
            import sys
            return sys.getsizeof(obj)
        except:
            # Fallback estimation
            if isinstance(obj, str):
                return len(obj.encode('utf-8'))
            elif isinstance(obj, (list, tuple)):
                return sum(self._estimate_size(item) for item in obj)
            elif isinstance(obj, dict):
                return sum(self._estimate_size(k) + self._estimate_size(v) for k, v in obj.items())
            else:
                return 1024  # Default 1KB estimate
    
    def _cleanup_memory(self):
        """Clean up cache to free memory"""
        if self.current_memory <= self.max_memory:
            return
        
        # Remove least recently used items
        sorted_items = sorted(
            self.access_times.items(),
            key=lambda x: (self.hit_counts[x[0]], x[1])  # Sort by hit count, then access time
        )
        
        for key, _ in sorted_items:
            if self.current_memory <= self.max_memory * 0.8:  # Target 80% of max
                break
            
            if key in self.cache:
                obj_size = self._estimate_size(self.cache[key])
                del self.cache[key]
                del self.access_times[key]
                del self.hit_counts[key]
                self.current_memory -= obj_size
                self.stats['evictions'] += 1
        
        self.stats['memory_cleanups'] += 1
    
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache"""
        if key in self.cache:
            self.access_times[key] = time.time()
            self.hit_counts[key] += 1
            self.stats['hits'] += 1
            return self.cache[key]
        
        self.stats['misses'] += 1
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set item in cache with optional TTL"""
        obj_size = self._estimate_size(value)
        
        # Check if we need to cleanup memory
        if self.current_memory + obj_size > self.max_memory:
            self._cleanup_memory()
        
        # If still too big, don't cache
        if obj_size > self.max_memory * 0.5:  # Don't cache items larger than 50% of max
            return
        
        # Store with TTL information
        cache_entry = {
            'value': value,
            'expires': time.time() + ttl if ttl else None
        }
        
        # Remove old entry if exists
        if key in self.cache:
            old_size = self._estimate_size(self.cache[key])
            self.current_memory -= old_size
        
        self.cache[key] = cache_entry
        self.access_times[key] = time.time()
        self.current_memory += obj_size
    
    def delete(self, key: str):
        """Delete item from cache"""
        if key in self.cache:
            obj_size = self._estimate_size(self.cache[key])
            del self.cache[key]
            del self.access_times[key]
            if key in self.hit_counts:
                del self.hit_counts[key]
            self.current_memory -= obj_size
    
    def cleanup_expired(self):
        """Remove expired cache entries"""
        current_time = time.time()
        expired_keys = []
        
        for key, entry in self.cache.items():
            if isinstance(entry, dict) and 'expires' in entry:
                if entry['expires'] and current_time > entry['expires']:
                    expired_keys.append(key)
        
        for key in expired_keys:
            self.delete(key)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = self.stats['hits'] / max(total_requests, 1)
        
        return {
            'entries': len(self.cache),
            'memory_usage_mb': self.current_memory / 1024 / 1024,
            'memory_limit_mb': self.max_memory / 1024 / 1024,
            'hit_rate': hit_rate,
            'total_hits': self.stats['hits'],
            'total_misses': self.stats['misses'],
            'evictions': self.stats['evictions'],
            'memory_cleanups': self.stats['memory_cleanups']
        }
    
    def clear(self):
        """Clear all cache entries"""
        self.cache.clear()
        self.access_times.clear()
        self.hit_counts.clear()
        self.current_memory = 0


class ProcessingOptimizer:
    """Optimize processing through parallel execution and batching"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.semaphore = asyncio.Semaphore(max_workers)
    
    async def process_batch(self, items: List[Any], processor: Callable, batch_size: int = 50) -> List[Any]:
        """Process items in optimized batches"""
        if not items:
            return []
        
        results = []
        
        # Process in batches to avoid memory issues
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            batch_results = await self._process_batch_parallel(batch, processor)
            results.extend(batch_results)
            
            # Small delay between batches to prevent resource exhaustion
            if i + batch_size < len(items):
                await asyncio.sleep(0.1)
        
        return results
    
    async def _process_batch_parallel(self, batch: List[Any], processor: Callable) -> List[Any]:
        """Process a batch of items in parallel"""
        async def process_with_semaphore(item):
            async with self.semaphore:
                try:
                    return await processor(item)
                except Exception as e:
                    log_error("optimizer", f"Processing error: {e}")
                    return None
        
        tasks = [process_with_semaphore(item) for item in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out None results and exceptions
        return [r for r in results if r is not None and not isinstance(r, Exception)]


# Global instances
_monitor: Optional[PerformanceMonitor] = None
_cache: Optional[SmartCache] = None
_optimizer: Optional[ProcessingOptimizer] = None

def get_monitor() -> PerformanceMonitor:
    """Get global performance monitor instance"""
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

def get_processing_optimizer() -> ProcessingOptimizer:
    """Get global processing optimizer instance"""
    global _optimizer
    if _optimizer is None:
        _optimizer = ProcessingOptimizer()
    return _optimizer


def performance_monitor(operation_name: str):
    """Decorator for performance monitoring."""
    return get_monitor().measure_performance(operation_name)
