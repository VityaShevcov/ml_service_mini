"""
Unit tests for OptimizedMLService
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import time
from datetime import datetime

from app.ml.optimized_ml_service import (
    OptimizedMLService, 
    MemoryManager, 
    ModelCache, 
    ResponseCache
)


class TestMemoryManager:
    """Test cases for MemoryManager"""
    
    @pytest.fixture
    def memory_manager(self):
        """MemoryManager instance for testing"""
        return MemoryManager(max_memory_usage=0.8)
    
    @patch('app.ml.optimized_ml_service.torch')
    @patch('app.ml.optimized_ml_service.psutil')
    def test_get_memory_info_with_gpu(self, mock_psutil, mock_torch, memory_manager):
        """Test memory info retrieval with GPU available"""
        # Mock GPU availability
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.memory_allocated.return_value = 2 * 1024**3  # 2GB
        mock_torch.cuda.memory_reserved.return_value = 3 * 1024**3   # 3GB
        
        mock_props = Mock()
        mock_props.total_memory = 8 * 1024**3  # 8GB
        mock_torch.cuda.get_device_properties.return_value = mock_props
        
        # Test
        memory_info = memory_manager.get_memory_info()
        
        # Assertions
        assert memory_info["gpu_available"] == True
        assert memory_info["gpu_total_gb"] == 8.0
        assert memory_info["gpu_allocated_gb"] == 2.0
        assert memory_info["gpu_usage_percent"] == 25.0
    
    @patch('app.ml.optimized_ml_service.torch')
    @patch('app.ml.optimized_ml_service.psutil')
    def test_get_memory_info_without_gpu(self, mock_psutil, mock_torch, memory_manager):
        """Test memory info retrieval without GPU"""
        # Mock no GPU
        mock_torch.cuda.is_available.return_value = False
        
        # Mock system memory
        mock_memory = Mock()
        mock_memory.total = 16 * 1024**3  # 16GB
        mock_memory.used = 8 * 1024**3    # 8GB
        mock_memory.available = 8 * 1024**3  # 8GB
        mock_memory.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_memory
        
        # Test
        memory_info = memory_manager.get_memory_info()
        
        # Assertions
        assert memory_info["gpu_available"] == False
        assert memory_info["ram_total_gb"] == 16.0
        assert memory_info["ram_used_gb"] == 8.0
        assert memory_info["ram_usage_percent"] == 50.0
    
    def test_should_cleanup_memory(self, memory_manager):
        """Test memory cleanup threshold detection"""
        with patch.object(memory_manager, 'get_memory_info') as mock_get_info:
            # Test high GPU usage
            mock_get_info.return_value = {
                "gpu_available": True,
                "gpu_usage_percent": 95.0
            }
            assert memory_manager.should_cleanup_memory() == True
            
            # Test normal GPU usage
            mock_get_info.return_value = {
                "gpu_available": True,
                "gpu_usage_percent": 70.0
            }
            assert memory_manager.should_cleanup_memory() == False
            
            # Test high RAM usage
            mock_get_info.return_value = {
                "gpu_available": False,
                "ram_usage_percent": 95.0
            }
            assert memory_manager.should_cleanup_memory() == True
    
    @patch('app.ml.optimized_ml_service.torch')
    @patch('app.ml.optimized_ml_service.gc')
    def test_cleanup_memory(self, mock_gc, mock_torch, memory_manager):
        """Test memory cleanup execution"""
        mock_torch.cuda.is_available.return_value = True
        
        # Test cleanup
        memory_manager.cleanup_memory()
        
        # Verify cleanup calls
        mock_gc.collect.assert_called_once()
        mock_torch.cuda.empty_cache.assert_called_once()
        mock_torch.cuda.synchronize.assert_called_once()


class TestModelCache:
    """Test cases for ModelCache"""
    
    @pytest.fixture
    def model_cache(self):
        """ModelCache instance for testing"""
        return ModelCache(max_models=2)
    
    def test_put_and_get_model(self, model_cache):
        """Test adding and retrieving models from cache"""
        # Create mock model data
        model_data = {
            "model": Mock(),
            "tokenizer": Mock(),
            "generation_config": Mock()
        }
        
        # Add to cache
        model_cache.put("test_model", model_data, 100.0)
        
        # Retrieve from cache
        retrieved = model_cache.get("test_model")
        
        # Assertions
        assert retrieved is not None
        assert retrieved == model_data
        assert "test_model" in model_cache.models
        assert model_cache.model_sizes["test_model"] == 100.0
    
    def test_lru_eviction(self, model_cache):
        """Test LRU eviction when cache is full"""
        # Add models to fill cache
        model_cache.put("model1", {"model": Mock()}, 50.0)
        model_cache.put("model2", {"model": Mock()}, 60.0)
        
        # Cache should be full
        assert len(model_cache.models) == 2
        
        # Add third model - should evict oldest
        model_cache.put("model3", {"model": Mock()}, 70.0)
        
        # Assertions
        assert len(model_cache.models) == 2
        assert "model1" not in model_cache.models  # Should be evicted
        assert "model2" in model_cache.models
        assert "model3" in model_cache.models
    
    def test_access_updates_lru_order(self, model_cache):
        """Test that accessing a model updates LRU order"""
        # Add two models
        model_cache.put("model1", {"model": Mock()}, 50.0)
        model_cache.put("model2", {"model": Mock()}, 60.0)
        
        # Access first model (makes it most recent)
        model_cache.get("model1")
        
        # Add third model
        model_cache.put("model3", {"model": Mock()}, 70.0)
        
        # model2 should be evicted (least recently used)
        assert "model1" in model_cache.models
        assert "model2" not in model_cache.models
        assert "model3" in model_cache.models
    
    def test_clear_cache(self, model_cache):
        """Test clearing all models from cache"""
        # Add models
        model_cache.put("model1", {"model": Mock()}, 50.0)
        model_cache.put("model2", {"model": Mock()}, 60.0)
        
        # Clear cache
        model_cache.clear()
        
        # Assertions
        assert len(model_cache.models) == 0
        assert len(model_cache.model_sizes) == 0
    
    def test_get_cache_info(self, model_cache):
        """Test cache information retrieval"""
        # Add a model
        model_cache.put("test_model", {"model": Mock()}, 100.0)
        
        # Get cache info
        info = model_cache.get_cache_info()
        
        # Assertions
        assert info["cached_models"] == ["test_model"]
        assert info["cache_size"] == 1
        assert info["max_size"] == 2
        assert info["total_size_mb"] == 100.0


class TestResponseCache:
    """Test cases for ResponseCache"""
    
    @pytest.fixture
    def response_cache(self):
        """ResponseCache instance for testing"""
        return ResponseCache(max_size=100, ttl_hours=1)
    
    def test_put_and_get_response(self, response_cache):
        """Test caching and retrieving responses"""
        # Cache a response
        response_cache.put("Hello", "gemma3_1b", "Hi there!")
        
        # Retrieve response
        cached = response_cache.get("Hello", "gemma3_1b")
        
        # Assertions
        assert cached == "Hi there!"
    
    def test_cache_key_generation(self, response_cache):
        """Test that cache keys are generated correctly"""
        # Same prompt and model should return same response
        response_cache.put("Hello", "gemma3_1b", "Response 1")
        response_cache.put("Hello", "gemma3_1b", "Response 2")  # Should overwrite
        
        cached = response_cache.get("Hello", "gemma3_1b")
        assert cached == "Response 2"
        
        # Different model should be separate cache entry
        response_cache.put("Hello", "gemma3_12b", "Response 3")
        
        cached_1b = response_cache.get("Hello", "gemma3_1b")
        cached_12b = response_cache.get("Hello", "gemma3_12b")
        
        assert cached_1b == "Response 2"
        assert cached_12b == "Response 3"
    
    def test_cache_with_parameters(self, response_cache):
        """Test caching with additional parameters"""
        # Cache with different parameters
        response_cache.put("Hello", "gemma3_1b", "Response 1", max_length=100)
        response_cache.put("Hello", "gemma3_1b", "Response 2", max_length=200)
        
        # Should be different cache entries
        cached_100 = response_cache.get("Hello", "gemma3_1b", max_length=100)
        cached_200 = response_cache.get("Hello", "gemma3_1b", max_length=200)
        
        assert cached_100 == "Response 1"
        assert cached_200 == "Response 2"
    
    def test_ttl_expiration(self, response_cache):
        """Test TTL expiration"""
        # Cache a response
        response_cache.put("Hello", "gemma3_1b", "Response")
        
        # Should be available immediately
        assert response_cache.get("Hello", "gemma3_1b") == "Response"
        
        # Mock expired timestamp
        key = response_cache._generate_key("Hello", "gemma3_1b")
        response_cache.timestamps[key] = datetime.now() - response_cache.ttl - response_cache.ttl
        
        # Should be expired
        assert response_cache.get("Hello", "gemma3_1b") is None
    
    def test_lru_eviction(self, response_cache):
        """Test LRU eviction when cache is full"""
        # Fill cache to capacity
        for i in range(response_cache.max_size):
            response_cache.put(f"prompt_{i}", "gemma3_1b", f"response_{i}")
        
        # Add one more - should evict oldest
        response_cache.put("new_prompt", "gemma3_1b", "new_response")
        
        # First entry should be evicted
        assert response_cache.get("prompt_0", "gemma3_1b") is None
        assert response_cache.get("new_prompt", "gemma3_1b") == "new_response"


class TestOptimizedMLService:
    """Test cases for OptimizedMLService"""
    
    @pytest.fixture
    def ml_service(self):
        """OptimizedMLService instance for testing"""
        return OptimizedMLService()
    
    def test_initialization(self, ml_service):
        """Test service initialization"""
        assert ml_service.model_cache is not None
        assert ml_service.response_cache is not None
        assert ml_service.memory_manager is not None
        assert ml_service.models_loaded == False
    
    def test_initialize_models(self, ml_service):
        """Test model initialization with lazy loading"""
        result = ml_service.initialize_models()
        
        # Should enable lazy loading
        assert ml_service.models_loaded == True
        assert result == {"lazy_loading": True}
    
    def test_normalize_model_name(self, ml_service):
        """Test model name normalization"""
        test_cases = [
            ("Gemma3 1B", "gemma3_1b"),
            ("Gemma3 12B", "gemma3_12b"),
            ("gemma3-1b", "gemma3_1b"),
            ("gemma3-12b", "gemma3_12b"),
            ("1b", "gemma3_1b"),
            ("12b", "gemma3_12b")
        ]
        
        for input_name, expected in test_cases:
            assert ml_service._normalize_model_name(input_name) == expected
    
    def test_get_available_models(self, ml_service):
        """Test getting available models list"""
        models = ml_service.get_available_models()
        
        assert "Gemma3 1B" in models
        assert "Gemma3 12B" in models
    
    def test_get_model_cost(self, ml_service):
        """Test getting model costs"""
        # Mock settings
        with patch('app.ml.optimized_ml_service.settings') as mock_settings:
            mock_settings.gemma3_1b_cost = 10
            mock_settings.gemma3_12b_cost = 50
            
            assert ml_service.get_model_cost("Gemma3 1B") == 10
            assert ml_service.get_model_cost("Gemma3 12B") == 50
            assert ml_service.get_model_cost("unknown") == 1
    
    def test_is_model_available(self, ml_service):
        """Test model availability check"""
        # Should be available for known models
        assert ml_service.is_model_available("Gemma3 1B") == True
        assert ml_service.is_model_available("Gemma3 12B") == True
        
        # Should not be available for unknown models
        assert ml_service.is_model_available("unknown_model") == False
    
    @patch('app.ml.optimized_ml_service.OptimizedMLService._load_model_lazy')
    def test_generate_response_with_cache_hit(self, mock_load_model, ml_service):
        """Test response generation with cache hit"""
        # Mock cached response
        ml_service.response_cache.put("Hello", "gemma3_1b", "Cached response")
        
        # Generate response
        success, response, time_ms = ml_service.generate_response("Hello", "Gemma3 1B")
        
        # Should use cached response
        assert success == True
        assert response == "Cached response"
        assert time_ms > 0
        
        # Should not try to load model
        mock_load_model.assert_not_called()
    
    @patch('app.ml.optimized_ml_service.OptimizedMLService._generate_with_model')
    @patch('app.ml.optimized_ml_service.OptimizedMLService._load_model_lazy')
    def test_generate_response_with_model_loading(self, mock_load_model, mock_generate, ml_service):
        """Test response generation with model loading"""
        # Mock successful model loading
        mock_load_model.return_value = True
        
        # Mock model in cache
        mock_model_data = {
            "model": Mock(),
            "tokenizer": Mock(),
            "generation_config": Mock()
        }
        ml_service.model_cache.put("gemma3_1b", mock_model_data, 100.0)
        
        # Mock generation
        mock_generate.return_value = (True, "Generated response", 1500)
        
        # Generate response
        success, response, time_ms = ml_service.generate_response("Hello", "Gemma3 1B")
        
        # Assertions
        assert success == True
        assert response == "Generated response"
        mock_load_model.assert_called_once_with("gemma3_1b")
        mock_generate.assert_called_once()
    
    def test_get_system_status(self, ml_service):
        """Test system status retrieval"""
        status = ml_service.get_system_status()
        
        # Should contain expected keys
        assert "models_loaded" in status
        assert "available_models" in status
        assert "memory" in status
        assert "model_cache" in status
        assert "response_cache" in status
        assert "usage_stats" in status
        assert "performance" in status
    
    def test_get_model_info(self, ml_service):
        """Test model information retrieval"""
        info = ml_service.get_model_info("Gemma3 1B")
        
        # Should contain expected keys
        assert info["name"] == "Gemma3 1B"
        assert info["normalized_name"] == "gemma3_1b"
        assert "is_loaded" in info
        assert "cost" in info
        assert "usage_count" in info
    
    @patch('app.ml.optimized_ml_service.OptimizedMLService.memory_manager')
    def test_optimize_memory(self, mock_memory_manager, ml_service):
        """Test manual memory optimization"""
        ml_service.optimize_memory()
        
        # Should trigger memory cleanup
        mock_memory_manager.cleanup_memory.assert_called_once()
    
    def test_shutdown(self, ml_service):
        """Test service shutdown"""
        # Start service first
        ml_service.initialize_models()
        
        # Shutdown
        ml_service.shutdown()
        
        # Should stop cleanup thread
        assert ml_service._stop_cleanup == True