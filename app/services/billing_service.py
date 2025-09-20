"""
Billing service for credit management and transactions
"""
from datetime import datetime
from typing import Tuple, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.models import User, CreditTransaction
from app.models.crud import UserCRUD, CreditTransactionCRUD
from app.utils.logging import get_logger, log_billing_transaction
from app.utils.transactions import atomic_transaction
from config import settings


logger = get_logger(__name__)


class BillingService:
    """Service for billing operations and credit management"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def charge_credits(
        self, 
        user_id: int, 
        amount: int, 
        description: str = None
    ) -> Tuple[bool, str, int]:
        """
        Charge credits from user account
        Returns (success, message, remaining_credits)
        """
        try:
            with atomic_transaction(self.db):
                user = UserCRUD.get_by_id(self.db, user_id)
                if not user:
                    return False, "User not found", 0
                
                # Check if user has enough credits
                if user.credits < amount:
                    log_billing_transaction(
                        logger, user_id, "charge_failed", -amount, 
                        reason="insufficient_credits", 
                        current_balance=user.credits
                    )
                    return False, f"Insufficient credits. You have {user.credits}, need {amount}", user.credits
                
                # Calculate new balance
                new_balance = user.credits - amount
                
                # Update user credits
                success = UserCRUD.update_credits(self.db, user_id, new_balance)
                if not success:
                    return False, "Failed to update user credits", user.credits
                
                # Log transaction
                CreditTransactionCRUD.create(
                    db=self.db,
                    user_id=user_id,
                    amount=-amount,  # Negative for charge
                    transaction_type="charge",
                    description=description or f"Credit charge: {amount} credits"
                )
                
                log_billing_transaction(
                    logger, user_id, "charge", -amount,
                    new_balance=new_balance,
                    description=description
                )
                
                return True, f"Successfully charged {amount} credits", new_balance
            
        except SQLAlchemyError as e:
            logger.error("billing_charge_failed", error=str(e), user_id=user_id, amount=amount)
            return False, "Database error during charge operation", 0
        except Exception as e:
            logger.error("billing_charge_error", error=str(e), user_id=user_id, amount=amount)
            return False, "Unexpected error during charge operation", 0
    
    def add_credits(
        self, 
        user_id: int, 
        amount: int, 
        description: str = None
    ) -> Tuple[bool, str, int]:
        """
        Add credits to user account
        Returns (success, message, new_balance)
        """
        try:
            if amount <= 0:
                return False, "Amount must be positive", 0
            
            # Get current user
            user = UserCRUD.get_by_id(self.db, user_id)
            if not user:
                return False, "User not found", 0
            
            # Calculate new balance
            new_balance = user.credits + amount
            
            # Update user credits
            success = UserCRUD.update_credits(self.db, user_id, new_balance)
            if not success:
                return False, "Failed to update user credits", user.credits
            
            # Log transaction
            CreditTransactionCRUD.create(
                db=self.db,
                user_id=user_id,
                amount=amount,  # Positive for add
                transaction_type="add",
                description=description or f"Credit addition: {amount} credits"
            )
            
            log_billing_transaction(
                logger, user_id, "add", amount,
                new_balance=new_balance,
                description=description
            )
            
            return True, f"Successfully added {amount} credits", new_balance
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error("billing_add_failed", error=str(e), user_id=user_id, amount=amount)
            return False, "Database error during add operation", 0
        except Exception as e:
            self.db.rollback()
            logger.error("billing_add_error", error=str(e), user_id=user_id, amount=amount)
            return False, "Unexpected error during add operation", 0
    
    def refund_credits(
        self, 
        user_id: int, 
        amount: int, 
        description: str = None
    ) -> Tuple[bool, str, int]:
        """
        Refund credits to user account (e.g., when operation fails)
        Returns (success, message, new_balance)
        """
        try:
            if amount <= 0:
                return False, "Refund amount must be positive", 0
            
            # Get current user
            user = UserCRUD.get_by_id(self.db, user_id)
            if not user:
                return False, "User not found", 0
            
            # Calculate new balance
            new_balance = user.credits + amount
            
            # Update user credits
            success = UserCRUD.update_credits(self.db, user_id, new_balance)
            if not success:
                return False, "Failed to update user credits", user.credits
            
            # Log transaction
            CreditTransactionCRUD.create(
                db=self.db,
                user_id=user_id,
                amount=amount,  # Positive for refund
                transaction_type="refund",
                description=description or f"Credit refund: {amount} credits"
            )
            
            log_billing_transaction(
                logger, user_id, "refund", amount,
                new_balance=new_balance,
                description=description
            )
            
            return True, f"Successfully refunded {amount} credits", new_balance
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error("billing_refund_failed", error=str(e), user_id=user_id, amount=amount)
            return False, "Database error during refund operation", 0
        except Exception as e:
            self.db.rollback()
            logger.error("billing_refund_error", error=str(e), user_id=user_id, amount=amount)
            return False, "Unexpected error during refund operation", 0
    
    def get_user_balance(self, user_id: int) -> Optional[int]:
        """
        Get current user credit balance
        Returns balance or None if user not found
        """
        try:
            user = UserCRUD.get_by_id(self.db, user_id)
            return user.credits if user else None
            
        except Exception as e:
            logger.error("get_balance_failed", error=str(e), user_id=user_id)
            return None
    
    def get_user_transactions(
        self, 
        user_id: int, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[CreditTransaction]:
        """
        Get user transaction history
        Returns list of transactions
        """
        try:
            return CreditTransactionCRUD.get_by_user(self.db, user_id, skip, limit)
            
        except Exception as e:
            logger.error("get_transactions_failed", error=str(e), user_id=user_id)
            return []
    
    def get_transaction_summary(self, user_id: int) -> dict:
        """
        Get transaction summary for user
        Returns summary statistics
        """
        try:
            transactions = CreditTransactionCRUD.get_by_user(self.db, user_id, 0, 1000)
            
            total_charged = sum(abs(t.amount) for t in transactions if t.transaction_type == "charge")
            total_added = sum(t.amount for t in transactions if t.transaction_type == "add")
            total_refunded = sum(t.amount for t in transactions if t.transaction_type == "refund")
            
            return {
                "total_transactions": len(transactions),
                "total_charged": total_charged,
                "total_added": total_added,
                "total_refunded": total_refunded,
                "net_spent": total_charged - total_refunded,
                "current_balance": self.get_user_balance(user_id) or 0
            }
            
        except Exception as e:
            logger.error("get_summary_failed", error=str(e), user_id=user_id)
            return {
                "total_transactions": 0,
                "total_charged": 0,
                "total_added": 0,
                "total_refunded": 0,
                "net_spent": 0,
                "current_balance": 0
            }
    
    def check_sufficient_credits(self, user_id: int, required_amount: int) -> Tuple[bool, str]:
        """
        Check if user has sufficient credits for operation
        Returns (has_sufficient, message)
        """
        try:
            balance = self.get_user_balance(user_id)
            if balance is None:
                return False, "User not found"
            
            if balance >= required_amount:
                return True, f"Sufficient credits: {balance} >= {required_amount}"
            else:
                return False, f"Insufficient credits: {balance} < {required_amount}"
                
        except Exception as e:
            logger.error("check_credits_failed", error=str(e), user_id=user_id)
            return False, "Error checking credit balance"
    
    def get_model_cost(self, model_name: str) -> int:
        """
        Get cost for using a specific model
        Returns credit cost
        """
        model_costs = {
            "gemma3_1b": settings.gemma3_1b_cost,
            "gemma3_4b": settings.gemma3_4b_cost,
            "Gemma3 1B": settings.gemma3_1b_cost,
            "Gemma3 4B": settings.gemma3_4b_cost,
        }
        
        return model_costs.get(model_name, 1)  # Default to 1 credit
    
    def process_model_usage(
        self, 
        user_id: int, 
        model_name: str, 
        description: str = None
    ) -> Tuple[bool, str, int]:
        """
        Process credit charge for model usage
        Returns (success, message, remaining_credits)
        """
        cost = self.get_model_cost(model_name)
        
        # Check if user has sufficient credits first
        has_credits, check_message = self.check_sufficient_credits(user_id, cost)
        if not has_credits:
            return False, check_message, self.get_user_balance(user_id) or 0
        
        # Charge credits
        return self.charge_credits(
            user_id=user_id,
            amount=cost,
            description=description or f"Model usage: {model_name}"
        )
    
    def bulk_add_credits(self, user_credits: List[Tuple[int, int]]) -> Tuple[int, int]:
        """
        Add credits to multiple users in bulk
        Args: user_credits - list of (user_id, amount) tuples
        Returns (successful_count, failed_count)
        """
        successful = 0
        failed = 0
        
        for user_id, amount in user_credits:
            try:
                success, _, _ = self.add_credits(
                    user_id=user_id,
                    amount=amount,
                    description="Bulk credit addition"
                )
                if success:
                    successful += 1
                else:
                    failed += 1
                    
            except Exception as e:
                logger.error("bulk_add_failed", error=str(e), user_id=user_id, amount=amount)
                failed += 1
        
        logger.info("bulk_add_completed", successful=successful, failed=failed)
        return successful, failed