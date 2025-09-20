"""
Chat API endpoints integrating ML service with billing
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.chat_service import ChatService
from app.ml.ml_service import MLService
from app.api.ml import ml_service  # Use the same MLService instance initialized on startup
from app.api.dependencies import get_current_user
from app.models import User
from app.utils.logging import get_logger


router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger(__name__)

# Global ML service instance is imported from app.api.ml


class ChatRequest(BaseModel):
    """Chat request with model selection"""
    message: str = Field(..., min_length=1, max_length=2000, description="User message")
    model: str = Field(..., description="Model to use (Gemma3 1B or Gemma3 12B)")
    max_length: Optional[int] = Field(None, ge=50, le=1000, description="Maximum response length")
    temperature: Optional[float] = Field(None, ge=0.1, le=2.0, description="Generation temperature")


class ChatResponse(BaseModel):
    """Chat response with billing information"""
    success: bool
    message: str
    model_used: str
    credits_charged: int
    remaining_credits: int
    processing_time_ms: int
    interaction_id: Optional[int] = None


class ChatHistoryItem(BaseModel):
    """Chat history item"""
    id: int
    prompt: str
    response: str
    model_name: str
    credits_charged: int
    processing_time_ms: Optional[int]
    created_at: str


class ChatHistoryResponse(BaseModel):
    """Chat history response"""
    history: list[ChatHistoryItem]
    total_count: int
    page: int
    page_size: int


def get_chat_service(db: Session = Depends(get_db)) -> ChatService:
    """Get ChatService instance"""
    return ChatService(db, ml_service)


@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service)
):
    """
    Send a message to the chat and get AI response
    Integrates ML generation with billing and logging
    """
    
    # Validate message
    is_valid, validation_message = chat_service.validate_message(request.message)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation_message
        )
    
    # Send message through chat service
    success, response_or_error, metadata = chat_service.send_message(
        user=current_user,
        message=request.message,
        model_name=request.model,
        max_length=request.max_length,
        temperature=request.temperature
    )
    
    if not success:
        # Determine appropriate HTTP status code
        if "not available" in response_or_error.lower():
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        elif "insufficient credits" in response_or_error.lower() or "billing error" in response_or_error.lower():
            status_code = status.HTTP_402_PAYMENT_REQUIRED
        elif "invalid" in response_or_error.lower() or "validation" in response_or_error.lower():
            status_code = status.HTTP_400_BAD_REQUEST
        else:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        
        raise HTTPException(
            status_code=status_code,
            detail=response_or_error
        )
    
    # Return successful response
    return ChatResponse(
        success=True,
        message=response_or_error,
        model_used=metadata.get("model_used", request.model),
        credits_charged=metadata.get("credits_charged", 0),
        remaining_credits=metadata.get("remaining_credits", current_user.credits),
        processing_time_ms=metadata.get("processing_time_ms", 0),
        interaction_id=metadata.get("interaction_id")
    )


@router.get("/history")
async def get_chat_history(
    page: int = 1,
    page_size: int = 20,
    model_name: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service)
):
    """Get user's chat history with pagination and filtering"""
    
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 20
    
    offset = (page - 1) * page_size
    
    try:
        # Get history from chat service with filters
        history_data, total_count = chat_service.get_conversation_history_filtered(
            user_id=current_user.id,
            limit=page_size,
            offset=offset,
            model_name=model_name,
            date_from=date_from,
            date_to=date_to
        )
        
        # Convert to response format
        history_items = []
        for item in history_data:
            history_items.append({
                "id": item["id"],
                "prompt": item["prompt"],
                "response": item["response"],
                "model_name": item["model"],
                "credits_charged": item["credits_charged"],
                "processing_time_ms": item["processing_time_ms"],
                "created_at": item["timestamp"]
            })
        
        return {
            "success": True,
            "history": history_items,
            "total": total_count,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_count,
                "pages": (total_count + page_size - 1) // page_size if total_count > 0 else 1
            },
            "filters": {
                "model_name": model_name,
                "date_from": date_from,
                "date_to": date_to
            }
        }
        
    except Exception as e:
        logger.error("chat_history_failed", user_id=current_user.id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve chat history"
        )


@router.get("/models")
async def get_available_models():
    """Get available chat models"""
    
    try:
        if not ml_service.models_loaded:
            # Try to get model info without loading
            return {
                "available_models": [],
                "models_loaded": False,
                "message": "Models not loaded yet. Try sending a message to initialize."
            }
        
        available_models = ml_service.get_available_models()
        
        models_info = []
        for model_name in available_models:
            cost = ml_service.get_model_cost(model_name)
            info = ml_service.get_model_info(model_name)
            
            models_info.append({
                "name": model_name,
                "cost": cost,
                "description": f"Costs {cost} credit(s) per message",
                "available": True,
                "device": info.get("device") if info else "unknown"
            })
        
        return {
            "available_models": models_info,
            "models_loaded": True,
            "message": f"Found {len(models_info)} available models"
        }
        
    except Exception as e:
        logger.error("get_models_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get available models"
        )


@router.get("/status")
async def get_chat_status(
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service)
):
    """Get chat service status for current user"""
    
    try:
        # Get ML service status
        ml_status = ml_service.get_system_status()
        
        # Get user's chat statistics
        chat_stats = chat_service.get_user_chat_stats(current_user.id)
        
        return {
            "user_id": current_user.id,
            "username": current_user.username,
            "credits": current_user.credits,
            "ml_service": {
                "models_loaded": ml_status["models_loaded"],
                "available_models": ml_status["available_models"],
                "memory_usage_gb": ml_status["memory_usage_gb"],
                "device": ml_status["device"]
            },
            "chat_stats": chat_stats,
            "status": "ready" if ml_status["models_loaded"] else "initializing"
        }
        
    except Exception as e:
        logger.error("chat_status_failed", user_id=current_user.id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get chat status"
        )


@router.get("/stats")
async def get_user_chat_stats(
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service)
):
    """Get detailed chat statistics for current user"""
    
    try:
        stats = chat_service.get_user_chat_stats(current_user.id)
        return {
            "success": True,
            "stats": stats
        }
        
    except Exception as e:
        logger.error("get_chat_stats_failed", user_id=current_user.id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get chat statistics"
        )


@router.get("/models/costs")
async def get_model_costs(
    chat_service: ChatService = Depends(get_chat_service)
):
    """Get cost estimates for all available models"""
    
    try:
        available_models = ml_service.get_available_models()
        
        model_costs = []
        for model_name in available_models:
            cost_info = chat_service.estimate_response_cost(model_name)
            model_costs.append(cost_info)
        
        return {
            "success": True,
            "models": model_costs
        }
        
    except Exception as e:
        logger.error("get_model_costs_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get model costs"
        )

@router.get("/model-suggestions")
async def get_model_suggestions(
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service)
):
    """Get model suggestions based on user's credit balance"""
    try:
        suggestions = chat_service.get_model_suggestions(current_user.credits)
        
        return {
            "success": True,
            "user_credits": current_user.credits,
            "suggestions": suggestions
        }
        
    except Exception as e:
        logger.error("get_model_suggestions_failed", user_id=current_user.id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get model suggestions"
        )