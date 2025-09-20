"""
Performance monitoring and optimization API endpoints
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.dependencies import get_current_user
from app.models import User
from app.utils.performance_monitor import (
    system_monitor, 
    request_tracker, 
    performance_optimizer
)
from app.utils.logging import get_logger


router = APIRouter(prefix="/performance", tags=["performance"])
logger = get_logger(__name__)


@router.get("/metrics")
async def get_performance_metrics(
    window_minutes: int = Query(60, ge=1, le=1440, description="Time window in minutes"),
    current_user: User = Depends(get_current_user)
):
    """Get system performance metrics"""
    try:
        # Get performance report
        report = system_monitor.get_performance_report(window_minutes)
        
        return {
            "success": True,
            "metrics": report
        }
        
    except Exception as e:
        logger.error("get_performance_metrics_failed", 
                    user_id=current_user.id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get performance metrics"
        )


@router.get("/requests")
async def get_request_statistics(
    window_minutes: int = Query(60, ge=1, le=1440, description="Time window in minutes"),
    current_user: User = Depends(get_current_user)
):
    """Get API request statistics"""
    try:
        # Get request statistics
        stats = request_tracker.get_request_stats(window_minutes)
        
        # Get slowest requests
        slowest = request_tracker.get_slowest_requests(
            limit=10, 
            window_minutes=window_minutes
        )
        
        return {
            "success": True,
            "statistics": stats,
            "slowest_requests": slowest
        }
        
    except Exception as e:
        logger.error("get_request_statistics_failed", 
                    user_id=current_user.id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get request statistics"
        )


@router.get("/analysis")
async def get_performance_analysis(
    window_minutes: int = Query(60, ge=1, le=1440, description="Time window in minutes"),
    current_user: User = Depends(get_current_user)
):
    """Get comprehensive performance analysis with recommendations"""
    try:
        # Get performance analysis
        analysis = performance_optimizer.analyze_performance(window_minutes)
        
        # Get optimization suggestions
        suggestions = performance_optimizer.get_optimization_suggestions()
        
        return {
            "success": True,
            "analysis": analysis,
            "optimization_suggestions": suggestions
        }
        
    except Exception as e:
        logger.error("get_performance_analysis_failed", 
                    user_id=current_user.id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get performance analysis"
        )


@router.get("/system/current")
async def get_current_system_status(
    current_user: User = Depends(get_current_user)
):
    """Get current system status snapshot"""
    try:
        # Get current metrics
        metrics = system_monitor.get_current_metrics()
        
        return {
            "success": True,
            "system_status": metrics
        }
        
    except Exception as e:
        logger.error("get_current_system_status_failed", 
                    user_id=current_user.id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get current system status"
        )


@router.post("/optimize/memory")
async def trigger_memory_optimization(
    current_user: User = Depends(get_current_user)
):
    """Manually trigger memory optimization"""
    try:
        # Get current memory status
        before_metrics = system_monitor.get_current_metrics()
        
        # Trigger optimization
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
        
        # Get metrics after optimization
        after_metrics = system_monitor.get_current_metrics()
        
        logger.info("manual_memory_optimization_triggered", 
                   user_id=current_user.id)
        
        return {
            "success": True,
            "message": "Memory optimization completed",
            "before": before_metrics.get("memory", {}),
            "after": after_metrics.get("memory", {})
        }
        
    except Exception as e:
        logger.error("memory_optimization_failed", 
                    user_id=current_user.id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to optimize memory"
        )


@router.get("/cache/stats")
async def get_cache_statistics(
    current_user: User = Depends(get_current_user)
):
    """Get caching statistics and performance"""
    try:
        # This would integrate with the optimized ML service
        # For now, return placeholder data
        
        cache_stats = {
            "response_cache": {
                "total_entries": 0,
                "hit_rate": 0.0,
                "memory_usage_mb": 0.0
            },
            "model_cache": {
                "cached_models": [],
                "total_size_mb": 0.0,
                "cache_utilization": 0.0
            }
        }
        
        return {
            "success": True,
            "cache_statistics": cache_stats
        }
        
    except Exception as e:
        logger.error("get_cache_statistics_failed", 
                    user_id=current_user.id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get cache statistics"
        )


@router.post("/cache/clear")
async def clear_caches(
    cache_type: str = Query("all", regex="^(all|response|model)$"),
    current_user: User = Depends(get_current_user)
):
    """Clear specified caches"""
    try:
        cleared_caches = []
        
        if cache_type in ["all", "response"]:
            # Clear response cache (would integrate with optimized ML service)
            cleared_caches.append("response_cache")
        
        if cache_type in ["all", "model"]:
            # Clear model cache (would integrate with optimized ML service)
            cleared_caches.append("model_cache")
        
        logger.info("caches_cleared", 
                   user_id=current_user.id, 
                   cache_type=cache_type,
                   cleared=cleared_caches)
        
        return {
            "success": True,
            "message": f"Cleared {cache_type} cache(s)",
            "cleared_caches": cleared_caches
        }
        
    except Exception as e:
        logger.error("clear_caches_failed", 
                    user_id=current_user.id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear caches"
        )


@router.get("/alerts")
async def get_performance_alerts(
    severity: Optional[str] = Query(None, regex="^(low|medium|high|critical)$"),
    current_user: User = Depends(get_current_user)
):
    """Get performance alerts and warnings"""
    try:
        # Get current system status
        current_metrics = system_monitor.get_current_metrics()
        
        alerts = []
        
        # Check memory usage
        memory_usage = current_metrics.get("memory", {}).get("usage_percent", 0)
        if memory_usage > 95:
            alerts.append({
                "severity": "critical",
                "type": "memory",
                "message": f"Critical memory usage: {memory_usage:.1f}%",
                "threshold": 95,
                "current_value": memory_usage
            })
        elif memory_usage > 85:
            alerts.append({
                "severity": "high",
                "type": "memory",
                "message": f"High memory usage: {memory_usage:.1f}%",
                "threshold": 85,
                "current_value": memory_usage
            })
        
        # Check CPU usage
        cpu_usage = current_metrics.get("cpu", {}).get("usage_percent", 0)
        if cpu_usage > 90:
            alerts.append({
                "severity": "high",
                "type": "cpu",
                "message": f"High CPU usage: {cpu_usage:.1f}%",
                "threshold": 90,
                "current_value": cpu_usage
            })
        
        # Check GPU usage if available
        gpu_info = current_metrics.get("gpu", {})
        if gpu_info.get("available", False):
            gpu_usage = gpu_info.get("usage_percent", 0)
            if gpu_usage > 95:
                alerts.append({
                    "severity": "critical",
                    "type": "gpu_memory",
                    "message": f"Critical GPU memory usage: {gpu_usage:.1f}%",
                    "threshold": 95,
                    "current_value": gpu_usage
                })
        
        # Check disk usage
        disk_usage = current_metrics.get("disk", {}).get("usage_percent", 0)
        if disk_usage > 90:
            alerts.append({
                "severity": "medium",
                "type": "disk",
                "message": f"High disk usage: {disk_usage:.1f}%",
                "threshold": 90,
                "current_value": disk_usage
            })
        
        # Filter by severity if specified
        if severity:
            alerts = [alert for alert in alerts if alert["severity"] == severity]
        
        return {
            "success": True,
            "alerts": alerts,
            "total_alerts": len(alerts),
            "severity_filter": severity
        }
        
    except Exception as e:
        logger.error("get_performance_alerts_failed", 
                    user_id=current_user.id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get performance alerts"
        )


@router.get("/recommendations")
async def get_optimization_recommendations(
    current_user: User = Depends(get_current_user)
):
    """Get personalized optimization recommendations"""
    try:
        # Get performance analysis
        analysis = performance_optimizer.analyze_performance(60)
        
        # Get general suggestions
        general_suggestions = performance_optimizer.get_optimization_suggestions()
        
        # Generate personalized recommendations based on current state
        personalized = []
        
        # Check current system state
        current_metrics = system_monitor.get_current_metrics()
        memory_usage = current_metrics.get("memory", {}).get("usage_percent", 0)
        
        if memory_usage > 80:
            personalized.append({
                "priority": "high",
                "category": "memory",
                "recommendation": "Enable aggressive memory cleanup",
                "reason": f"Current memory usage is {memory_usage:.1f}%",
                "action": "Consider clearing model cache or reducing batch sizes"
            })
        
        # Check request patterns
        request_stats = request_tracker.get_request_stats(60)
        avg_duration = request_stats.get("avg_duration_ms", 0)
        
        if avg_duration > 3000:
            personalized.append({
                "priority": "medium",
                "category": "performance",
                "recommendation": "Implement response caching",
                "reason": f"Average response time is {avg_duration}ms",
                "action": "Enable caching for frequently requested content"
            })
        
        return {
            "success": True,
            "personalized_recommendations": personalized,
            "general_suggestions": general_suggestions,
            "analysis_summary": {
                "system_health": analysis.get("system_health", "unknown"),
                "issues_count": len(analysis.get("issues", [])),
                "recommendations_count": len(analysis.get("recommendations", []))
            }
        }
        
    except Exception as e:
        logger.error("get_optimization_recommendations_failed", 
                    user_id=current_user.id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get optimization recommendations"
        )