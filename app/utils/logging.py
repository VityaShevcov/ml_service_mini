"""
Structured logging utilities
"""
import logging
import structlog
from typing import Any, Dict


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structured logging"""
    
    # Configure standard logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(message)s"
    )
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance"""
    return structlog.get_logger(name)


def log_user_action(logger: structlog.BoundLogger, user_id: int, action: str, **kwargs: Any) -> None:
    """Log user action with structured data"""
    logger.info(
        "user_action",
        user_id=user_id,
        action=action,
        **kwargs
    )


def log_model_interaction(
    logger: structlog.BoundLogger,
    user_id: int,
    model_name: str,
    credits_charged: int,
    processing_time_ms: int,
    **kwargs: Any
) -> None:
    """Log ML model interaction"""
    logger.info(
        "model_interaction",
        user_id=user_id,
        model_name=model_name,
        credits_charged=credits_charged,
        processing_time_ms=processing_time_ms,
        **kwargs
    )


def log_billing_transaction(
    logger: structlog.BoundLogger,
    user_id: int,
    transaction_type: str,
    amount: int,
    **kwargs: Any
) -> None:
    """Log billing transaction"""
    logger.info(
        "billing_transaction",
        user_id=user_id,
        transaction_type=transaction_type,
        amount=amount,
        **kwargs
    )