#!/usr/bin/env python3
"""Test script for MLService initialization"""

from app.ml.ml_service import MLService
from config import settings

print('Settings:')
print(f'use_ollama: {settings.use_ollama}')
print(f'ollama_base_url: {settings.ollama_base_url}')

print()
print('Testing MLService initialization...')
ml_service = MLService()
print(f'ML service models_loaded: {ml_service.models_loaded}')
print(f'Available models: {ml_service.get_available_models()}')

status = ml_service.get_system_status()
print(f'Device: {status["device"]}')

# Test generation
print()
print('Testing generation...')
success, response, processing_time = ml_service.generate_response(
    prompt='Hello, how are you?',
    model_name='Gemma3 1B',
    max_length=50,
    temperature=0.7
)

print(f'Success: {success}')
print(f'Processing time: {processing_time}ms')
print(f'Response length: {len(response)}')
print(f'Response: {response[:100]}...')
