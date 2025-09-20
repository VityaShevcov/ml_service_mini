"""
Transaction utilities for ensuring data consistency
"""
from contextlib import contextmanager
from typing import Generator, Any, Callable
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.utils.logging import get_logger


logger = get_logger(__name__)


@contextmanager
def atomic_transaction(db: Session) -> Generator[Session, None, None]:
    """
    Context manager for atomic database transactions
    Automatically commits on success or rolls back on error
    """
    try:
        yield db
        db.commit()
        logger.debug("transaction_committed")
    except SQLAlchemyError as e:
        db.rollback()
        logger.error("transaction_rollback", error=str(e), error_type="SQLAlchemyError")
        raise
    except Exception as e:
        db.rollback()
        logger.error("transaction_rollback", error=str(e), error_type="UnexpectedError")
        raise


def with_transaction(func: Callable) -> Callable:
    """
    Decorator to wrap function in atomic transaction
    """
    def wrapper(*args, **kwargs):
        # Assume first argument is self and has db attribute
        if hasattr(args[0], 'db'):
            db = args[0].db
            with atomic_transaction(db):
                return func(*args, **kwargs)
        else:
            return func(*args, **kwargs)
    
    return wrapper


class TransactionManager:
    """
    Manager for handling complex multi-step transactions
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.operations = []
        self.rollback_operations = []
    
    def add_operation(self, operation: Callable, rollback_operation: Callable = None):
        """
        Add an operation to the transaction
        Args:
            operation: Function to execute
            rollback_operation: Function to execute if rollback is needed
        """
        self.operations.append(operation)
        if rollback_operation:
            self.rollback_operations.append(rollback_operation)
    
    def execute(self) -> bool:
        """
        Execute all operations in transaction
        Returns True if successful, False otherwise
        """
        executed_operations = []
        
        try:
            for i, operation in enumerate(self.operations):
                result = operation()
                executed_operations.append(i)
                
                if not result:
                    raise Exception(f"Operation {i} failed")
            
            self.db.commit()
            logger.info("multi_step_transaction_success", operations_count=len(self.operations))
            return True
            
        except Exception as e:
            logger.error("multi_step_transaction_failed", error=str(e))
            
            # Execute rollback operations in reverse order
            for i in reversed(executed_operations):
                if i < len(self.rollback_operations):
                    try:
                        self.rollback_operations[i]()
                    except Exception as rollback_error:
                        logger.error("rollback_operation_failed", 
                                   operation_index=i, 
                                   error=str(rollback_error))
            
            self.db.rollback()
            return False
    
    def clear(self):
        """Clear all operations"""
        self.operations.clear()
        self.rollback_operations.clear()


def ensure_credit_consistency(db: Session, user_id: int) -> bool:
    """
    Ensure credit consistency by checking user balance against transaction history
    Returns True if consistent, False otherwise
    """
    try:
        from app.models.crud import UserCRUD, CreditTransactionCRUD
        
        user = UserCRUD.get_by_id(db, user_id)
        if not user:
            return False
        
        transactions = CreditTransactionCRUD.get_by_user(db, user_id, 0, 10000)
        
        # Calculate expected balance from transactions
        from config import settings
        expected_balance = settings.initial_credits  # Initial credits from settings
        for transaction in transactions:
            if transaction.transaction_type == "charge":
                expected_balance += transaction.amount  # amount is negative for charges
            elif transaction.transaction_type in ["add", "refund"]:
                expected_balance += transaction.amount  # amount is positive for adds/refunds
        
        is_consistent = user.credits == expected_balance
        
        if not is_consistent:
            logger.error("credit_inconsistency_detected",
                        user_id=user_id,
                        actual_balance=user.credits,
                        expected_balance=expected_balance,
                        transaction_count=len(transactions))
        
        return is_consistent
        
    except Exception as e:
        logger.error("credit_consistency_check_failed", error=str(e), user_id=user_id)
        return False


def repair_credit_balance(db: Session, user_id: int) -> bool:
    """
    Repair user credit balance based on transaction history
    Returns True if repair was successful, False otherwise
    """
    try:
        from app.models.crud import UserCRUD, CreditTransactionCRUD
        
        user = UserCRUD.get_by_id(db, user_id)
        if not user:
            return False
        
        transactions = CreditTransactionCRUD.get_by_user(db, user_id, 0, 10000)
        
        # Calculate correct balance from transactions
        correct_balance = 100  # Initial credits
        for transaction in transactions:
            if transaction.transaction_type == "charge":
                correct_balance += transaction.amount  # amount is negative for charges
            elif transaction.transaction_type in ["add", "refund"]:
                correct_balance += transaction.amount  # amount is positive for adds/refunds
        
        # Update user balance
        old_balance = user.credits
        success = UserCRUD.update_credits(db, user_id, correct_balance)
        
        if success:
            logger.info("credit_balance_repaired",
                       user_id=user_id,
                       old_balance=old_balance,
                       new_balance=correct_balance,
                       transaction_count=len(transactions))
            return True
        
        return False
        
    except Exception as e:
        logger.error("credit_balance_repair_failed", error=str(e), user_id=user_id)
        return False