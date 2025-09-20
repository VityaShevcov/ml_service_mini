"""
Monitoring and analytics service
"""
import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.models.crud import ModelInteractionCRUD, CreditTransactionCRUD, UserCRUD
from app.models import ModelInteraction, CreditTransaction, User
from app.utils.logging import get_logger


logger = get_logger(__name__)


class MonitoringService:
    """Service for system monitoring and analytics"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system performance metrics"""
        try:
            # CPU and Memory
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # GPU metrics if available
            gpu_metrics = {}
            try:
                import torch
                if torch.cuda.is_available():
                    gpu_memory_allocated = torch.cuda.memory_allocated() / 1024**3  # GB
                    gpu_memory_reserved = torch.cuda.memory_reserved() / 1024**3   # GB
                    gpu_memory_total = torch.cuda.get_device_properties(0).total_memory / 1024**3  # GB
                    
                    gpu_metrics = {
                        "gpu_available": True,
                        "gpu_memory_allocated_gb": round(gpu_memory_allocated, 2),
                        "gpu_memory_reserved_gb": round(gpu_memory_reserved, 2),
                        "gpu_memory_total_gb": round(gpu_memory_total, 2),
                        "gpu_memory_usage_percent": round((gpu_memory_allocated / gpu_memory_total) * 100, 2)
                    }
            except ImportError:
                gpu_metrics = {"gpu_available": False}
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "cpu_percent": cpu_percent,
                "memory": {
                    "total_gb": round(memory.total / 1024**3, 2),
                    "available_gb": round(memory.available / 1024**3, 2),
                    "used_gb": round(memory.used / 1024**3, 2),
                    "percent": memory.percent
                },
                "disk": {
                    "total_gb": round(disk.total / 1024**3, 2),
                    "free_gb": round(disk.free / 1024**3, 2),
                    "used_gb": round(disk.used / 1024**3, 2),
                    "percent": round((disk.used / disk.total) * 100, 2)
                },
                **gpu_metrics
            }
            
        except Exception as e:
            logger.error("get_system_metrics_failed", error=str(e))
            return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}
    
    def get_usage_statistics(self, days: int = 7) -> Dict[str, Any]:
        """Get usage statistics for the last N days"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Model usage statistics
            model_stats = (
                self.db.query(
                    ModelInteraction.model_name,
                    func.count(ModelInteraction.id).label('total_requests'),
                    func.sum(ModelInteraction.credits_charged).label('total_credits'),
                    func.avg(ModelInteraction.processing_time_ms).label('avg_processing_time')
                )
                .filter(ModelInteraction.created_at >= cutoff_date)
                .group_by(ModelInteraction.model_name)
                .all()
            )
            
            # User activity statistics
            user_stats = (
                self.db.query(
                    func.count(func.distinct(ModelInteraction.user_id)).label('active_users'),
                    func.count(ModelInteraction.id).label('total_interactions')
                )
                .filter(ModelInteraction.created_at >= cutoff_date)
                .first()
            )
            
            # Credit statistics
            credit_stats = (
                self.db.query(
                    func.sum(CreditTransaction.amount).label('total_credits_flow'),
                    func.count(CreditTransaction.id).label('total_transactions')
                )
                .filter(CreditTransaction.created_at >= cutoff_date)
                .first()
            )
            
            # Daily breakdown
            daily_stats = (
                self.db.query(
                    func.date(ModelInteraction.created_at).label('date'),
                    func.count(ModelInteraction.id).label('interactions'),
                    func.sum(ModelInteraction.credits_charged).label('credits_used')
                )
                .filter(ModelInteraction.created_at >= cutoff_date)
                .group_by(func.date(ModelInteraction.created_at))
                .order_by(desc(func.date(ModelInteraction.created_at)))
                .all()
            )
            
            return {
                "period_days": days,
                "model_statistics": [
                    {
                        "model_name": stat.model_name,
                        "total_requests": stat.total_requests,
                        "total_credits": stat.total_credits or 0,
                        "avg_processing_time_ms": round(stat.avg_processing_time or 0, 2)
                    }
                    for stat in model_stats
                ],
                "user_activity": {
                    "active_users": user_stats.active_users or 0,
                    "total_interactions": user_stats.total_interactions or 0
                },
                "credit_flow": {
                    "total_credits_flow": credit_stats.total_credits_flow or 0,
                    "total_transactions": credit_stats.total_transactions or 0
                },
                "daily_breakdown": [
                    {
                        "date": stat.date.isoformat() if stat.date else None,
                        "interactions": stat.interactions,
                        "credits_used": stat.credits_used or 0
                    }
                    for stat in daily_stats
                ]
            }
            
        except Exception as e:
            logger.error("get_usage_statistics_failed", error=str(e))
            return {"error": str(e)}
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for the last hour"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=1)
            
            # Recent interactions
            recent_interactions = (
                self.db.query(ModelInteraction)
                .filter(ModelInteraction.created_at >= cutoff_time)
                .all()
            )
            
            if not recent_interactions:
                return {
                    "period": "last_hour",
                    "total_requests": 0,
                    "avg_response_time_ms": 0,
                    "error_rate": 0,
                    "requests_per_minute": 0
                }
            
            # Calculate metrics
            processing_times = [i.processing_time_ms for i in recent_interactions if i.processing_time_ms]
            avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
            
            # Requests per minute
            total_requests = len(recent_interactions)
            requests_per_minute = total_requests / 60  # Last hour = 60 minutes
            
            return {
                "period": "last_hour",
                "total_requests": total_requests,
                "avg_response_time_ms": round(avg_processing_time, 2),
                "requests_per_minute": round(requests_per_minute, 2),
                "model_breakdown": self._get_model_performance_breakdown(recent_interactions)
            }
            
        except Exception as e:
            logger.error("get_performance_metrics_failed", error=str(e))
            return {"error": str(e)}
    
    def _get_model_performance_breakdown(self, interactions: List[ModelInteraction]) -> List[Dict[str, Any]]:
        """Get performance breakdown by model"""
        model_data = {}
        
        for interaction in interactions:
            model = interaction.model_name
            if model not in model_data:
                model_data[model] = {
                    "requests": 0,
                    "processing_times": [],
                    "credits_charged": 0
                }
            
            model_data[model]["requests"] += 1
            model_data[model]["credits_charged"] += interaction.credits_charged
            
            if interaction.processing_time_ms:
                model_data[model]["processing_times"].append(interaction.processing_time_ms)
        
        # Calculate averages
        breakdown = []
        for model, data in model_data.items():
            avg_time = (
                sum(data["processing_times"]) / len(data["processing_times"])
                if data["processing_times"] else 0
            )
            
            breakdown.append({
                "model_name": model,
                "requests": data["requests"],
                "avg_processing_time_ms": round(avg_time, 2),
                "total_credits_charged": data["credits_charged"]
            })
        
        return breakdown
    
    def get_user_analytics(self, limit: int = 10) -> Dict[str, Any]:
        """Get top user analytics"""
        try:
            # Top users by interactions
            top_users_interactions = (
                self.db.query(
                    User.username,
                    func.count(ModelInteraction.id).label('total_interactions'),
                    func.sum(ModelInteraction.credits_charged).label('total_credits_spent')
                )
                .join(ModelInteraction, User.id == ModelInteraction.user_id)
                .group_by(User.id, User.username)
                .order_by(desc(func.count(ModelInteraction.id)))
                .limit(limit)
                .all()
            )
            
            # Top users by credits spent
            top_users_credits = (
                self.db.query(
                    User.username,
                    func.sum(ModelInteraction.credits_charged).label('total_credits_spent'),
                    func.count(ModelInteraction.id).label('total_interactions')
                )
                .join(ModelInteraction, User.id == ModelInteraction.user_id)
                .group_by(User.id, User.username)
                .order_by(desc(func.sum(ModelInteraction.credits_charged)))
                .limit(limit)
                .all()
            )
            
            return {
                "top_users_by_interactions": [
                    {
                        "username": user.username,
                        "total_interactions": user.total_interactions,
                        "total_credits_spent": user.total_credits_spent or 0
                    }
                    for user in top_users_interactions
                ],
                "top_users_by_credits": [
                    {
                        "username": user.username,
                        "total_credits_spent": user.total_credits_spent or 0,
                        "total_interactions": user.total_interactions
                    }
                    for user in top_users_credits
                ]
            }
            
        except Exception as e:
            logger.error("get_user_analytics_failed", error=str(e))
            return {"error": str(e)}
    
    def get_error_analytics(self, hours: int = 24) -> Dict[str, Any]:
        """Get error analytics from logs (simplified version)"""
        try:
            # This would typically analyze log files
            # For now, return a basic structure
            return {
                "period_hours": hours,
                "total_errors": 0,
                "error_types": [],
                "error_rate_per_hour": 0,
                "most_common_errors": []
            }
            
        except Exception as e:
            logger.error("get_error_analytics_failed", error=str(e))
            return {"error": str(e)}
    
    def generate_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive health report"""
        try:
            system_metrics = self.get_system_metrics()
            usage_stats = self.get_usage_statistics(days=1)  # Last 24 hours
            performance_metrics = self.get_performance_metrics()
            
            # Health indicators
            health_status = "healthy"
            warnings = []
            
            # Check system resources
            if system_metrics.get("cpu_percent", 0) > 80:
                warnings.append("High CPU usage detected")
                health_status = "warning"
            
            if system_metrics.get("memory", {}).get("percent", 0) > 85:
                warnings.append("High memory usage detected")
                health_status = "warning"
            
            # Check GPU if available
            gpu_usage = system_metrics.get("gpu_memory_usage_percent", 0)
            if gpu_usage > 90:
                warnings.append("High GPU memory usage detected")
                health_status = "warning"
            
            # Check performance
            avg_response_time = performance_metrics.get("avg_response_time_ms", 0)
            if avg_response_time > 5000:  # 5 seconds
                warnings.append("Slow response times detected")
                health_status = "warning"
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "health_status": health_status,
                "warnings": warnings,
                "system_metrics": system_metrics,
                "usage_statistics": usage_stats,
                "performance_metrics": performance_metrics
            }
            
        except Exception as e:
            logger.error("generate_health_report_failed", error=str(e))
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "health_status": "error",
                "error": str(e)
            }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get system health status"""
        try:
            # Get current system metrics
            system_metrics = self.get_system_metrics()
            
            # Determine health status
            status = "healthy"
            issues = []
            
            # Check memory usage
            memory_usage = system_metrics.get("memory", {}).get("percent", 0)
            if memory_usage > 90:
                issues.append("High memory usage")
                status = "critical"
            elif memory_usage > 80:
                issues.append("Elevated memory usage")
                status = "warning"
            
            # Check CPU usage
            cpu_usage = system_metrics.get("cpu", {}).get("percent", 0)
            if cpu_usage > 95:
                issues.append("High CPU usage")
                status = "critical"
            elif cpu_usage > 80:
                issues.append("Elevated CPU usage")
                status = "warning"
            
            # Check disk usage
            disk_usage = system_metrics.get("disk", {}).get("percent", 0)
            if disk_usage > 95:
                issues.append("High disk usage")
                status = "critical"
            elif disk_usage > 85:
                issues.append("Elevated disk usage")
                status = "warning"
            
            return {
                "status": status,
                "timestamp": datetime.utcnow().isoformat(),
                "uptime_seconds": system_metrics.get("uptime_seconds", 0),
                "issues": issues,
                "components": {
                    "database": "healthy",  # Would check DB connection in real implementation
                    "memory": "normal" if memory_usage < 80 else "high",
                    "cpu": "normal" if cpu_usage < 80 else "high",
                    "disk": "normal" if disk_usage < 85 else "high"
                }
            }
            
        except Exception as e:
            logger.error("get_health_status_failed", error=str(e))
            return {
                "status": "error",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }

    def get_usage_analytics(self, days: int = 7) -> Dict[str, Any]:
        """Get usage analytics (alias for get_usage_statistics)"""
        return self.get_usage_statistics(days)