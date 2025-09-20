"""
Performance monitoring utilities for ML service optimization
"""
import time
import psutil
import threading
from typing import Dict, List, Any, Optional
from collections import deque, defaultdict
from datetime import datetime, timedelta
import statistics

from app.utils.logging import get_logger


logger = get_logger(__name__)


class PerformanceMetrics:
    """Collect and analyze performance metrics"""
    
    def __init__(self, max_samples: int = 1000):
        self.max_samples = max_samples
        self.metrics = defaultdict(lambda: deque(maxlen=max_samples))
        self.lock = threading.RLock()
        
    def record_metric(self, name: str, value: float, timestamp: Optional[datetime] = None):
        """Record a performance metric"""
        with self.lock:
            if timestamp is None:
                timestamp = datetime.now()
            
            self.metrics[name].append({
                "value": value,
                "timestamp": timestamp
            })
    
    def get_metric_stats(self, name: str, window_minutes: int = 60) -> Dict[str, Any]:
        """Get statistics for a metric within time window"""
        with self.lock:
            if name not in self.metrics:
                return {}
            
            # Filter by time window
            cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
            recent_values = [
                entry["value"] for entry in self.metrics[name]
                if entry["timestamp"] >= cutoff_time
            ]
            
            if not recent_values:
                return {}
            
            return {
                "count": len(recent_values),
                "mean": statistics.mean(recent_values),
                "median": statistics.median(recent_values),
                "min": min(recent_values),
                "max": max(recent_values),
                "std_dev": statistics.stdev(recent_values) if len(recent_values) > 1 else 0,
                "percentile_95": statistics.quantiles(recent_values, n=20)[18] if len(recent_values) >= 20 else max(recent_values),
                "window_minutes": window_minutes
            }
    
    def get_all_metrics(self, window_minutes: int = 60) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all metrics"""
        with self.lock:
            return {
                name: self.get_metric_stats(name, window_minutes)
                for name in self.metrics.keys()
            }
    
    def clear_old_metrics(self, hours_old: int = 24):
        """Clear metrics older than specified hours"""
        with self.lock:
            cutoff_time = datetime.now() - timedelta(hours=hours_old)
            
            for name in self.metrics:
                # Filter out old entries
                self.metrics[name] = deque(
                    [entry for entry in self.metrics[name] 
                     if entry["timestamp"] >= cutoff_time],
                    maxlen=self.max_samples
                )


class SystemMonitor:
    """Monitor system resources in real-time"""
    
    def __init__(self, sample_interval: int = 30):
        self.sample_interval = sample_interval
        self.metrics = PerformanceMetrics()
        self.monitoring = False
        self.monitor_thread = None
        
    def start_monitoring(self):
        """Start background system monitoring"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("system_monitoring_started", interval=self.sample_interval)
    
    def stop_monitoring(self):
        """Stop background monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("system_monitoring_stopped")
    
    def _monitor_loop(self):
        """Background monitoring loop"""
        while self.monitoring:
            try:
                self._collect_system_metrics()
                time.sleep(self.sample_interval)
            except Exception as e:
                logger.error("system_monitoring_error", error=str(e))
                time.sleep(self.sample_interval)
    
    def _collect_system_metrics(self):
        """Collect current system metrics"""
        timestamp = datetime.now()
        
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        self.metrics.record_metric("cpu_usage_percent", cpu_percent, timestamp)
        
        # Memory metrics
        memory = psutil.virtual_memory()
        self.metrics.record_metric("memory_usage_percent", memory.percent, timestamp)
        self.metrics.record_metric("memory_used_gb", memory.used / (1024**3), timestamp)
        self.metrics.record_metric("memory_available_gb", memory.available / (1024**3), timestamp)
        
        # Disk metrics
        disk = psutil.disk_usage('/')
        disk_percent = (disk.used / disk.total) * 100
        self.metrics.record_metric("disk_usage_percent", disk_percent, timestamp)
        
        # GPU metrics if available
        try:
            import torch
            if torch.cuda.is_available():
                gpu_memory_allocated = torch.cuda.memory_allocated() / (1024**3)
                gpu_memory_reserved = torch.cuda.memory_reserved() / (1024**3)
                gpu_memory_total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                gpu_usage_percent = (gpu_memory_allocated / gpu_memory_total) * 100
                
                self.metrics.record_metric("gpu_memory_usage_percent", gpu_usage_percent, timestamp)
                self.metrics.record_metric("gpu_memory_allocated_gb", gpu_memory_allocated, timestamp)
                self.metrics.record_metric("gpu_memory_reserved_gb", gpu_memory_reserved, timestamp)
        except ImportError:
            pass
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current system metrics snapshot"""
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Memory
            memory = psutil.virtual_memory()
            
            # Disk
            disk = psutil.disk_usage('/')
            
            metrics = {
                "timestamp": datetime.now().isoformat(),
                "cpu": {
                    "usage_percent": cpu_percent,
                    "count": psutil.cpu_count()
                },
                "memory": {
                    "usage_percent": memory.percent,
                    "used_gb": memory.used / (1024**3),
                    "available_gb": memory.available / (1024**3),
                    "total_gb": memory.total / (1024**3)
                },
                "disk": {
                    "usage_percent": (disk.used / disk.total) * 100,
                    "used_gb": disk.used / (1024**3),
                    "free_gb": disk.free / (1024**3),
                    "total_gb": disk.total / (1024**3)
                }
            }
            
            # Add GPU metrics if available
            try:
                import torch
                if torch.cuda.is_available():
                    gpu_memory_allocated = torch.cuda.memory_allocated() / (1024**3)
                    gpu_memory_total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                    
                    metrics["gpu"] = {
                        "available": True,
                        "memory_allocated_gb": gpu_memory_allocated,
                        "memory_total_gb": gpu_memory_total,
                        "usage_percent": (gpu_memory_allocated / gpu_memory_total) * 100
                    }
                else:
                    metrics["gpu"] = {"available": False}
            except ImportError:
                metrics["gpu"] = {"available": False}
            
            return metrics
            
        except Exception as e:
            logger.error("get_current_metrics_failed", error=str(e))
            return {}
    
    def get_performance_report(self, window_minutes: int = 60) -> Dict[str, Any]:
        """Generate performance report"""
        return {
            "report_time": datetime.now().isoformat(),
            "window_minutes": window_minutes,
            "metrics": self.metrics.get_all_metrics(window_minutes),
            "current_snapshot": self.get_current_metrics()
        }


class RequestTracker:
    """Track API request performance and patterns"""
    
    def __init__(self):
        self.requests = deque(maxlen=10000)
        self.lock = threading.RLock()
        
    def record_request(self, endpoint: str, method: str, duration_ms: int, 
                      status_code: int, user_id: Optional[int] = None):
        """Record API request metrics"""
        with self.lock:
            self.requests.append({
                "timestamp": datetime.now(),
                "endpoint": endpoint,
                "method": method,
                "duration_ms": duration_ms,
                "status_code": status_code,
                "user_id": user_id
            })
    
    def get_request_stats(self, window_minutes: int = 60) -> Dict[str, Any]:
        """Get request statistics for time window"""
        with self.lock:
            cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
            recent_requests = [
                req for req in self.requests
                if req["timestamp"] >= cutoff_time
            ]
            
            if not recent_requests:
                return {
                    "total_requests": 0,
                    "window_minutes": window_minutes
                }
            
            # Calculate statistics
            durations = [req["duration_ms"] for req in recent_requests]
            status_codes = defaultdict(int)
            endpoints = defaultdict(int)
            methods = defaultdict(int)
            
            for req in recent_requests:
                status_codes[req["status_code"]] += 1
                endpoints[req["endpoint"]] += 1
                methods[req["method"]] += 1
            
            return {
                "total_requests": len(recent_requests),
                "requests_per_minute": len(recent_requests) / window_minutes,
                "avg_duration_ms": statistics.mean(durations),
                "median_duration_ms": statistics.median(durations),
                "min_duration_ms": min(durations),
                "max_duration_ms": max(durations),
                "p95_duration_ms": statistics.quantiles(durations, n=20)[18] if len(durations) >= 20 else max(durations),
                "status_codes": dict(status_codes),
                "top_endpoints": dict(sorted(endpoints.items(), key=lambda x: x[1], reverse=True)[:10]),
                "methods": dict(methods),
                "error_rate": sum(1 for req in recent_requests if req["status_code"] >= 400) / len(recent_requests),
                "window_minutes": window_minutes
            }
    
    def get_slowest_requests(self, limit: int = 10, window_minutes: int = 60) -> List[Dict[str, Any]]:
        """Get slowest requests in time window"""
        with self.lock:
            cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
            recent_requests = [
                req for req in self.requests
                if req["timestamp"] >= cutoff_time
            ]
            
            # Sort by duration and return top N
            slowest = sorted(recent_requests, key=lambda x: x["duration_ms"], reverse=True)[:limit]
            
            return [
                {
                    "timestamp": req["timestamp"].isoformat(),
                    "endpoint": req["endpoint"],
                    "method": req["method"],
                    "duration_ms": req["duration_ms"],
                    "status_code": req["status_code"]
                }
                for req in slowest
            ]


class PerformanceOptimizer:
    """Analyze performance data and suggest optimizations"""
    
    def __init__(self, system_monitor: SystemMonitor, request_tracker: RequestTracker):
        self.system_monitor = system_monitor
        self.request_tracker = request_tracker
        
    def analyze_performance(self, window_minutes: int = 60) -> Dict[str, Any]:
        """Analyze system performance and provide recommendations"""
        system_report = self.system_monitor.get_performance_report(window_minutes)
        request_stats = self.request_tracker.get_request_stats(window_minutes)
        
        recommendations = []
        issues = []
        
        # Analyze system metrics
        metrics = system_report.get("metrics", {})
        
        # CPU analysis
        if "cpu_usage_percent" in metrics:
            cpu_stats = metrics["cpu_usage_percent"]
            if cpu_stats.get("mean", 0) > 80:
                issues.append("High CPU usage detected")
                recommendations.append("Consider scaling horizontally or optimizing CPU-intensive operations")
        
        # Memory analysis
        if "memory_usage_percent" in metrics:
            memory_stats = metrics["memory_usage_percent"]
            if memory_stats.get("mean", 0) > 85:
                issues.append("High memory usage detected")
                recommendations.append("Consider implementing more aggressive memory cleanup or increasing available memory")
        
        # GPU analysis
        if "gpu_memory_usage_percent" in metrics:
            gpu_stats = metrics["gpu_memory_usage_percent"]
            if gpu_stats.get("mean", 0) > 90:
                issues.append("High GPU memory usage detected")
                recommendations.append("Consider model quantization or batch size optimization")
        
        # Request performance analysis
        if request_stats.get("total_requests", 0) > 0:
            avg_duration = request_stats.get("avg_duration_ms", 0)
            error_rate = request_stats.get("error_rate", 0)
            
            if avg_duration > 5000:  # 5 seconds
                issues.append("High average response time")
                recommendations.append("Consider implementing response caching or optimizing slow endpoints")
            
            if error_rate > 0.05:  # 5% error rate
                issues.append("High error rate detected")
                recommendations.append("Investigate and fix failing requests")
        
        return {
            "analysis_time": datetime.now().isoformat(),
            "window_minutes": window_minutes,
            "system_health": "healthy" if not issues else "needs_attention",
            "issues": issues,
            "recommendations": recommendations,
            "system_metrics": system_report,
            "request_metrics": request_stats
        }
    
    def get_optimization_suggestions(self) -> List[str]:
        """Get general optimization suggestions"""
        return [
            "Enable response caching for frequently requested content",
            "Implement model lazy loading to reduce memory usage",
            "Use model quantization for large models",
            "Monitor and cleanup expired cache entries regularly",
            "Implement request rate limiting to prevent overload",
            "Use connection pooling for database operations",
            "Enable GPU memory optimization if available",
            "Implement graceful degradation for high load scenarios"
        ]


# Global instances
system_monitor = SystemMonitor()
request_tracker = RequestTracker()
performance_optimizer = PerformanceOptimizer(system_monitor, request_tracker)