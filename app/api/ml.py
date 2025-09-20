"""
ML API endpoints for model management and inference
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.ml.ml_service import MLService
from app.api.dependencies import get_current_user
from app.models import User


router = APIRouter(prefix="/ml", tags=["machine-learning"])


# Pydantic schemas
class GenerateRequest(BaseModel):
    """Request for text generation"""
    prompt: str = Field(..., min_length=1, max_length=2000, description="Input prompt for generation")
    model_name: str = Field(..., description="Model to use for generation")
    max_length: Optional[int] = Field(None, ge=50, le=1000, description="Maximum response length")
    temperature: Optional[float] = Field(None, ge=0.1, le=2.0, description="Generation temperature")


class GenerateResponse(BaseModel):
    """Response from text generation"""
    success: bool
    response: str
    model_used: str
    processing_time_ms: int
    credits_charged: int
    remaining_credits: int


class ModelInfo(BaseModel):
    """Model information"""
    name: str
    cost: int
    available: bool
    memory_usage_gb: Optional[float] = None
    device: Optional[str] = None


class SystemStatus(BaseModel):
    """System status response"""
    models_loaded: bool
    available_models: List[str]
    memory_usage_gb: float
    max_memory_gb: float
    device: str
    cuda_available: bool


class ErrorResponse(BaseModel):
    """Error response"""
    success: bool = False
    error: str
    detail: Optional[str] = None


# Global ML service instance
ml_service = MLService()


def get_ml_service() -> MLService:
    """Get ML service instance"""
    return ml_service


@router.on_event("startup")
async def startup_ml_service():
    """Initialize ML service on startup (4B only)"""
    try:
        from config import settings
        if settings.use_ollama:
            print("ML Service init: Ollama mode enabled, skipping HF model load")
        else:
            ok4 = ml_service.reload_model("gemma3_4b")
            print(f"ML Service init 4B-only: gemma3_4b loaded={ok4}")
    except Exception as e:
        print(f"Failed to initialize ML service: {e}")


@router.get("/status", response_model=SystemStatus)
async def get_system_status(
    ml_service: MLService = Depends(get_ml_service)
):
    """Get ML system status"""
    status = ml_service.get_system_status()
    return SystemStatus(**status)


@router.get("/models", response_model=List[ModelInfo])
async def get_available_models(
    ml_service: MLService = Depends(get_ml_service)
):
    """Get list of available models"""
    available_models = ml_service.get_available_models()
    
    models_info = []
    for model_name in available_models:
        info = ml_service.get_model_info(model_name)
        cost = ml_service.get_model_cost(model_name)
        
        models_info.append(ModelInfo(
            name=model_name,
            cost=cost,
            available=True,
            memory_usage_gb=info.get("memory_usage_gb") if info else None,
            device=info.get("device") if info else None
        ))
    
    return models_info


@router.get("/models/{model_name}/cost")
async def get_model_cost(
    model_name: str,
    ml_service: MLService = Depends(get_ml_service)
):
    """Get cost for specific model"""
    cost = ml_service.get_model_cost(model_name)
    return {
        "model_name": model_name,
        "cost": cost,
        "description": f"Using {model_name} costs {cost} credit(s) per request"
    }


@router.post("/generate", response_model=GenerateResponse)
async def generate_text(
    request: GenerateRequest,
    current_user: User = Depends(get_current_user),
    ml_service: MLService = Depends(get_ml_service)
):
    """Generate text using specified model"""
    
    # Check if ML service is initialized
    if not ml_service.models_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML service is not initialized. Please try again later."
        )
    
    # Check if model is available
    if not ml_service.is_model_available(request.model_name):
        available_models = ml_service.get_available_models()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model '{request.model_name}' is not available. Available models: {available_models}"
        )
    
    # Get model cost
    cost = ml_service.get_model_cost(request.model_name)
    
    # Check if user has sufficient credits
    if current_user.credits < cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient credits. You have {current_user.credits}, need {cost}"
        )
    
    try:
        # Generate response
        success, response, processing_time = ml_service.generate_response(
            prompt=request.prompt,
            model_name=request.model_name,
            max_length=request.max_length,
            temperature=request.temperature
        )
        
        if not success:
            # Generation failed, don't charge credits
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Text generation failed: {response}"
            )
        
        # TODO: Integrate with billing service to charge credits
        # For now, we'll simulate charging credits
        remaining_credits = current_user.credits - cost
        
        return GenerateResponse(
            success=True,
            response=response,
            model_used=request.model_name,
            processing_time_ms=processing_time,
            credits_charged=cost,
            remaining_credits=remaining_credits
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during generation: {str(e)}"
        )


@router.post("/optimize-memory")
async def optimize_memory(
    current_user: User = Depends(get_current_user),
    ml_service: MLService = Depends(get_ml_service)
):
    """Optimize memory usage (admin function)"""
    
    # For now, allow any authenticated user to optimize memory
    # In production, you might want to restrict this to admin users
    
    try:
        optimization_report = ml_service.optimize_memory()
        return {
            "success": True,
            "message": "Memory optimization completed",
            "report": optimization_report
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Memory optimization failed: {str(e)}"
        )


@router.post("/reload-model/{model_name}")
async def reload_model(
    model_name: str,
    current_user: User = Depends(get_current_user),
    ml_service: MLService = Depends(get_ml_service)
):
    """Reload a specific model (admin function)"""
    
    try:
        success = ml_service.reload_model(model_name)
        
        if success:
            return {
                "success": True,
                "message": f"Model '{model_name}' reloaded successfully"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to reload model '{model_name}'"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Model reload failed: {str(e)}"
        )