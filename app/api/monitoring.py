"""
Monitoring API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.monitoring_service import MonitoringService
from app.api.dependencies import get_current_user
from app.models import User
from app.utils.logging import get_logger


router = APIRouter(prefix="/monitoring", tags=["monitoring"])
logger = get_logger(__name__)


def get_monitoring_service(db: Session = Depends(get_db)) -> MonitoringService:
    """Get MonitoringService instance"""
    return MonitoringService(db)


@router.get("/system")
async def get_system_metrics(
    current_user: User = Depends(get_current_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service)
):
    """Get current system metrics"""
    return monitoring_service.get_system_metrics()


@router.get("/usage")
async def get_usage_statistics(
    days: int = Query(7, ge=1, le=30, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service)
):
    """Get usage statistics"""
    return monitoring_service.get_usage_statistics(days)


@router.get("/performance")
async def get_performance_metrics(
    current_user: User = Depends(get_current_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service)
):
    """Get performance metrics"""
    return monitoring_service.get_performance_metrics()


@router.get("/users")
async def get_user_analytics(
    limit: int = Query(10, ge=1, le=50, description="Number of top users to return"),
    current_user: User = Depends(get_current_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service)
):
    """Get user analytics"""
    return monitoring_service.get_user_analytics(limit)


@router.get("/health")
async def get_health_report(
    monitoring_service: MonitoringService = Depends(get_monitoring_service)
):
    """Get comprehensive health report"""
    return monitoring_service.generate_health_report()


@router.get("/metrics")
async def get_monitoring_metrics(
    current_user: User = Depends(get_current_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service)
):
    """Get system monitoring metrics"""
    try:
        metrics = monitoring_service.get_system_metrics()
        return {
            "success": True,
            "metrics": metrics
        }
        
    except Exception as e:
        logger.error("get_monitoring_metrics_failed", user_id=current_user.id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get monitoring metrics"
        )


@router.get("/analytics")
async def get_monitoring_analytics(
    days: int = Query(7, ge=1, le=30, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service)
):
    """Get usage analytics"""
    try:
        analytics = monitoring_service.get_usage_analytics(days)
        return {
            "success": True,
            "analytics": analytics
        }
        
    except Exception as e:
        logger.error("get_monitoring_analytics_failed", user_id=current_user.id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get usage analytics"
        )