"""
Basic test for ML service functionality
"""
import torch
from app.ml.ml_service import MLService
from app.ml.model_loader import ModelLoader


def test_cuda_availability():
    """Test CUDA availability"""
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA device: {torch.cuda.get_device_name(0)}")
        print(f"CUDA memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    return torch.cuda.is_available()


def test_model_loader():
    """Test ModelLoader basic functionality"""
    print("\n=== Testing ModelLoader ===")
    
    loader = ModelLoader()
    print(f"Device: {loader.device}")
    print(f"Max memory GB: {loader.max_memory_gb}")
    print(f"Current memory usage: {loader.get_memory_usage():.2f} GB")
    
    # Test memory check
    has_memory = loader.check_memory_available(4.0)
    print(f"Has 4GB available: {has_memory}")
    
    return True


def test_ml_service():
    """Test MLService basic functionality"""
    print("\n=== Testing MLService ===")
    
    service = MLService()
    print(f"Models loaded: {service.models_loaded}")
    
    # Test model name normalization
    normalized = service._normalize_model_name("Gemma3 1B")
    print(f"Normalized 'Gemma3 1B': {normalized}")
    
    # Test model costs
    cost_1b = service.get_model_cost("Gemma3 1B")
    cost_12b = service.get_model_cost("Gemma3 12B")
    print(f"Cost 1B: {cost_1b}, Cost 12B: {cost_12b}")
    
    # Test system status
    status = service.get_system_status()
    print(f"System status: {status}")
    
    return True


def main():
    """Run all tests"""
    print("=== ML Service Basic Tests ===")
    
    try:
        # Test CUDA
        cuda_ok = test_cuda_availability()
        
        # Test ModelLoader
        loader_ok = test_model_loader()
        
        # Test MLService
        service_ok = test_ml_service()
        
        print(f"\n=== Results ===")
        print(f"CUDA: {'✓' if cuda_ok else '✗'}")
        print(f"ModelLoader: {'✓' if loader_ok else '✗'}")
        print(f"MLService: {'✓' if service_ok else '✗'}")
        
        if cuda_ok and loader_ok and service_ok:
            print("\n🎉 All basic tests passed!")
            return True
        else:
            print("\n❌ Some tests failed!")
            return False
            
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        return False


if __name__ == "__main__":
    main()