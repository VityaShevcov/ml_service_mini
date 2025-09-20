"""
Chat service for managing conversations and integrating ML with billing
"""
import time
from typing import Tuple, Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.services.billing_service import BillingService
from app.ml.ml_service import MLService
from app.models import User
from app.models.crud import ModelInteractionCRUD
from app.utils.logging import get_logger, log_model_interaction
from app.utils.transactions import atomic_transaction


logger = get_logger(__name__)


class ChatService:
    """Service for managing chat conversations with ML models and billing"""
    
    def __init__(self, db: Session, ml_service: MLService):
        self.db = db
        self.ml_service = ml_service
        self.billing_service = BillingService(db)
    
    def send_message(
        self,
        user: User,
        message: str,
        model_name: str,
        max_length: Optional[int] = None,
        temperature: Optional[float] = None,
        use_ollama: Optional[bool] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Send a message and get AI response with billing integration
        Returns (success, response_or_error, metadata)
        """
        start_time = time.time()

        try:
            # Validate inputs
            if not message.strip():
                return False, "Message cannot be empty", {}

            if len(message) > 2000:
                return False, "Message too long (max 2000 characters)", {}

            # Determine which ML service to use
            use_ollama_backend = use_ollama if use_ollama is not None else True  # Default to Ollama for speed
            ml_service_to_use = self.ml_service

            # If use_ollama differs from current settings, create a new instance
            if use_ollama_backend != getattr(self.ml_service, '_use_ollama', None):
                from config import settings
                # Temporarily override settings for this request
                original_use_ollama = settings.use_ollama
                settings.use_ollama = use_ollama_backend

                try:
                    ml_service_to_use = MLService()
                    ml_service_to_use._use_ollama = use_ollama_backend
                finally:
                    settings.use_ollama = original_use_ollama

            # Check if ML service is ready
            if not ml_service_to_use.models_loaded:
                # Try to initialize
                try:
                    results = ml_service_to_use.initialize_models()
                    if not any(results.values()):
                        return False, "ML service is not available", {}
                except Exception as e:
                    logger.error("ml_service_init_failed", user_id=user.id, error=str(e))
                    return False, "Failed to initialize ML service", {}
            
            # Ensure requested model is available; try to load it on demand
            if not ml_service_to_use.is_model_available(model_name):
                tried = ml_service_to_use.reload_model(model_name)
                if not tried or not ml_service_to_use.is_model_available(model_name):
                    # Fallback to small model if present
                    fallback = "Gemma3 1B"
                    if ml_service_to_use.is_model_available(fallback) or ml_service_to_use.reload_model(fallback):
                        model_name = fallback
                    else:
                        available_models = ml_service_to_use.get_available_models()
                        return False, f"Model '{model_name}' not available. Available: {available_models}", {}

            # Get model cost
            model_cost = self.billing_service.get_model_cost(model_name)
            
            # Check credits before generation
            has_credits, credit_message = self.billing_service.check_sufficient_credits(
                user.id, model_cost
            )
            
            if not has_credits:
                # Try to fallback to cheaper model if user selected expensive one
                fallback_model = self._get_fallback_model(model_name, user.credits)
                if fallback_model and fallback_model != model_name:
                    logger.info("using_fallback_model", 
                               user_id=user.id,
                               requested_model=model_name,
                               fallback_model=fallback_model,
                               user_credits=user.credits)
                    
                    # Recursively call with fallback model
                    return self.send_message(user, message, fallback_model, max_length, temperature)
                
                return False, credit_message, {"cost": model_cost, "user_credits": user.credits}
            
            # Generate AI response
            logger.info("generating_chat_response",
                       user_id=user.id,
                       model=model_name,
                       message_length=len(message))

            success, ai_response, processing_time = ml_service_to_use.generate_response(
                prompt=message,
                model_name=model_name,
                max_length=max_length,
                temperature=temperature
            )
            
            if not success:
                logger.error("chat_generation_failed", 
                            user_id=user.id,
                            model=model_name,
                            error=ai_response)
                return False, f"Generation failed: {ai_response}", {"processing_time_ms": processing_time}
            
            # Use atomic transaction for billing and logging
            try:
                with atomic_transaction(self.db):
                    # Charge credits
                    charge_success, charge_message, remaining_credits = self.billing_service.charge_credits(
                        user_id=user.id,
                        amount=model_cost,
                        description=f"Chat with {model_name}: {message[:50]}..."
                    )
                    
                    if not charge_success:
                        logger.error("credit_charge_failed", 
                                    user_id=user.id,
                                    model=model_name,
                                    cost=model_cost,
                                    error=charge_message)
                        return False, f"Billing error: {charge_message}", {}
                    
                    # Log interaction
                    interaction = ModelInteractionCRUD.create(
                        db=self.db,
                        user_id=user.id,
                        model_name=model_name,
                        prompt=message,
                        response=ai_response,
                        credits_charged=model_cost,
                        processing_time_ms=processing_time
                    )
                    
                    # Log structured data
                    log_model_interaction(
                        logger, user.id, model_name, model_cost, processing_time,
                        interaction_id=interaction.id,
                        message_length=len(message),
                        response_length=len(ai_response)
                    )
                    
                    # Prepare metadata
                    metadata = {
                        "interaction_id": interaction.id,
                        "model_used": model_name,
                        "credits_charged": model_cost,
                        "remaining_credits": remaining_credits,
                        "processing_time_ms": processing_time,
                        "message_length": len(message),
                        "response_length": len(ai_response)
                    }
                    
                    logger.info("chat_message_completed",
                               user_id=user.id,
                               model=model_name,
                               credits_charged=model_cost,
                               remaining_credits=remaining_credits,
                               processing_time_ms=processing_time)
                    
                    return True, ai_response, metadata
                    
            except Exception as e:
                logger.error("chat_transaction_failed", 
                            user_id=user.id,
                            model=model_name,
                            error=str(e))
                return False, "Transaction failed, please try again", {}
        
        except Exception as e:
            total_time = int((time.time() - start_time) * 1000)
            logger.error("chat_service_error", 
                        user_id=user.id,
                        model=model_name,
                        error=str(e),
                        total_time_ms=total_time)
            return False, f"Unexpected error: {str(e)}", {}
    
    def get_conversation_history(
        self, 
        user_id: int, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get user's conversation history"""
        try:
            interactions = ModelInteractionCRUD.get_by_user(
                db=self.db,
                user_id=user_id,
                skip=offset,
                limit=limit
            )
            
            history = []
            for interaction in interactions:
                history.append({
                    "id": interaction.id,
                    "timestamp": interaction.created_at.isoformat(),
                    "model": interaction.model_name,
                    "prompt": interaction.prompt,
                    "response": interaction.response,
                    "credits_charged": interaction.credits_charged,
                    "processing_time_ms": interaction.processing_time_ms
                })
            
            return history
            
        except Exception as e:
            logger.error("get_history_failed", user_id=user_id, error=str(e))
            return []
    
    def get_conversation_history_filtered(self, user_id: int, limit: int = 20, offset: int = 0,
                                        model_name: str = None, date_from: str = None, 
                                        date_to: str = None) -> Tuple[List[Dict[str, Any]], int]:
        """Get conversation history for a user with filtering"""
        try:
            from datetime import datetime
            from sqlalchemy import and_
            
            # Build query with filters
            query = self.db.query(ModelInteraction).filter(
                ModelInteraction.user_id == user_id
            )
            
            # Apply model filter
            if model_name and model_name != "all":
                query = query.filter(ModelInteraction.model_name == model_name)
            
            # Apply date filters
            if date_from:
                try:
                    from_date = datetime.strptime(date_from, "%Y-%m-%d")
                    query = query.filter(ModelInteraction.created_at >= from_date)
                except ValueError:
                    logger.warning("invalid_date_from", date_from=date_from)
            
            if date_to:
                try:
                    to_date = datetime.strptime(date_to, "%Y-%m-%d")
                    # Add one day to include the entire day
                    to_date = to_date.replace(hour=23, minute=59, second=59)
                    query = query.filter(ModelInteraction.created_at <= to_date)
                except ValueError:
                    logger.warning("invalid_date_to", date_to=date_to)
            
            # Get total count
            total_count = query.count()
            
            # Get interactions with pagination and ordering
            interactions = query.order_by(
                ModelInteraction.created_at.desc()
            ).offset(offset).limit(limit).all()
            
            # Format history
            history = []
            for interaction in interactions:
                history.append({
                    "id": interaction.id,
                    "prompt": interaction.prompt,
                    "response": interaction.response,
                    "model": interaction.model_name,
                    "credits_charged": interaction.credits_charged,
                    "processing_time_ms": interaction.processing_time_ms,
                    "timestamp": interaction.created_at.isoformat()
                })
            
            return history, total_count
            
        except Exception as e:
            logger.error("get_conversation_history_filtered_failed", 
                        user_id=user_id, error=str(e))
            return [], 0
    
    def get_user_chat_stats(self, user_id: int) -> Dict[str, Any]:
        """Get user's chat statistics"""
        try:
            # Get recent interactions
            recent_interactions = ModelInteractionCRUD.get_by_user(
                db=self.db,
                user_id=user_id,
                skip=0,
                limit=100
            )
            
            if not recent_interactions:
                return {
                    "total_messages": 0,
                    "total_credits_spent": 0,
                    "favorite_model": None,
                    "avg_processing_time_ms": 0,
                    "models_used": {}
                }
            
            # Calculate statistics
            total_messages = len(recent_interactions)
            total_credits = sum(i.credits_charged for i in recent_interactions)
            
            # Model usage statistics
            model_usage = {}
            processing_times = []
            
            for interaction in recent_interactions:
                model = interaction.model_name
                model_usage[model] = model_usage.get(model, 0) + 1
                
                if interaction.processing_time_ms:
                    processing_times.append(interaction.processing_time_ms)
            
            # Find favorite model
            favorite_model = max(model_usage.items(), key=lambda x: x[1])[0] if model_usage else None
            
            # Average processing time
            avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
            
            return {
                "total_messages": total_messages,
                "total_credits_spent": total_credits,
                "favorite_model": favorite_model,
                "avg_processing_time_ms": int(avg_processing_time),
                "models_used": model_usage
            }
            
        except Exception as e:
            logger.error("get_chat_stats_failed", user_id=user_id, error=str(e))
            return {}
    
    def estimate_response_cost(self, model_name: str) -> Dict[str, Any]:
        """Estimate cost for using a model"""
        try:
            cost = self.billing_service.get_model_cost(model_name)
            is_available = self.ml_service.is_model_available(model_name)
            
            # Get model info if available
            model_info = self.ml_service.get_model_info(model_name) if is_available else None
            
            return {
                "model_name": model_name,
                "cost": cost,
                "available": is_available,
                "description": f"Costs {cost} credit(s) per message",
                "device": model_info.get("device") if model_info else "unknown"
            }
            
        except Exception as e:
            logger.error("estimate_cost_failed", model=model_name, error=str(e))
            return {
                "model_name": model_name,
                "cost": 1,
                "available": False,
                "description": "Cost estimation failed",
                "device": "unknown"
            }
    
    def validate_message(self, message: str) -> Tuple[bool, str]:
        """Validate chat message"""
        if not message or not message.strip():
            return False, "Message cannot be empty"
        
        if len(message) > 2000:
            return False, "Message too long (maximum 2000 characters)"
        
        # Check for potentially harmful content (basic)
        harmful_patterns = ["<script", "javascript:", "data:text/html"]
        message_lower = message.lower()
        
        for pattern in harmful_patterns:
            if pattern in message_lower:
                return False, "Message contains potentially harmful content"
        
        return True, "Message is valid"
    
    def cleanup_old_interactions(self, days_old: int = 30) -> int:
        """Clean up old interactions (for maintenance)"""
        try:
            from datetime import datetime, timedelta
            
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            # This would need to be implemented in CRUD
            # For now, just return 0
            logger.info("cleanup_requested", days_old=days_old, cutoff_date=cutoff_date.isoformat())
            return 0
            
        except Exception as e:
            logger.error("cleanup_failed", error=str(e))
            return 0

    def _get_fallback_model(self, requested_model: str, user_credits: int) -> Optional[str]:
        """
        Get fallback model if user doesn't have enough credits for requested model
        Returns cheaper model that user can afford, or None if no fallback available
        """
        try:
            # Get all available models with their costs
            available_models = self.ml_service.get_available_models()
            model_costs = []
            
            for model in available_models:
                cost = self.billing_service.get_model_cost(model)
                model_costs.append((model, cost))
            
            # Sort by cost (cheapest first)
            model_costs.sort(key=lambda x: x[1])
            
            # Find cheapest model user can afford that's different from requested
            for model, cost in model_costs:
                if cost <= user_credits and model != requested_model:
                    logger.info("fallback_model_found", 
                               requested=requested_model,
                               fallback=model,
                               cost=cost,
                               user_credits=user_credits)
                    return model
            
            return None
            
        except Exception as e:
            logger.error("fallback_model_selection_failed", error=str(e))
            return None
    
    def get_model_suggestions(self, user_credits: int) -> Dict[str, Any]:
        """Get model suggestions based on user's credit balance"""
        try:
            available_models = self.ml_service.get_available_models()
            suggestions = {
                "affordable": [],
                "expensive": [],
                "recommended": None
            }
            
            for model in available_models:
                cost = self.billing_service.get_model_cost(model)
                model_info = {
                    "name": model,
                    "cost": cost,
                    "affordable": cost <= user_credits
                }
                
                if cost <= user_credits:
                    suggestions["affordable"].append(model_info)
                else:
                    suggestions["expensive"].append(model_info)
            
            # Recommend the most expensive model user can afford
            if suggestions["affordable"]:
                suggestions["recommended"] = max(
                    suggestions["affordable"], 
                    key=lambda x: x["cost"]
                )["name"]
            
            return suggestions
            
        except Exception as e:
            logger.error("model_suggestions_failed", error=str(e))
            return {"affordable": [], "expensive": [], "recommended": None}