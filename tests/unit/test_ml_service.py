"""
Unit tests for ML service with mock models
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import torch

from app.ml.ml_service import MLService
from app.ml.model_loader import ModelLoader


class MockModel:
    """Mock model for testing"""
    
    def __init__(self, response_text="Mock response"):
        self.response_text = response_text
        self.device = "cpu"
    
    def parameters(self):
        """Mock parameters method"""
        param = Mock()
        param.device = self.device
        yield param
    
    def generate(self, **kwargs):
        """Mock generate method"""
        # Return mock tensor that represents generated tokens
        input_ids = kwargs.get("input_ids", torch.tensor([[1, 2, 3]]))
        # Simulate adding new tokens
        new_tokens = torch.tensor([[4, 5, 6, 7]])
        return torch.cat([input_ids, new_tokens], dim=1)


class MockTokenizer:
    """Mock tokenizer for testing"""
    
    def __init__(self):
        self.eos_token_id = 2
    
    def __call__(self, text, **kwargs):
        """Mock tokenization"""
        return {
            "input_ids": torch.tensor([[1, 2, 3]]),
            "attention_mask": torch.tensor([[1, 1, 1]])
        }
    
    def decode(self, tokens, **kwargs):
        """Mock decoding"""
        return "Mock response from model"


@pytest.fixture
def mock_ml_service():
    """Create MLService with mocked components"""
    service = MLService()
    
    # Mock the model loader
    service.model_loader = Mock(spec=ModelLoader)
    service.model_loader.models = {
        "gemma3_1b": {
            "model": MockModel("Fast response"),
            "tokenizer": MockTokenizer(),
            "generation_config": Mock(),
            "cost": 1
        },
        "gemma3_12b": {
            "model": MockModel("Detailed response"),
            "tokenizer": MockTokenizer(),
            "generation_config": Mock(),
            "cost": 3
        }
    }
    
    service.model_loader.is_model_loaded.side_effect = lambda name: name in service.model_loader.models
    service.model_loader.get_loaded_models.return_value = ["gemma3_1b", "gemma3_12b"]
    service.model_loader.get_memory_usage.return_value = 4.5
    service.models_loaded = True
    
    return service


class TestMLService:
    """Test ML service functionality"""
    
    def test_normalize_model_name(self, mock_ml_service):
        """Test model name normalization"""
        service = mock_ml_service
        
        assert service._normalize_model_name("Gemma3 1B") == "gemma3_1b"
        assert service._normalize_model_name("Gemma3 12B") == "gemma3_12b"
        assert service._normalize_model_name("1b") == "gemma3_1b"
        assert service._normalize_model_name("12b") == "gemma3_12b"
        assert service._normalize_model_name("gemma3_1b") == "gemma3_1b"
    
    def test_is_model_available(self, mock_ml_service):
        """Test checking model availability"""
        service = mock_ml_service
        
        assert service.is_model_available("Gemma3 1B") is True
        assert service.is_model_available("Gemma3 12B") is True
        assert service.is_model_available("nonexistent") is False
    
    def test_get_available_models(self, mock_ml_service):
        """Test getting available models"""
        service = mock_ml_service
        
        models = service.get_available_models()
        assert "Gemma3 1B" in models
        assert "Gemma3 12B" in models
        assert len(models) == 2
    
    def test_get_model_cost(self, mock_ml_service):
        """Test getting model costs"""
        service = mock_ml_service
        
        assert service.get_model_cost("Gemma3 1B") == 1
        assert service.get_model_cost("Gemma3 12B") == 3
        assert service.get_model_cost("gemma3_1b") == 1
        assert service.get_model_cost("unknown") == 1  # Default
    
    @patch('torch.no_grad')
    def test_generate_response_success(self, mock_no_grad, mock_ml_service):
        """Test successful response generation"""
        service = mock_ml_service
        
        # Mock torch.no_grad context manager
        mock_no_grad.return_value.__enter__ = Mock()
        mock_no_grad.return_value.__exit__ = Mock()
        
        success, response, processing_time = service.generate_response(
            prompt="Hello, how are you?",
            model_name="Gemma3 1B"
        )
        
        assert success is True
        assert isinstance(response, str)
        assert len(response) > 0
        assert processing_time >= 0
    
    def test_generate_response_model_not_available(self, mock_ml_service):
        """Test response generation with unavailable model"""
        service = mock_ml_service
        
        success, response, processing_time = service.generate_response(
            prompt="Hello",
            model_name="nonexistent_model"
        )
        
        assert success is False
        assert "not available" in response
        assert processing_time == 0
    
    @patch('torch.no_grad')
    def test_generate_response_with_custom_params(self, mock_no_grad, mock_ml_service):
        """Test response generation with custom parameters"""
        service = mock_ml_service
        
        # Mock torch.no_grad context manager
        mock_no_grad.return_value.__enter__ = Mock()
        mock_no_grad.return_value.__exit__ = Mock()
        
        success, response, processing_time = service.generate_response(
            prompt="Hello",
            model_name="Gemma3 1B",
            max_length=100,
            temperature=0.8
        )
        
        assert success is True
        assert isinstance(response, str)
    
    def test_format_prompt(self, mock_ml_service):
        """Test prompt formatting"""
        service = mock_ml_service
        
        # Test Gemma formatting
        formatted = service._format_prompt("Hello", "gemma3_1b")
        assert "<start_of_turn>user" in formatted
        assert "<end_of_turn>" in formatted
        
        # Test other model (no special formatting)
        formatted = service._format_prompt("Hello", "other_model")
        assert formatted == "Hello"
    
    def test_clean_response(self, mock_ml_service):
        """Test response cleaning"""
        service = mock_ml_service
        
        # Test removing end tokens
        response = "Hello there<end_of_turn>"
        cleaned = service._clean_response(response)
        assert "<end_of_turn>" not in cleaned
        assert cleaned == "Hello there"
        
        # Test stripping whitespace
        response = "  Hello there  "
        cleaned = service._clean_response(response)
        assert cleaned == "Hello there"
    
    def test_get_model_info(self, mock_ml_service):
        """Test getting model information"""
        service = mock_ml_service
        
        # Mock the model_loader.get_model_info method
        service.model_loader.get_model_info.return_value = {
            "name": "gemma3_1b",
            "cost": 1,
            "memory_usage_gb": 2.5,
            "device": "cpu",
            "loaded": True
        }
        
        info = service.get_model_info("Gemma3 1B")
        assert info is not None
        assert info["name"] == "gemma3_1b"
        assert info["cost"] == 1
    
    def test_get_system_status(self, mock_ml_service):
        """Test getting system status"""
        service = mock_ml_service
        
        status = service.get_system_status()
        
        assert "models_loaded" in status
        assert "available_models" in status
        assert "memory_usage_gb" in status
        assert "device" in status
        assert status["models_loaded"] is True
    
    def test_optimize_memory(self, mock_ml_service):
        """Test memory optimization"""
        service = mock_ml_service
        
        # Mock the optimization method
        service.model_loader.optimize_memory_usage.return_value = {
            "initial_memory_gb": 8.0,
            "final_memory_gb": 6.0,
            "memory_freed_gb": 2.0,
            "actions_taken": ["unloaded_gemma3_12b"]
        }
        
        result = service.optimize_memory()
        
        assert "memory_freed_gb" in result
        assert result["memory_freed_gb"] >= 0
    
    def test_reload_model(self, mock_ml_service):
        """Test model reloading"""
        service = mock_ml_service
        
        # Mock the reload methods
        service.model_loader.unload_model.return_value = True
        service.model_loader.load_gemma3_1b.return_value = True
        service.model_loader.load_gemma3_12b_quantized.return_value = True
        
        # Test reloading 1B model
        success = service.reload_model("Gemma3 1B")
        assert success is True
        
        # Test reloading 12B model
        success = service.reload_model("Gemma3 12B")
        assert success is True
        
        # Test reloading unknown model
        success = service.reload_model("unknown")
        assert success is False
    
    def test_shutdown(self, mock_ml_service):
        """Test service shutdown"""
        service = mock_ml_service
        
        # Mock unload methods
        service.model_loader.unload_model.return_value = True
        
        # Should not raise any exceptions
        service.shutdown()
        
        # Verify unload was called for each model
        expected_calls = len(service.model_loader.models)
        assert service.model_loader.unload_model.call_count == expected_calls


class TestModelLoader:
    """Test ModelLoader functionality with mocks"""
    
    @patch('psutil.Process')
    def test_get_memory_usage(self, mock_process):
        """Test memory usage calculation"""
        # Mock memory info
        mock_process.return_value.memory_info.return_value.rss = 2048 * 1024 * 1024  # 2GB in bytes
        
        loader = ModelLoader()
        memory_gb = loader.get_memory_usage()
        
        assert memory_gb == 2.0
    
    def test_check_memory_available(self):
        """Test memory availability check"""
        loader = ModelLoader()
        loader.max_memory_gb = 10
        
        # Mock get_memory_usage
        with patch.object(loader, 'get_memory_usage', return_value=4.0):
            # Should have enough memory (10 - 4 = 6GB available, need 2GB)
            assert loader.check_memory_available(2.0) is True
            
            # Should not have enough memory (need 8GB, only 6GB available)
            assert loader.check_memory_available(8.0) is False
    
    def test_is_model_loaded(self):
        """Test checking if model is loaded"""
        loader = ModelLoader()
        
        # No models loaded initially
        assert loader.is_model_loaded("gemma3_1b") is False
        
        # Add mock model
        loader.models["gemma3_1b"] = {"model": Mock()}
        assert loader.is_model_loaded("gemma3_1b") is True
    
    def test_get_loaded_models(self):
        """Test getting loaded models list"""
        loader = ModelLoader()
        
        # No models initially
        assert loader.get_loaded_models() == []
        
        # Add mock models
        loader.models["gemma3_1b"] = {"model": Mock()}
        loader.models["gemma3_12b"] = {"model": Mock()}
        
        loaded = loader.get_loaded_models()
        assert "gemma3_1b" in loaded
        assert "gemma3_12b" in loaded
        assert len(loaded) == 2