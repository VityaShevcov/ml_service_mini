"""
FastAPI middleware for logging and error handling
"""
import time
import uuid
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.logging import get_logger


logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = str(uuid.uuid4())
        
        # Log request
        start_time = time.time()
        
        logger.info("request_started",
                   request_id=request_id,
                   method=request.method,
                   url=str(request.url),
                   client_ip=request.client.host if request.client else "unknown")
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Log response
            logger.info("request_completed",
                       request_id=request_id,
                       status_code=response.status_code,
                       process_time_ms=int(process_time * 1000))
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            # Log error
            process_time = time.time() - start_time
            
            logger.error("request_failed",
                        request_id=request_id,
                        error=str(e),
                        process_time_ms=int(process_time * 1000))
            
            # Return error response
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": "Internal server error",
                    "request_id": request_id
                },
                headers={"X-Request-ID": request_id}
            )


class AuthLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for authentication event logging"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Log authentication events
        if request.url.path.startswith("/auth/"):
            if request.method == "POST":
                if "login" in request.url.path:
                    if response.status_code == 200:
                        logger.info("auth_login_success", 
                                   client_ip=request.client.host if request.client else "unknown")
                    else:
                        logger.warning("auth_login_failed",
                                     status_code=response.status_code,
                                     client_ip=request.client.host if request.client else "unknown")
                
                elif "register" in request.url.path:
                    if response.status_code == 200:
                        logger.info("auth_register_success",
                                   client_ip=request.client.host if request.client else "unknown")
                    else:
                        logger.warning("auth_register_failed",
                                     status_code=response.status_code,
                                     client_ip=request.client.host if request.client else "unknown")
        
        return response


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware"""
    
    def __init__(self, app, calls_per_minute: int = 60):
        super().__init__(app)
        self.calls_per_minute = calls_per_minute
        self.client_requests = {}  # In production, use Redis or similar
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        
        # Clean old entries (simple cleanup)
        cutoff_time = current_time - 60  # 1 minute ago
        self.client_requests = {
            ip: requests for ip, requests in self.client_requests.items()
            if any(req_time > cutoff_time for req_time in requests)
        }
        
        # Check rate limit for client
        if client_ip in self.client_requests:
            # Filter requests from last minute
            recent_requests = [
                req_time for req_time in self.client_requests[client_ip]
                if req_time > cutoff_time
            ]
            
            if len(recent_requests) >= self.calls_per_minute:
                logger.warning("rate_limit_exceeded",
                             client_ip=client_ip,
                             requests_count=len(recent_requests))
                
                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": "Rate limit exceeded",
                        "detail": f"Maximum {self.calls_per_minute} requests per minute"
                    }
                )
            
            self.client_requests[client_ip] = recent_requests + [current_time]
        else:
            self.client_requests[client_ip] = [current_time]
        
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware for adding security headers"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Add CORS headers if needed
        if request.method == "OPTIONS":
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        
        return response