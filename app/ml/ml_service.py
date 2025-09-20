"""
ML service for text generation using Gemma3 models
"""
import time
import torch
from typing import Optional, Tuple, Dict, Any
from transformers import GenerationConfig

from app.ml.model_loader import ModelLoader
from app.utils.logging import get_logger
from config import settings


logger = get_logger(__name__)


class MLService:
    """Service for ML model inference and management"""
    
    def __init__(self):
        self.model_loader = ModelLoader()
        self.models_loaded = False
        self.ollama_client = None

        # Initialize Ollama client if enabled
        if settings.use_ollama:
            try:
                from ollama import Client
                self.ollama_client = Client(host=settings.ollama_base_url)
                logger.info("ollama_client_initialized", host=settings.ollama_base_url)
            except ImportError:
                logger.error("ollama_import_failed", reason="ollama library not installed")
                settings.use_ollama = False
            except Exception as e:
                logger.error("ollama_client_init_failed", error=str(e))
                settings.use_ollama = False
        
    def initialize_models(self) -> Dict[str, bool]:
        """
        Initialize ML service (load minimal default model only)
        Returns dict with model load status
        """
        try:
            logger.info("initializing_ml_service")
            # In Ollama mode, skip HF model loading entirely
            if settings.use_ollama:
                self.models_loaded = True
                logger.info("ml_service_initialized_ollama_mode")
                return {"ollama": True}
            # Load only the small model by default to conserve memory
            loaded_small = self.model_loader.load_gemma3_1b()
            results = {"gemma3_1b": loaded_small}
            # Consider service initialized if at least one model is available
            self.models_loaded = loaded_small
            
            if self.models_loaded:
                logger.info("ml_service_initialized", loaded_models=self.model_loader.get_loaded_models())
            else:
                logger.error("ml_service_initialization_failed", reason="no_models_loaded")
            
            return results
            
        except Exception as e:
            logger.error("ml_service_initialization_error", error=str(e))
            return {}
    
    def is_model_available(self, model_name: str) -> bool:
        """Check if model is available for inference"""
        # Normalize model name
        normalized_name = self._normalize_model_name(model_name)
        if settings.use_ollama:
            # In Ollama mode we don't preload HF models; treat as available
            return True
        return self.model_loader.is_model_loaded(normalized_name)
    
    def _normalize_model_name(self, model_name: str) -> str:
        """Normalize model name to internal format"""
        name_mapping = {
            "Gemma3 1B": "gemma3_1b",
            "Gemma3 4B": "gemma3_4b",
            "gemma3_1b": "gemma3_1b",
            "gemma3_4b": "gemma3_4b",
            "1b": "gemma3_1b",
            "4b": "gemma3_4b",
            # be tolerant to input format from UI
            "Gemma3 1b": "gemma3_1b",
            "Gemma3 4b": "gemma3_4b",
            "gemma3 1b": "gemma3_1b",
            "gemma3 4b": "gemma3_4b",
        }
        key = model_name.strip()
        return name_mapping.get(key, name_mapping.get(key.lower(), model_name.lower()))
    
    def get_available_models(self) -> list:
        """Get list of available models"""
        if settings.use_ollama:
            return ["Gemma3 1B", "Gemma3 4B", "Llama3.2 1B"]
        loaded_models = self.model_loader.get_loaded_models()
        
        # Convert to user-friendly names
        friendly_names = []
        for model in loaded_models:
            if model == "gemma3_1b":
                friendly_names.append("Gemma3 1B")
            elif model == "gemma3_4b":
                friendly_names.append("Gemma3 4B")
            else:
                friendly_names.append(model)
        
        return friendly_names
    
    def get_model_cost(self, model_name: str) -> int:
        """Get cost for using a specific model"""
        normalized_name = self._normalize_model_name(model_name)
        
        if normalized_name == "gemma3_1b":
            return settings.gemma3_1b_cost
        elif normalized_name == "gemma3_4b":
            return settings.gemma3_4b_cost
        else:
            return 1  # Default cost
    
    def generate_response(
        self, 
        prompt: str, 
        model_name: str,
        max_length: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Tuple[bool, str, int]:
        """
        Generate response using specified model
        Returns (success, response, processing_time_ms)
        """
        start_time = time.time()

        # Demo mode - return mock responses
        if settings.demo_mode:
            return self._generate_mock_response(prompt, model_name, start_time)

        try:
            # Normalize model name
            normalized_name = self._normalize_model_name(model_name)
            # If Ollama enabled, route generation to Ollama
            if settings.use_ollama:
                return self._generate_ollama_response(prompt, model_name, max_length, temperature)
            
            # Ensure requested model is loaded (sequential swap if needed)
            if not self.is_model_available(normalized_name):
                # Try to load this model (will unload others first)
                reloaded = self.reload_model(normalized_name)
                if not reloaded:
                    return False, f"Model {model_name} is not available", 0
            
            # Get model components
            model_data = self.model_loader.models[normalized_name]
            model = model_data["model"]
            tokenizer = model_data["tokenizer"]
            generation_config = model_data["generation_config"]
            
            # Prepare inputs using chat template for instruction-tuned Gemma 3
            if "gemma3" in normalized_name or "gemma" in normalized_name:
                # Use explicit Gemma chat formatting to avoid tokenizer message schema issues
                formatted_prompt = self._format_prompt(prompt, normalized_name)
                inputs = tokenizer(
                    formatted_prompt,
                    return_tensors="pt",
                    truncation=True,
                    max_length=2048,
                )
            else:
                # Fallback simple formatting
                formatted_prompt = self._format_prompt(prompt, normalized_name)
                inputs = tokenizer(
                    formatted_prompt,
                    return_tensors="pt",
                    truncation=True,
                    max_length=2048,
                )
            
            # Ensure inputs are on the same device as input embeddings
            embedding_device = model.get_input_embeddings().weight.device
            inputs = {k: v.to(embedding_device) for k, v in inputs.items()}
            
            # Override generation config if specified
            if max_length or temperature:
                generation_config = GenerationConfig(
                    max_new_tokens=max_length or settings.max_response_length,
                    temperature=temperature or 0.7,
                    do_sample=True,
                    top_p=0.9,
                    pad_token_id=tokenizer.eos_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                )
            
            # Generate response
            logger.info("generating_response", 
                       model=normalized_name, 
                       prompt_length=len(prompt))
            
            with torch.no_grad():
                # Prefer math (eager) SDPA to avoid alignment issues in some kernels
                try:
                    from torch.backends.cuda import sdp_kernel  # type: ignore
                    if torch.cuda.is_available():
                        with sdp_kernel(enable_flash=False, enable_math=True, enable_mem_efficient=False):
                            outputs = model.generate(
                                **inputs,
                                generation_config=generation_config,
                                do_sample=True,
                                pad_token_id=tokenizer.eos_token_id,
                                eos_token_id=tokenizer.eos_token_id,
                            )
                    else:
                        outputs = model.generate(
                            **inputs,
                            generation_config=generation_config,
                            do_sample=True,
                            pad_token_id=tokenizer.eos_token_id,
                            eos_token_id=tokenizer.eos_token_id,
                        )
                except Exception:
                    outputs = model.generate(
                        **inputs,
                        generation_config=generation_config,
                        do_sample=True,
                        pad_token_id=tokenizer.eos_token_id,
                        eos_token_id=tokenizer.eos_token_id,
                    )
            
            # Decode response
            input_length = inputs["input_ids"].shape[1]
            generated_tokens = outputs[0][input_length:]
            response = tokenizer.decode(generated_tokens, skip_special_tokens=True)
            
            # Clean up response
            response = self._clean_response(response)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            logger.info("response_generated", 
                       model=normalized_name,
                       processing_time_ms=processing_time,
                       response_length=len(response))
            
            return True, response, processing_time
            
        except torch.cuda.OutOfMemoryError:
            logger.error("cuda_out_of_memory", model=normalized_name)
            
            # Try to free memory and suggest using smaller model
            self.model_loader.optimize_memory_usage()
            
            return False, "Out of memory. Please try using Gemma3 1B model instead.", 0
            
        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)
            logger.error("generation_failed", 
                        model=normalized_name, 
                        error=str(e),
                        processing_time_ms=processing_time)
            
            return False, f"Error generating response: {str(e)}", processing_time
    
    def _format_prompt(self, prompt: str, model_name: str) -> str:
        """Format prompt for specific model"""
        # Basic prompt formatting for Gemma models
        if "gemma" in model_name.lower():
            return f"<start_of_turn>user\n{prompt}<end_of_turn>\n<start_of_turn>model\n"
        else:
            return prompt
    
    def _clean_response(self, response: str) -> str:
        """Clean and format the generated response"""
        # Remove common artifacts
        response = response.strip()
        
        # Remove end tokens if present
        end_tokens = ["<end_of_turn>", "<|endoftext|>", "</s>"]
        for token in end_tokens:
            if token in response:
                response = response.split(token)[0]
        
        # Limit response length
        if len(response) > settings.max_response_length * 4:  # Rough character limit
            response = response[:settings.max_response_length * 4] + "..."
        
        return response.strip()
    
    def get_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a model"""
        normalized_name = self._normalize_model_name(model_name)
        if settings.use_ollama:
            return {
                "name": normalized_name,
                "cost": self.get_model_cost(model_name),
                "device": "ollama",
                "loaded": True,
            }
        return self.model_loader.get_model_info(normalized_name)
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get system status and model information"""
        if settings.use_ollama:
            return {
                "models_loaded": True,
                "available_models": self.get_available_models(),
                "loaded_models": ["gemma3_1b", "gemma3_4b"],
                "memory_usage_gb": 0.0,
                "max_memory_gb": self.model_loader.max_memory_gb,
                "device": "ollama",
                "cuda_available": torch.cuda.is_available(),
            }
        return {
            "models_loaded": self.models_loaded,
            "available_models": self.get_available_models(),
            "loaded_models": self.model_loader.get_loaded_models(),
            "memory_usage_gb": self.model_loader.get_memory_usage(),
            "max_memory_gb": self.model_loader.max_memory_gb,
            "device": "cuda" if torch.cuda.is_available() else "cpu",
            "cuda_available": torch.cuda.is_available()
        }
    
    def optimize_memory(self) -> Dict[str, Any]:
        """Optimize memory usage"""
        return self.model_loader.optimize_memory_usage()
    
    def reload_model(self, model_name: str) -> bool:
        """
        Reload a specific model
        Returns True if successful, False otherwise
        """
        try:
            normalized_name = self._normalize_model_name(model_name)
            if settings.use_ollama:
                # No-op in Ollama mode; report success for UI
                return True
            
            # Unload all currently loaded models to free memory for the target
            for loaded in list(self.model_loader.models.keys()):
                self.model_loader.unload_model(loaded)
            
            # Reload model
            if normalized_name == "gemma3_1b":
                ok = self.model_loader.load_gemma3_1b()
            elif normalized_name == "gemma3_4b":
                ok = self.model_loader.load_gemma3_4b()
            else:
                return False
            # Update service readiness flag if a model is available
            if ok:
                self.models_loaded = True
            return ok
                
        except Exception as e:
            logger.error("model_reload_failed", model=model_name, error=str(e))
            return False
    
    def shutdown(self):
        """Shutdown ML service and cleanup resources"""
        try:
            logger.info("shutting_down_ml_service")
            
            # Unload all models
            for model_name in list(self.model_loader.models.keys()):
                self.model_loader.unload_model(model_name)
            
            # Final cleanup
            import gc
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info("ml_service_shutdown_complete")
            
        except Exception as e:
            logger.error("ml_service_shutdown_error", error=str(e))
    
    def _generate_ollama_response(self, prompt: str, model_name: str, max_length: Optional[int], temperature: Optional[float]) -> Tuple[bool, str, int]:
        """Generate response using Ollama backend"""
        start_time = time.time()

        if not self.ollama_client:
            return False, "Ollama client not initialized", 0

        # Map model names to Ollama model names
        model_map = {
            "gemma3_1b": "llama3.2:1b",  # Use llama as fallback since gemma3 not available
            "gemma3_4b": "llama3.2:3b",  # Use llama as fallback
        }

        normalized_name = self._normalize_model_name(model_name)
        ollama_model = model_map.get(normalized_name)

        # Additional fallback logic
        if not ollama_model:
            if "1b" in normalized_name or "small" in normalized_name.lower():
                ollama_model = "llama3.2:1b"
            elif "4b" in normalized_name:
                ollama_model = "llama3.2:3b"

        if not ollama_model:
            return False, f"Model {model_name} not supported by Ollama backend", 0

        try:
            # Generate response using Ollama client with optimized parameters
            response = self.ollama_client.generate(
                model=ollama_model,
                prompt=prompt,
                options={
                    "num_predict": max_length or min(settings.max_response_length, 128),
                    "temperature": temperature or 0.7,
                    "top_k": 30,
                    "top_p": 0.85,
                    "num_ctx": 1024,  # Balanced context size
                    "num_thread": -1,  # Use all available threads
                    "repeat_penalty": 1.1,
                    "repeat_last_n": 32,
                }
            )

            generated_text = response.get('response', '').strip()
            processing_time = int((time.time() - start_time) * 1000)

            logger.info("ollama_response_generated",
                       model=model_name,
                       processing_time_ms=processing_time)

            return True, self._clean_response(generated_text), processing_time

        except Exception as e:
            logger.error("ollama_generation_failed", model=model_name, error=str(e))
            return False, f"Ollama generation failed: {str(e)}", int((time.time() - start_time) * 1000)

    def _generate_mock_response(self, prompt: str, model_name: str, start_time: float) -> Tuple[bool, str, int]:
        """Generate mock response for demo mode"""
        import random
        import time
        
        # Simulate processing time
        processing_delay = random.uniform(0.5, 2.0)  # 0.5-2 seconds
        time.sleep(processing_delay)
        
        # Mock responses based on model
        if "1b" in model_name.lower() or "small" in model_name.lower():
            responses = [
                f"Hello! I'm {model_name} (1B model). I understand you said: '{prompt[:50]}...' This is a demo response.",
                f"Thanks for your message! As {model_name}, I can help with various tasks. Your prompt was about: {prompt[:30]}...",
                f"Hi there! I'm the smaller {model_name} model. I received your message: '{prompt[:40]}...' How can I assist you further?",
                f"Greetings! Using {model_name} to respond to: '{prompt[:35]}...' This is a simulated response for demonstration.",
            ]
        else:
            responses = [
                f"Hello! I'm {model_name} (12B model). I can provide more detailed responses. You asked: '{prompt[:50]}...' Let me give you a comprehensive answer with better reasoning and context understanding.",
                f"Greetings! As the larger {model_name} model, I have enhanced capabilities. Regarding your prompt: '{prompt[:40]}...' I can offer more nuanced and detailed insights on this topic.",
                f"Hi! I'm {model_name} with advanced reasoning. Your message '{prompt[:45]}...' is interesting. I can provide deeper analysis and more sophisticated responses.",
                f"Welcome! Using {model_name} (large model) to address: '{prompt[:35]}...' This allows for more complex reasoning and detailed explanations.",
            ]
        
        response = random.choice(responses)
        processing_time = int((time.time() - start_time) * 1000)
        
        logger.info("mock_response_generated", 
                   model=model_name,
                   prompt_length=len(prompt),
                   response_length=len(response),
                   processing_time_ms=processing_time)
        
        return True, response, processing_time