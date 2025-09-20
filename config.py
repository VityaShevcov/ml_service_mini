"""
Configuration settings for ML Chat Billing Service
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    
    # Database
    database_url: str = "sqlite:///./ml_chat_service.db"
    
    # JWT Settings
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    
    # ML Models
    model_cache_dir: str = "./models"
    max_response_length: int = 128  # Balanced for speed and quality
    # Real Gemma 3 IT models
    gemma3_1b_model: str = "google/gemma-3-1b-it"
    gemma3_4b_model: str = "google/gemma-3-4b-it"
    
    # Billing
    initial_credits: int = 100
    gemma3_1b_cost: int = 1
    gemma3_4b_cost: int = 3
    
    # Server
    host: str = "127.0.0.1"
    port: int = 7860
    debug: bool = True
    
    # Demo mode (uses mock responses instead of real models)
    demo_mode: bool = False
    
    # Logging
    log_level: str = "INFO"
    
    # HuggingFace token (env: HF_TOKEN or HUGGING_FACE_HUB_TOKEN)
    hf_token: Optional[str] = None

    # Ollama integration
    use_ollama: bool = True
    ollama_base_url: str = "http://127.0.0.1:11434"
    
    class Config:
        env_file = ".env"


# Global settings instance
settings = Settings()