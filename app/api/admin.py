"""
Administrative API endpoints for system management and analytics
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import io
import csv
import json

from app.database import get_db
from app.services.monitoring_service import MonitoringService
from app.services.billing_service import BillingService
from app.api.dependencies import get_current_user
from app.models import User, ModelInteraction, CreditTransaction
from app.models.crud import UserCRUD, ModelInteractionCRUD, CreditTransactionCRUD
from app.utils.logging import get_logger


router = APIRouter(prefix="/admin", tags=["admin"])
logger = get_logger(__name__)


def get_monitoring_service(db: Session = Depends(get_db)) -> MonitoringService:
    """Get MonitoringService instance"""
    return MonitoringService(db)


def get_billing_service(db: Session = Depends(get_db)) -> BillingService:
    """Get BillingService instance"""
    return BillingService(db)


def verify_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Verify that current user has admin privileges"""
    # For now, check if user is admin by username or email
    # In production, you'd have proper role-based access control
    admin_users = ["admin", "administrator", "admin@example.com"]
    
    if current_user.username not in admin_users and current_user.email not in admin_users:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    return current_user


@router.get("/dashboard")
async def get_admin_dashboard(
    days: int = Query(7, ge=1, le=90, description="Number of days for analytics"),
    admin_user: User = Depends(verify_admin_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
    db: Session = Depends(get_db)
):
    """Get comprehensive admin dashboard data"""
    try:
        # System health and metrics
        health_status = monitoring_service.get_health_status()
        system_metrics = monitoring_service.get_system_metrics()
        
        # Usage analytics
        usage_analytics = monitoring_service.get_usage_analytics(days)
        
        # User statistics
        total_users = db.query(User).count()
        active_users_count = len(set(
            interaction.user_id for interaction in 
            ModelInteractionCRUD.get_recent(db, days=days)
        ))
        
        # Credit statistics
        total_credits_added = db.query(CreditTransaction).filter(
            CreditTransaction.transaction_type == "add",
            CreditTransaction.created_at >= datetime.utcnow() - timedelta(days=days)
        ).count()
        
        total_credits_spent = db.query(CreditTransaction).filter(
            CreditTransaction.transaction_type == "charge",
            CreditTransaction.created_at >= datetime.utcnow() - timedelta(days=days)
        ).count()
        
        # Recent activity
        recent_interactions = ModelInteractionCRUD.get_recent(db, limit=10)
        recent_users = UserCRUD.get_recent(db, limit=10)
        
        return {
            "success": True,
            "dashboard": {
                "period_days": days,
                "system": {
                    "health": health_status,
                    "metrics": system_metrics
                },
                "usage": usage_analytics,
                "users": {
                    "total_users": total_users,
                    "active_users": active_users_count,
                    "activity_rate": round((active_users_count / total_users * 100), 2) if total_users > 0 else 0,
                    "recent_registrations": len(recent_users)
                },
                "credits": {
                    "total_added": total_credits_added,
                    "total_spent": total_credits_spent,
                    "net_flow": total_credits_added - total_credits_spent
                },
                "recent_activity": {
                    "interactions": [
                        {
                            "id": interaction.id,
                            "user_id": interaction.user_id,
                            "model": interaction.model_name,
                            "credits": interaction.credits_charged,
                            "timestamp": interaction.created_at.isoformat()
                        }
                        for interaction in recent_interactions
                    ],
                    "new_users": [
                        {
                            "id": user.id,
                            "username": user.username,
                            "email": user.email,
                            "credits": user.credits,
                            "created_at": user.created_at.isoformat()
                        }
                        for user in recent_users
                    ]
                }
            }
        }
        
    except Exception as e:
        logger.error("admin_dashboard_failed", admin_id=admin_user.id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load admin dashboard"
        )


@router.get("/users")
async def get_users_list(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by username or email"),
    admin_user: User = Depends(verify_admin_user),
    db: Session = Depends(get_db)
):
    """Get paginated list of users with search"""
    try:
        skip = (page - 1) * page_size
        
        # Build query
        query = db.query(User)
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (User.username.ilike(search_term)) | 
                (User.email.ilike(search_term))
            )
        
        # Get total count
        total_count = query.count()
        
        # Get users with pagination
        users = query.offset(skip).limit(page_size).all()
        
        # Format response
        users_data = []
        for user in users:
            # Get user statistics
            user_interactions = db.query(ModelInteraction).filter(
                ModelInteraction.user_id == user.id
            ).count()
            
            total_spent = sum(
                interaction.credits_charged for interaction in
                db.query(ModelInteraction).filter(
                    ModelInteraction.user_id == user.id
                ).all()
            )
            
            users_data.append({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "credits": user.credits,
                "created_at": user.created_at.isoformat(),
            "is_active": True,
                "statistics": {
                    "total_interactions": user_interactions,
                    "total_credits_spent": total_spent
                }
            })
        
        return {
            "success": True,
            "users": users_data,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_count,
                "pages": (total_count + page_size - 1) // page_size
            },
            "search": search
        }
        
    except Exception as e:
        logger.error("admin_users_list_failed", admin_id=admin_user.id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get users list"
        )


@router.get("/users/{user_id}")
async def get_user_details(
    user_id: int,
    admin_user: User = Depends(verify_admin_user),
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific user"""
    try:
        # Get user
        user = UserCRUD.get(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get user interactions
        interactions = ModelInteractionCRUD.get_by_user(db, user_id, skip=0, limit=50)
        
        # Get credit transactions
        credit_transactions = CreditTransactionCRUD.get_by_user(db, user_id, skip=0, limit=50)
        
        # Calculate statistics
        total_interactions = len(interactions)
        total_credits_spent = sum(i.credits_charged for i in interactions)
        
        model_usage = {}
        for interaction in interactions:
            model = interaction.model_name
            model_usage[model] = model_usage.get(model, 0) + 1
        
        return {
            "success": True,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "credits": user.credits,
                "created_at": user.created_at.isoformat(),
                "is_active": True
            },
            "statistics": {
                "total_interactions": total_interactions,
                "total_credits_spent": total_credits_spent,
                "model_usage": model_usage
            },
            "recent_interactions": [
                {
                    "id": interaction.id,
                    "model": interaction.model_name,
                    "credits": interaction.credits_charged,
                    "processing_time_ms": interaction.processing_time_ms,
                    "timestamp": interaction.created_at.isoformat()
                }
                for interaction in interactions[:10]
            ],
            "credit_transactions": [
                {
                    "id": transaction.id,
                    "type": transaction.transaction_type,
                    "amount": transaction.amount,
                    "description": transaction.description,
                    "timestamp": transaction.created_at.isoformat()
                }
                for transaction in credit_transactions[:10]
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("admin_user_details_failed", admin_id=admin_user.id, user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user details"
        )


@router.post("/users/{user_id}/credits")
async def adjust_user_credits(
    user_id: int,
    amount: int,
    description: str = "Admin adjustment",
    admin_user: User = Depends(verify_admin_user),
    billing_service: BillingService = Depends(get_billing_service)
):
    """Adjust user credits (admin only)"""
    try:
        if amount == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Amount cannot be zero"
            )
        
        # Add or charge credits
        if amount > 0:
            success, message, new_balance = billing_service.add_credits(
                user_id=user_id,
                amount=amount,
                description=f"Admin credit adjustment: {description}"
            )
        else:
            success, message, new_balance = billing_service.charge_credits(
                user_id=user_id,
                amount=abs(amount),
                description=f"Admin credit deduction: {description}"
            )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        logger.info("admin_credit_adjustment", 
                   admin_id=admin_user.id, 
                   user_id=user_id, 
                   amount=amount,
                   new_balance=new_balance)
        
        return {
            "success": True,
            "message": message,
            "new_balance": new_balance,
            "adjustment": amount
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("admin_credit_adjustment_failed", 
                    admin_id=admin_user.id, 
                    user_id=user_id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to adjust user credits"
        )


@router.get("/reports/usage")
async def generate_usage_report(
    days: int = Query(30, ge=1, le=365, description="Number of days for report"),
    format: str = Query("json", regex="^(json|csv)$", description="Report format"),
    admin_user: User = Depends(verify_admin_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service)
):
    """Generate detailed usage report"""
    try:
        # Get comprehensive analytics
        analytics = monitoring_service.get_usage_analytics(days)
        
        if format == "json":
            return {
                "success": True,
                "report": analytics,
                "generated_at": datetime.utcnow().isoformat(),
                "period_days": days
            }
        
        elif format == "csv":
            # Generate CSV report
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write headers and data
            writer.writerow(["Report Type", "Usage Report"])
            writer.writerow(["Generated At", datetime.utcnow().isoformat()])
            writer.writerow(["Period (days)", days])
            writer.writerow([])
            
            # Model usage
            writer.writerow(["Model Usage"])
            writer.writerow(["Model", "Interactions", "Credits Used", "Avg Time (ms)"])
            
            models_data = analytics.get("models", {}).get("by_model", {})
            for model_name, stats in models_data.items():
                writer.writerow([
                    model_name,
                    stats.get("count", 0),
                    stats.get("credits_used", 0),
                    stats.get("avg_processing_time_ms", 0)
                ])
            
            csv_content = output.getvalue()
            output.close()
            
            return {
                "success": True,
                "format": "csv",
                "content": csv_content,
                "filename": f"usage_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        
    except Exception as e:
        logger.error("admin_usage_report_failed", admin_id=admin_user.id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate usage report"
        )


@router.get("/reports/financial")
async def generate_financial_report(
    days: int = Query(30, ge=1, le=365, description="Number of days for report"),
    admin_user: User = Depends(verify_admin_user),
    db: Session = Depends(get_db)
):
    """Generate financial report showing credit flows"""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get all credit transactions in period
        transactions = db.query(CreditTransaction).filter(
            CreditTransaction.created_at >= start_date,
            CreditTransaction.created_at <= end_date
        ).all()
        
        # Analyze transactions
        credits_added = sum(t.amount for t in transactions if t.transaction_type == "add")
        credits_spent = sum(abs(t.amount) for t in transactions if t.transaction_type == "charge")
        
        # Daily breakdown
        daily_stats = {}
        for transaction in transactions:
            date_key = transaction.created_at.date().isoformat()
            if date_key not in daily_stats:
                daily_stats[date_key] = {"added": 0, "spent": 0, "transactions": 0}
            
            daily_stats[date_key]["transactions"] += 1
            if transaction.transaction_type == "add":
                daily_stats[date_key]["added"] += transaction.amount
            else:
                daily_stats[date_key]["spent"] += abs(transaction.amount)
        
        # User spending analysis
        user_spending = {}
        for transaction in transactions:
            if transaction.transaction_type == "charge":
                user_id = transaction.user_id
                user_spending[user_id] = user_spending.get(user_id, 0) + abs(transaction.amount)
        
        # Top spenders
        top_spenders = sorted(user_spending.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "success": True,
            "report": {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "days": days
                },
                "summary": {
                    "total_credits_added": credits_added,
                    "total_credits_spent": credits_spent,
                    "net_flow": credits_added - credits_spent,
                    "total_transactions": len(transactions)
                },
                "daily_breakdown": [
                    {
                        "date": date,
                        "credits_added": stats["added"],
                        "credits_spent": stats["spent"],
                        "net_flow": stats["added"] - stats["spent"],
                        "transactions": stats["transactions"]
                    }
                    for date, stats in sorted(daily_stats.items())
                ],
                "top_spenders": [
                    {
                        "user_id": user_id,
                        "credits_spent": amount
                    }
                    for user_id, amount in top_spenders
                ]
            }
        }
        
    except Exception as e:
        logger.error("admin_financial_report_failed", admin_id=admin_user.id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate financial report"
        )


@router.get("/system/status")
async def get_system_status(
    admin_user: User = Depends(verify_admin_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service)
):
    """Get detailed system status for admin"""
    try:
        # Get comprehensive system information
        health_status = monitoring_service.get_health_status()
        system_metrics = monitoring_service.get_system_metrics()
        performance_metrics = monitoring_service.get_performance_metrics()
        
        return {
            "success": True,
            "system_status": {
                "health": health_status,
                "metrics": system_metrics,
                "performance": performance_metrics,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
    except Exception as e:
        logger.error("admin_system_status_failed", admin_id=admin_user.id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system status"
        )