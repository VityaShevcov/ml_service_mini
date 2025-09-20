"""
Billing API endpoints
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.billing_service import BillingService
from app.api.dependencies import get_current_user
from app.api.schemas import (
    AddCreditsRequest,
    CreditsResponse,
    SuccessResponse
)
from app.models import User
from pydantic import BaseModel


router = APIRouter(prefix="/billing", tags=["billing"])


# Additional schemas for billing
class TransactionResponse(BaseModel):
    """Transaction response"""
    id: int
    amount: int
    transaction_type: str
    description: str
    created_at: str
    
    class Config:
        from_attributes = True


class TransactionHistoryResponse(BaseModel):
    """Transaction history response"""
    transactions: List[TransactionResponse]
    total_count: int


class TransactionSummaryResponse(BaseModel):
    """Transaction summary response"""
    total_transactions: int
    total_charged: int
    total_added: int
    total_refunded: int
    net_spent: int
    current_balance: int


class ChargeCreditsRequest(BaseModel):
    """Charge credits request"""
    amount: int
    description: str = None


class RefundCreditsRequest(BaseModel):
    """Refund credits request"""
    amount: int
    description: str = None


def get_billing_service(db: Session = Depends(get_db)) -> BillingService:
    """Get BillingService instance"""
    return BillingService(db)


@router.get("/balance", response_model=CreditsResponse)
async def get_balance(
    current_user: User = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service)
):
    """Get current user credit balance"""
    balance = billing_service.get_user_balance(current_user.id)
    
    if balance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return CreditsResponse(
        credits=balance,
        message=f"Current balance: {balance} credits"
    )


@router.post("/add", response_model=CreditsResponse)
async def add_credits(
    request: AddCreditsRequest,
    current_user: User = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service)
):
    """Add credits to current user account"""
    success, message, new_balance = billing_service.add_credits(
        user_id=current_user.id,
        amount=request.amount,
        description=f"Manual credit addition: {request.amount} credits"
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    return CreditsResponse(
        credits=new_balance,
        message=message
    )


@router.post("/charge", response_model=CreditsResponse)
async def charge_credits(
    request: ChargeCreditsRequest,
    current_user: User = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service)
):
    """Charge credits from current user account (admin only for testing)"""
    success, message, remaining = billing_service.charge_credits(
        user_id=current_user.id,
        amount=request.amount,
        description=request.description or f"Manual credit charge: {request.amount} credits"
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    return CreditsResponse(
        credits=remaining,
        message=message
    )


@router.post("/refund", response_model=CreditsResponse)
async def refund_credits(
    request: RefundCreditsRequest,
    current_user: User = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service)
):
    """Refund credits to current user account"""
    success, message, new_balance = billing_service.refund_credits(
        user_id=current_user.id,
        amount=request.amount,
        description=request.description or f"Manual credit refund: {request.amount} credits"
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    return CreditsResponse(
        credits=new_balance,
        message=message
    )


@router.get("/transactions", response_model=TransactionHistoryResponse)
async def get_transactions(
    skip: int = Query(0, ge=0, description="Number of transactions to skip"),
    limit: int = Query(50, ge=1, le=100, description="Number of transactions to return"),
    current_user: User = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service)
):
    """Get current user transaction history"""
    transactions = billing_service.get_user_transactions(
        user_id=current_user.id,
        skip=skip,
        limit=limit
    )
    
    transaction_responses = [
        TransactionResponse(
            id=t.id,
            amount=t.amount,
            transaction_type=t.transaction_type,
            description=t.description or "",
            created_at=t.created_at.isoformat()
        )
        for t in transactions
    ]
    
    return TransactionHistoryResponse(
        transactions=transaction_responses,
        total_count=len(transaction_responses)
    )


@router.get("/summary", response_model=TransactionSummaryResponse)
async def get_transaction_summary(
    current_user: User = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service)
):
    """Get current user transaction summary"""
    summary = billing_service.get_transaction_summary(current_user.id)
    
    return TransactionSummaryResponse(**summary)


@router.get("/check/{amount}", response_model=dict)
async def check_sufficient_credits(
    amount: int,
    current_user: User = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service)
):
    """Check if user has sufficient credits for an amount"""
    has_sufficient, message = billing_service.check_sufficient_credits(
        user_id=current_user.id,
        required_amount=amount
    )
    
    return {
        "sufficient": has_sufficient,
        "message": message,
        "current_balance": billing_service.get_user_balance(current_user.id),
        "required_amount": amount
    }


@router.get("/model-cost/{model_name}", response_model=dict)
async def get_model_cost(
    model_name: str,
    billing_service: BillingService = Depends(get_billing_service)
):
    """Get cost for using a specific model"""
    cost = billing_service.get_model_cost(model_name)
    
    return {
        "model_name": model_name,
        "cost": cost,
        "description": f"Using {model_name} costs {cost} credit(s)"
    }