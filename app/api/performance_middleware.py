"""
Performance monitoring middleware for FastAPI
"""
import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.performance_monitor import request_tracker, system_monitor
from app.utils.logging import get_logger


logger = get_logger(__name__)


class PerformanceMiddleware(BaseHTTPMiddleware):
    """Middleware to track request performance metrics"""
    
    def __init__(self, app, enable_detailed_logging: bool = False):
        super().__init__(app)
        self.enable_detailed_logging = enable_detailed_logging
        
        # Start system monitoring if not already started
        if not system_monitor.monitoring:
            system_monitor.start_monitoring()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and track performance metrics"""
        start_time = time.time()
        
        # Extract request info
        method = request.method
        path = request.url.path
        user_id = None
        
        # Try to get user ID from request state (set by auth middleware)
        if hasattr(request.state, 'user_id'):
            user_id = request.state.user_id
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Record metrics
            request_tracker.record_request(
                endpoint=path,
                method=method,
                duration_ms=duration_ms,
                status_code=response.status_code,
                user_id=user_id
            )
            
            # Add performance headers
            response.headers["X-Response-Time"] = f"{duration_ms}ms"
            
            # Log slow requests
            if duration_ms > 5000:  # 5 seconds
                logger.warning("slow_request_detected",
                             endpoint=path,
                             method=method,
                             duration_ms=duration_ms,
                             status_code=response.status_code,
                             user_id=user_id)
            
            # Detailed logging if enabled
            if self.enable_detailed_logging:
                logger.info("request_completed",
                           endpoint=path,
                           method=method,
                           duration_ms=duration_ms,
                           status_code=response.status_code,
                           user_id=user_id)
            
            return response
            
        except Exception as e:
            # Calculate duration for failed requests
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Record error metrics
            request_tracker.record_request(
                endpoint=path,
                method=method,
                duration_ms=duration_ms,
                status_code=500,
                user_id=user_id
            )
            
            logger.error("request_failed",
                        endpoint=path,
                        method=method,
                        duration_ms=duration_ms,
                        error=str(e),
                        user_id=user_id)
            
            # Re-raise the exception
            raise


class MemoryMonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware to monitor memory usage and trigger cleanup"""
    
    def __init__(self, app, memory_threshold: float = 0.9):
        super().__init__(app)
        self.memory_threshold = memory_threshold
        self.cleanup_in_progress = False
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Monitor memory and trigger cleanup if needed"""
        
        # Check memory before processing request
        current_metrics = system_monitor.get_current_metrics()
        
        # Check if memory cleanup is needed
        memory_usage = current_metrics.get("memory", {}).get("usage_percent", 0)
        gpu_usage = current_metrics.get("gpu", {}).get("usage_percent", 0)
        
        if (memory_usage > self.memory_threshold * 100 or 
            gpu_usage > self.memory_threshold * 100) and not self.cleanup_in_progress:
            
            logger.warning("high_memory_usage_detected",
                          memory_percent=memory_usage,
                          gpu_percent=gpu_usage,
                          threshold=self.memory_threshold * 100)
            
            # Trigger async cleanup (don't block request)
            self._trigger_async_cleanup()
        
        # Process request normally
        response = await call_next(request)
        
        return response
    
    def _trigger_async_cleanup(self):
        """Trigger asynchronous memory cleanup"""
        if self.cleanup_in_progress:
            return
        
        import threading
        
        def cleanup_worker():
            try:
                self.cleanup_in_progress = True
                logger.info("starting_memory_cleanup")
                
                # Import here to avoid circular imports
                from app.ml.optimized_ml_service import OptimizedMLService
                
                # Trigger garbage collection
                import gc
                gc.collect()
                
                # Clear GPU cache if available
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        torch.cuda.synchronize()
                except ImportError:
                    pass
                
                logger.info("memory_cleanup_completed")
                
            except Exception as e:
                logger.error("memory_cleanup_failed", error=str(e))
            finally:
                self.cleanup_in_progress = False
        
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware"""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts = {}
        self.window_start = {}
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply rate limiting based on client IP"""
        client_ip = self._get_client_ip(request)
        current_time = time.time()
        
        # Clean old entries
        self._cleanup_old_entries(current_time)
        
        # Check rate limit
        if self._is_rate_limited(client_ip, current_time):
            logger.warning("rate_limit_exceeded", client_ip=client_ip)
            
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later."
            )
        
        # Record request
        self._record_request(client_ip, current_time)
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        remaining = max(0, self.requests_per_minute - self.request_counts.get(client_ip, 0))
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request"""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        return request.client.host if request.client else "unknown"
    
    def _is_rate_limited(self, client_ip: str, current_time: float) -> bool:
        """Check if client is rate limited"""
        if client_ip not in self.request_counts:
            return False
        
        # Check if we're in the same minute window
        window_start = self.window_start.get(client_ip, 0)
        if current_time - window_start >= 60:  # New minute window
            return False
        
        return self.request_counts[client_ip] >= self.requests_per_minute
    
    def _record_request(self, client_ip: str, current_time: float):
        """Record a request for rate limiting"""
        # Check if we need to start a new window
        if (client_ip not in self.window_start or 
            current_time - self.window_start[client_ip] >= 60):
            self.window_start[client_ip] = current_time
            self.request_counts[client_ip] = 1
        else:
            self.request_counts[client_ip] = self.request_counts.get(client_ip, 0) + 1
    
    def _cleanup_old_entries(self, current_time: float):
        """Clean up old rate limiting entries"""
        expired_ips = []
        
        for client_ip, window_start in self.window_start.items():
            if current_time - window_start >= 120:  # Keep for 2 minutes
                expired_ips.append(client_ip)
        
        for ip in expired_ips:
            self.request_counts.pop(ip, None)
            self.window_start.pop(ip, None)


class HealthCheckMiddleware(BaseHTTPMiddleware):
    """Middleware to handle health checks and system status"""
    
    def __init__(self, app):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle health check requests"""
        
        # Quick health check endpoint
        if request.url.path == "/health":
            from fastapi.responses import JSONResponse
            
            try:
                # Get basic system metrics
                metrics = system_monitor.get_current_metrics()
                
                # Determine health status
                memory_usage = metrics.get("memory", {}).get("usage_percent", 0)
                cpu_usage = metrics.get("cpu", {}).get("usage_percent", 0)
                
                if memory_usage > 95 or cpu_usage > 95:
                    status = "unhealthy"
                elif memory_usage > 85 or cpu_usage > 85:
                    status = "degraded"
                else:
                    status = "healthy"
                
                return JSONResponse({
                    "status": status,
                    "timestamp": metrics.get("timestamp"),
                    "memory_usage_percent": memory_usage,
                    "cpu_usage_percent": cpu_usage
                })
                
            except Exception as e:
                logger.error("health_check_failed", error=str(e))
                return JSONResponse({
                    "status": "error",
                    "error": str(e)
                }, status_code=500)
        
        # Process normal requests
        return await call_next(request)