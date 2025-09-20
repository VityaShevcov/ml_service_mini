"""
Optimized ML service with advanced memory management and performance optimizations
"""
import time
import torch
import gc
import threading
from typing import Optional, Tuple, Dict, Any, List
from transformers import GenerationConfig
from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta
import hashlib
import json

from app.ml.model_loader import ModelLoader
from app.utils.logging import get_logger
from config import settings


logger = get_logger(__name__)


class MemoryManager:
    """Advanced memory management for ML models"""
    
    def __init__(self, max_memory_usage: float = 0.8):
        self.max_memory_usage = max_memory_usage  # 80% of available memory
        self.memory_threshold = 0.9  # Trigger cleanup at 90%
        
    def get_memory_info(self) -> Dict[str, float]:
        """Get current memory usage information"""
        if torch.cuda.is_available():
            gpu_memory = torch.cuda.get_device_properties(0).total_memory
            gpu_allocated = torch.cuda.memory_allocated()
            gpu_reserved = torch.cuda.memory_reserved()
            
            return {
                "gpu_total_gb": gpu_memory / (1024**3),
                "gpu_allocated_gb": gpu_allocated / (1024**3),
                "gpu_reserved_gb": gpu_reserved / (1024**3),
                "gpu_usage_percent": (gpu_allocated / gpu_memory) * 100,
                "gpu_available": True
            }
        else:
            import psutil
            memory = psutil.virtual_memory()
            return {
                "ram_total_gb": memory.total / (1024**3),
                "ram_used_gb": memory.used / (1024**3),
                "ram_available_gb": memory.available / (1024**3),
                "ram_usage_percent": memory.percent,
                "gpu_available": False
            }
    
    def should_cleanup_memory(self) -> bool:
        """Check if memory cleanup is needed"""
        memory_info = self.get_memory_info()
        
        if memory_info.get("gpu_available", False):
            return memory_info["gpu_usage_percent"] > (self.memory_threshold * 100)
        else:
            return memory_info["ram_usage_percent"] > (self.memory_threshold * 100)
    
    def cleanup_memory(self):
        """Perform memory cleanup"""
        logger.info("performing_memory_cleanup")
        
        # Clear Python garbage
        gc.collect()
        
        # Clear GPU cache if available
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        
        logger.info("memory_cleanup_completed")


class ModelCache:
    """LRU cache for models with memory-aware eviction"""
    
    def __init__(self, max_models: int = 2):
        self.max_models = max_models
        self.models = OrderedDict()
        self.model_sizes = {}
        self.access_times = {}
        self.lock = threading.RLock()
    
    def get(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get model from cache"""
        with self.lock:
            if model_name in self.models:
                # Move to end (most recently used)
                self.models.move_to_end(model_name)
                self.access_times[model_name] = datetime.now()
                return self.models[model_name]
            return None
    
    def put(self, model_name: str, model_data: Dict[str, Any], size_mb: float):
        """Add model to cache with LRU eviction"""
        with self.lock:
            # Remove if already exists
            if model_name in self.models:
                del self.models[model_name]
                del self.model_sizes[model_name]
            
            # Evict least recently used models if cache is full
            while len(self.models) >= self.max_models:
                oldest_model = next(iter(self.models))
                self._evict_model(oldest_model)
            
            # Add new model
            self.models[model_name] = model_data
            self.model_sizes[model_name] = size_mb
            self.access_times[model_name] = datetime.now()
            
            logger.info("model_cached", model=model_name, size_mb=size_mb)
    
    def _evict_model(self, model_name: str):
        """Evict model from cache and free memory"""
        if model_name in self.models:
            logger.info("evicting_model", model=model_name)
            
            # Clear model from memory
            model_data = self.models[model_name]
            if "model" in model_data:
                del model_data["model"]
            if "tokenizer" in model_data:
                del model_data["tokenizer"]
            
            # Remove from cache
            del self.models[model_name]
            del self.model_sizes[model_name]
            if model_name in self.access_times:
                del self.access_times[model_name]
            
            # Force garbage collection
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
    
    def clear(self):
        """Clear all models from cache"""
        with self.lock:
            for model_name in list(self.models.keys()):
                self._evict_model(model_name)
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            total_size = sum(self.model_sizes.values())
            return {
                "cached_models": list(self.models.keys()),
                "cache_size": len(self.models),
                "max_size": self.max_models,
                "total_size_mb": total_size,
                "access_times": dict(self.access_times)
            }


class ResponseCache:
    """Cache for frequently used prompts and responses"""
    
    def __init__(self, max_size: int = 1000, ttl_hours: int = 24):
        self.max_size = max_size
        self.ttl = timedelta(hours=ttl_hours)
        self.cache = OrderedDict()
        self.timestamps = {}
        self.lock = threading.RLock()
    
    def _generate_key(self, prompt: str, model_name: str, **kwargs) -> str:
        """Generate cache key for prompt and parameters"""
        cache_data = {
            "prompt": prompt,
            "model": model_name,
            **kwargs
        }
        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.md5(cache_str.encode()).hexdigest()
    
    def get(self, prompt: str, model_name: str, **kwargs) -> Optional[str]:
        """Get cached response"""
        with self.lock:
            key = self._generate_key(prompt, model_name, **kwargs)
            
            if key in self.cache:
                # Check if expired
                if datetime.now() - self.timestamps[key] > self.ttl:
                    del self.cache[key]
                    del self.timestamps[key]
                    return None
                
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                return self.cache[key]
            
            return None
    
    def put(self, prompt: str, model_name: str, response: str, **kwargs):
        """Cache response"""
        with self.lock:
            key = self._generate_key(prompt, model_name, **kwargs)
            
            # Remove oldest entries if cache is full
            while len(self.cache) >= self.max_size:
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
                del self.timestamps[oldest_key]
            
            self.cache[key] = response
            self.timestamps[key] = datetime.now()
    
    def clear_expired(self):
        """Clear expired entries"""
        with self.lock:
            now = datetime.now()
            expired_keys = [
                key for key, timestamp in self.timestamps.items()
                if now - timestamp > self.ttl
            ]
            
            for key in expired_keys:
                del self.cache[key]
                del self.timestamps[key]
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            now = datetime.now()
            expired_count = sum(
                1 for timestamp in self.timestamps.values()
                if now - timestamp > self.ttl
            )
            
            return {
                "total_entries": len(self.cache),
                "max_size": self.max_size,
                "expired_entries": expired_count,
                "hit_rate": getattr(self, '_hit_count', 0) / max(getattr(self, '_total_requests', 1), 1)
            }


class OptimizedMLService:
    """Optimized ML service with advanced memory management and caching"""
    
    def __init__(self):
        self.model_loader = ModelLoader()
        self.memory_manager = MemoryManager()
        self.model_cache = ModelCache(max_models=2)
        self.response_cache = ResponseCache(max_size=1000, ttl_hours=24)
        
        self.models_loaded = False
        self.current_model = None
        self.model_usage_stats = defaultdict(int)
        self.performance_stats = defaultdict(list)
        
        # Background cleanup thread
        self._cleanup_thread = None
        self._stop_cleanup = False
        
    def initialize_models(self) -> Dict[str, bool]:
        """Initialize ML service with lazy loading"""
        try:
            logger.info("initializing_optimized_ml_service")
            
            # Don't load all models at once - use lazy loading
            self.models_loaded = True
            
            # Start background cleanup thread
            self._start_cleanup_thread()
            
            logger.info("optimized_ml_service_initialized")
            return {"lazy_loading": True}
            
        except Exception as e:
            logger.error("optimized_ml_service_initialization_error", error=str(e))
            return {}
    
    def _start_cleanup_thread(self):
        """Start background thread for memory cleanup"""
        def cleanup_worker():
            while not self._stop_cleanup:
                try:
                    # Clean expired cache entries
                    self.response_cache.clear_expired()
                    
                    # Check memory usage and cleanup if needed
                    if self.memory_manager.should_cleanup_memory():
                        self.memory_manager.cleanup_memory()
                    
                    # Sleep for 5 minutes
                    time.sleep(300)
                    
                except Exception as e:
                    logger.error("cleanup_thread_error", error=str(e))
                    time.sleep(60)  # Wait 1 minute on error
        
        self._cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_thread.start()
        logger.info("cleanup_thread_started")
    
    def _load_model_lazy(self, model_name: str) -> bool:
        """Load model on-demand with caching"""
        try:
            # Check if model is already cached
            cached_model = self.model_cache.get(model_name)
            if cached_model:
                logger.info("model_loaded_from_cache", model=model_name)
                return True
            
            # Check memory before loading
            memory_info = self.memory_manager.get_memory_info()
            logger.info("loading_model_lazy", model=model_name, memory_info=memory_info)
            
            # Load model using existing model loader
            if model_name == "gemma3_1b":
                success = self.model_loader.load_gemma3_1b()
            elif model_name == "gemma3_12b":
                success = self.model_loader.load_gemma3_12b_quantized()
            else:
                return False
            
            if success and model_name in self.model_loader.models:
                # Calculate model size
                model_data = self.model_loader.models[model_name]
                model_size = self._estimate_model_size(model_data["model"])
                
                # Add to cache
                self.model_cache.put(model_name, model_data, model_size)
                
                logger.info("model_loaded_successfully", 
                           model=model_name, 
                           size_mb=model_size)
                return True
            
            return False
            
        except Exception as e:
            logger.error("lazy_model_loading_failed", model=model_name, error=str(e))
            return False
    
    def _estimate_model_size(self, model) -> float:
        """Estimate model size in MB"""
        try:
            param_count = sum(p.numel() for p in model.parameters())
            # Assume 4 bytes per parameter (float32)
            size_bytes = param_count * 4
            return size_bytes / (1024 * 1024)  # Convert to MB
        except:
            return 0.0
    
    def is_model_available(self, model_name: str) -> bool:
        """Check if model is available (can be loaded)"""
        normalized_name = self._normalize_model_name(model_name)
        
        # Check if cached
        if self.model_cache.get(normalized_name):
            return True
        
        # Check if can be loaded
        return normalized_name in ["gemma3_1b", "gemma3_12b"]
    
    def _normalize_model_name(self, model_name: str) -> str:
        """Normalize model name to internal format"""
        name_mapping = {
            "Gemma3 1B": "gemma3_1b",
            "Gemma3 12B": "gemma3_12b",
            "gemma3-1b": "gemma3_1b",
            "gemma3-12b": "gemma3_12b",
            "gemma3_1b": "gemma3_1b",
            "gemma3_12b": "gemma3_12b",
            "1b": "gemma3_1b",
            "12b": "gemma3_12b"
        }
        return name_mapping.get(model_name, model_name.lower())
    
    def get_available_models(self) -> List[str]:
        """Get list of available models"""
        return ["Gemma3 1B", "Gemma3 12B"]
    
    def get_model_cost(self, model_name: str) -> int:
        """Get cost for using a specific model"""
        normalized_name = self._normalize_model_name(model_name)
        
        if normalized_name == "gemma3_1b":
            return settings.gemma3_1b_cost
        elif normalized_name == "gemma3_12b":
            return settings.gemma3_12b_cost
        else:
            return 1
    
    def generate_response(
        self, 
        prompt: str, 
        model_name: str,
        max_length: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Tuple[bool, str, int]:
        """Generate response with caching and optimization"""
        start_time = time.time()
        
        try:
            normalized_name = self._normalize_model_name(model_name)
            
            # Check cache first
            cache_params = {
                "max_length": max_length,
                "temperature": temperature
            }
            cached_response = self.response_cache.get(prompt, normalized_name, **cache_params)
            
            if cached_response:
                processing_time = int((time.time() - start_time) * 1000)
                logger.info("response_served_from_cache", 
                           model=normalized_name,
                           processing_time_ms=processing_time)
                return True, cached_response, processing_time
            
            # Load model if not cached
            if not self.model_cache.get(normalized_name):
                if not self._load_model_lazy(normalized_name):
                    return False, f"Failed to load model {model_name}", 0
            
            # Get model from cache
            model_data = self.model_cache.get(normalized_name)
            if not model_data:
                return False, f"Model {model_name} not available", 0
            
            # Update usage stats
            self.model_usage_stats[normalized_name] += 1
            
            # Generate response using cached model
            success, response, gen_time = self._generate_with_model(
                prompt, model_data, normalized_name, max_length, temperature
            )
            
            if success:
                # Cache the response
                self.response_cache.put(prompt, normalized_name, response, **cache_params)
                
                # Update performance stats
                total_time = int((time.time() - start_time) * 1000)
                self.performance_stats[normalized_name].append(total_time)
                
                # Keep only last 100 measurements
                if len(self.performance_stats[normalized_name]) > 100:
                    self.performance_stats[normalized_name] = self.performance_stats[normalized_name][-100:]
                
                return True, response, total_time
            else:
                return False, response, gen_time
            
        except Exception as e:
            logger.error("optimized_generation_failed", 
                        model=model_name, 
                        error=str(e))
            return False, f"Generation failed: {str(e)}", 0
    
    def _generate_with_model(
        self, 
        prompt: str, 
        model_data: Dict[str, Any], 
        model_name: str,
        max_length: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Tuple[bool, str, int]:
        """Generate response using loaded model"""
        gen_start = time.time()
        
        try:
            model = model_data["model"]
            tokenizer = model_data["tokenizer"]
            generation_config = model_data["generation_config"]
            
            # Format prompt
            formatted_prompt = self._format_prompt(prompt, model_name)
            
            # Tokenize
            inputs = tokenizer(
                formatted_prompt,
                return_tensors="pt",
                truncation=True,
                max_length=2048
            )
            
            # Move to device
            device = next(model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}
            
            # Override generation config if needed
            if max_length or temperature:
                generation_config = GenerationConfig(
                    max_new_tokens=max_length or settings.max_response_length,
                    temperature=temperature or 0.7,
                    do_sample=True,
                    top_p=0.9,
                    pad_token_id=tokenizer.eos_token_id
                )
            
            # Generate
            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    generation_config=generation_config,
                    pad_token_id=tokenizer.eos_token_id
                )
            
            # Decode response
            input_length = inputs["input_ids"].shape[1]
            generated_tokens = outputs[0][input_length:]
            response = tokenizer.decode(generated_tokens, skip_special_tokens=True)
            
            processing_time = int((time.time() - gen_start) * 1000)
            
            logger.info("response_generated", 
                       model=model_name,
                       prompt_length=len(prompt),
                       response_length=len(response),
                       processing_time_ms=processing_time)
            
            return True, response.strip(), processing_time
            
        except Exception as e:
            logger.error("model_generation_failed", 
                        model=model_name, 
                        error=str(e))
            return False, f"Generation error: {str(e)}", 0
    
    def _format_prompt(self, prompt: str, model_name: str) -> str:
        """Format prompt for specific model"""
        if "gemma3" in model_name:
            return f"<start_of_turn>user\n{prompt}<end_of_turn>\n<start_of_turn>model\n"
        return prompt
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        memory_info = self.memory_manager.get_memory_info()
        cache_info = self.model_cache.get_cache_info()
        response_cache_stats = self.response_cache.get_cache_stats()
        
        # Calculate performance metrics
        avg_times = {}
        for model, times in self.performance_stats.items():
            if times:
                avg_times[model] = sum(times) / len(times)
        
        return {
            "models_loaded": self.models_loaded,
            "available_models": self.get_available_models(),
            "memory": memory_info,
            "model_cache": cache_info,
            "response_cache": response_cache_stats,
            "usage_stats": dict(self.model_usage_stats),
            "performance": {
                "avg_processing_times_ms": avg_times,
                "total_requests": sum(self.model_usage_stats.values())
            }
        }
    
    def get_model_info(self, model_name: str) -> Dict[str, Any]:
        """Get detailed model information"""
        normalized_name = self._normalize_model_name(model_name)
        
        # Check if model is cached
        cached_model = self.model_cache.get(normalized_name)
        is_loaded = cached_model is not None
        
        info = {
            "name": model_name,
            "normalized_name": normalized_name,
            "is_loaded": is_loaded,
            "cost": self.get_model_cost(model_name),
            "usage_count": self.model_usage_stats.get(normalized_name, 0)
        }
        
        if is_loaded and normalized_name in self.performance_stats:
            times = self.performance_stats[normalized_name]
            if times:
                info["avg_processing_time_ms"] = sum(times) / len(times)
                info["min_processing_time_ms"] = min(times)
                info["max_processing_time_ms"] = max(times)
        
        return info
    
    def optimize_memory(self):
        """Manually trigger memory optimization"""
        logger.info("manual_memory_optimization_triggered")
        
        # Clear response cache
        self.response_cache.clear_expired()
        
        # Perform memory cleanup
        self.memory_manager.cleanup_memory()
        
        # Log current status
        status = self.get_system_status()
        logger.info("memory_optimization_completed", status=status["memory"])
    
    def shutdown(self):
        """Shutdown service and cleanup resources"""
        logger.info("shutting_down_optimized_ml_service")
        
        # Stop cleanup thread
        self._stop_cleanup = True
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
        
        # Clear all caches
        self.model_cache.clear()
        self.response_cache.cache.clear()
        
        # Final memory cleanup
        self.memory_manager.cleanup_memory()
        
        logger.info("optimized_ml_service_shutdown_complete")