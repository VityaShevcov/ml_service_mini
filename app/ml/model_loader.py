"""
Model loader for Gemma3 models with quantization support
"""
import os
import gc
import torch
from typing import Optional, Dict, Any

# Avoid importing torchvision via transformers image utils on text-only usage
os.environ.setdefault("TRANSFORMERS_NO_TORCHVISION", "1")

from transformers import (
    AutoModelForCausalLM, 
    AutoTokenizer, 
    BitsAndBytesConfig,
    GenerationConfig
)
import psutil

from app.utils.logging import get_logger
from config import settings


logger = get_logger(__name__)


class ModelLoader:
    """Loader for Gemma3 models with memory optimization"""
    
    def __init__(self):
        self.models: Dict[str, Dict[str, Any]] = {}
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.max_memory_gb = 10  # Conservative limit for RTX 3080 Ti (12GB VRAM)
        
    def get_memory_usage(self) -> float:
        """Get current GPU memory usage in GB"""
        if torch.cuda.is_available():
            # Get GPU memory usage
            gpu_memory_mb = torch.cuda.memory_allocated() / 1024 / 1024
            return gpu_memory_mb / 1024
        else:
            # Fallback to system memory
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            return memory_mb / 1024
    
    def check_memory_available(self, required_gb: float) -> bool:
        """Check if enough memory is available"""
        if torch.cuda.is_available():
            current_usage = self.get_memory_usage()
            available = self.max_memory_gb - current_usage
        else:
            vm = psutil.virtual_memory()
            available = vm.available / 1024**3
            current_usage = (vm.total - vm.available) / 1024**3
        
        logger.info("memory_check", 
                   current_usage_gb=current_usage,
                   required_gb=required_gb,
                   available_gb=available)
        
        return available >= required_gb
    
    def load_gemma3_1b(self) -> bool:
        """
        Load Gemma3 1B model
        Returns True if successful, False otherwise
        """
        model_name = "gemma3_1b"
        
        try:
            if model_name in self.models:
                logger.info("model_already_loaded", model=model_name)
                return True
            
            # Check memory availability (2B model needs ~4GB VRAM)
            if not self.check_memory_available(4.0):
                logger.error("insufficient_memory", model=model_name, required_gb=4.0)
                return False
            
            logger.info("loading_model", model=model_name, model_id=settings.gemma3_1b_model)
            
            # Load tokenizer
            tokenizer = AutoTokenizer.from_pretrained(
                settings.gemma3_1b_model,
                cache_dir=settings.model_cache_dir,
                token=settings.hf_token
            )
            
            # Load model; prefer bfloat16 on cuda, float32 on cpu
            kwargs = dict(
                cache_dir=settings.model_cache_dir,
                trust_remote_code=True,
                token=settings.hf_token,
            )
            if self.device == "cuda":
                kwargs.update(dict(torch_dtype=torch.bfloat16, device_map="auto"))
            model = AutoModelForCausalLM.from_pretrained(settings.gemma3_1b_model, **kwargs)
            
            if self.device == "cpu":
                model = model.to(self.device)
            
            # Configure generation
            generation_config = GenerationConfig(
                max_new_tokens=settings.max_response_length,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                pad_token_id=tokenizer.eos_token_id
            )
            
            self.models[model_name] = {
                "model": model,
                "tokenizer": tokenizer,
                "generation_config": generation_config,
                "cost": settings.gemma3_1b_cost,
                "loaded_at": torch.cuda.memory_allocated() if torch.cuda.is_available() else 0
            }
            
            logger.info("model_loaded_successfully", 
                       model=model_name,
                       memory_usage_gb=self.get_memory_usage())
            return True
            
        except Exception as e:
            logger.error("model_loading_failed", model=model_name, error=str(e))
            return False
    
    def load_gemma3_4b(self) -> bool:
        """
        Load Gemma3 4B model on GPU (no quantization), with device_map="auto" and bfloat16.
        Returns True if successful, False otherwise
        """
        model_name = "gemma3_4b"
        
        try:
            if model_name in self.models:
                logger.info("model_already_loaded", model=model_name)
                return True
            
            # GPU preferred path; if CUDA not available, fail (user requires GPU)
            if self.device != "cuda":
                logger.error("cuda_required_for_4b", model=model_name)
                return False
            
            logger.info("loading_model", model=model_name, model_id=settings.gemma3_4b_model)
            
            # Prefer stable CPU load for 4B to avoid CUDA kernel issues
            quantization_config = None
            
            # Load tokenizer
            tokenizer = AutoTokenizer.from_pretrained(
                settings.gemma3_4b_model,
                cache_dir=settings.model_cache_dir,
                token=settings.hf_token
            )
            
            # Load model on GPU with BF16 and device_map auto
            model = AutoModelForCausalLM.from_pretrained(
                settings.gemma3_4b_model,
                cache_dir=settings.model_cache_dir,
                torch_dtype=torch.bfloat16,
                device_map="auto",
                low_cpu_mem_usage=True,
                trust_remote_code=True,
                token=settings.hf_token,
                attn_implementation="eager"
            )
            
            # Configure generation
            generation_config = GenerationConfig(
                max_new_tokens=settings.max_response_length,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                pad_token_id=tokenizer.eos_token_id
            )
            
            self.models[model_name] = {
                "model": model,
                "tokenizer": tokenizer,
                "generation_config": generation_config,
                "cost": settings.gemma3_4b_cost,
                "loaded_at": torch.cuda.memory_allocated() if torch.cuda.is_available() else 0
            }
            
            logger.info("model_loaded_successfully", 
                       model=model_name,
                       memory_usage_gb=self.get_memory_usage())
            return True
            
        except Exception as e:
            logger.error("model_loading_failed", model=model_name, error=str(e))
            return False
    
    def unload_model(self, model_name: str) -> bool:
        """
        Unload a model to free memory
        Returns True if successful, False otherwise
        """
        try:
            if model_name not in self.models:
                logger.warning("model_not_loaded", model=model_name)
                return False
            
            # Delete model and tokenizer
            del self.models[model_name]["model"]
            del self.models[model_name]["tokenizer"]
            del self.models[model_name]
            
            # Force garbage collection
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info("model_unloaded", 
                       model=model_name,
                       memory_usage_gb=self.get_memory_usage())
            return True
            
        except Exception as e:
            logger.error("model_unload_failed", model=model_name, error=str(e))
            return False
    
    def is_model_loaded(self, model_name: str) -> bool:
        """Check if model is loaded"""
        return model_name in self.models
    
    def get_loaded_models(self) -> list:
        """Get list of loaded model names"""
        return list(self.models.keys())
    
    def get_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a loaded model"""
        if model_name not in self.models:
            return None
        
        model_data = self.models[model_name]
        return {
            "name": model_name,
            "cost": model_data["cost"],
            "memory_usage_gb": self.get_memory_usage(),
            "device": str(next(model_data["model"].parameters()).device),
            "loaded": True
        }
    
    def optimize_memory_usage(self) -> Dict[str, Any]:
        """
        Optimize memory usage by managing loaded models
        Returns optimization report
        """
        current_memory = self.get_memory_usage()
        
        optimization_report = {
            "initial_memory_gb": current_memory,
            "actions_taken": [],
            "final_memory_gb": current_memory,
            "memory_freed_gb": 0
        }
        
        # If memory usage is high, unload less critical models
        if current_memory > self.max_memory_gb * 0.8:  # 80% threshold
            logger.warning("high_memory_usage", memory_gb=current_memory)
            
            # Unload 12B model first if both are loaded
            if "gemma3_12b" in self.models and "gemma3_1b" in self.models:
                if self.unload_model("gemma3_12b"):
                    optimization_report["actions_taken"].append("unloaded_gemma3_12b")
            
            # Force garbage collection
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            optimization_report["actions_taken"].append("garbage_collection")
        
        final_memory = self.get_memory_usage()
        optimization_report["final_memory_gb"] = final_memory
        optimization_report["memory_freed_gb"] = current_memory - final_memory
        
        logger.info("memory_optimization_completed", **optimization_report)
        return optimization_report
    
    def load_models(self) -> Dict[str, bool]:
        """
        Load all configured models
        Returns dict with model names and load status
        """
        results = {}
        
        logger.info("starting_model_loading")
        
        # Try to load 1B model first (smaller)
        results["gemma3_1b"] = self.load_gemma3_1b()
        
        # Try to load 4B model if memory allows
        if self.check_memory_available(3.5):
            results["gemma3_4b"] = self.load_gemma3_4b_quantized()
        else:
            logger.warning("skipping_4b_model", reason="insufficient_memory")
            results["gemma3_4b"] = False
        
        # Log final status
        loaded_models = [name for name, status in results.items() if status]
        logger.info("model_loading_completed", 
                   loaded_models=loaded_models,
                   total_memory_gb=self.get_memory_usage())
        
        return results