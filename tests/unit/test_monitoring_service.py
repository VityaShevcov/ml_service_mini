"""
Unit tests for MonitoringService
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.services.monitoring_service import MonitoringService
from app.models import User, ModelInteraction, CreditTransaction


class TestMonitoringService:
    """Test cases for MonitoringService"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def monitoring_service(self, mock_db):
        """MonitoringService instance with mocked dependencies"""
        return MonitoringService(mock_db)
    
    @patch('app.services.monitoring_service.psutil')
    def test_get_system_metrics_success(self, mock_psutil, monitoring_service):
        """Test successful system metrics retrieval"""
        # Mock psutil responses
        mock_psutil.cpu_percent.return_value = 45.5
        mock_memory = Mock()
        mock_memory.total = 16 * 1024**3  # 16GB
        mock_memory.used = 8 * 1024**3   # 8GB
        mock_memory.available = 8 * 1024**3  # 8GB
        mock_memory.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_memory
        
        mock_disk = Mock()
        mock_disk.total = 1000 * 1024**3  # 1TB
        mock_disk.used = 500 * 1024**3    # 500GB
        mock_disk.free = 500 * 1024**3    # 500GB
        mock_psutil.disk_usage.return_value = mock_disk
        
        # Test
        metrics = monitoring_service.get_system_metrics()
        
        # Assertions
        assert metrics["cpu"]["percent"] == 45.5
        assert metrics["memory"]["percent"] == 50.0
        assert metrics["memory"]["total_gb"] == 16.0
        assert metrics["disk"]["percent"] == 50.0
        assert "timestamp" in metrics
    
    @patch('app.services.monitoring_service.torch')
    @patch('app.services.monitoring_service.psutil')
    def test_get_system_metrics_with_gpu(self, mock_psutil, mock_torch, monitoring_service):
        """Test system metrics with GPU available"""
        # Mock psutil
        mock_psutil.cpu_percent.return_value = 30.0
        mock_memory = Mock()
        mock_memory.total = 8 * 1024**3
        mock_memory.used = 4 * 1024**3
        mock_memory.available = 4 * 1024**3
        mock_memory.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_memory
        
        mock_disk = Mock()
        mock_disk.total = 500 * 1024**3
        mock_disk.used = 250 * 1024**3
        mock_disk.free = 250 * 1024**3
        mock_psutil.disk_usage.return_value = mock_disk
        
        # Mock torch/GPU
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.device_count.return_value = 1
        mock_torch.cuda.memory_allocated.return_value = 2 * 1024**3  # 2GB
        mock_torch.cuda.memory_reserved.return_value = 3 * 1024**3   # 3GB
        
        mock_props = Mock()
        mock_props.name = "NVIDIA RTX 4090"
        mock_props.total_memory = 24 * 1024**3  # 24GB
        mock_torch.cuda.get_device_properties.return_value = mock_props
        
        # Test
        metrics = monitoring_service.get_system_metrics()
        
        # Assertions
        assert metrics["gpu"]["available"] == True
        assert metrics["gpu"]["device_count"] == 1
        assert len(metrics["gpu"]["devices"]) == 1
        assert metrics["gpu"]["devices"][0]["name"] == "NVIDIA RTX 4090"
        assert metrics["gpu"]["devices"][0]["memory_total_gb"] == 24.0
    
    def test_get_usage_analytics_success(self, monitoring_service, mock_db):
        """Test successful usage analytics retrieval"""
        # Mock interactions
        mock_interactions = [
            Mock(
                created_at=datetime.utcnow() - timedelta(days=1),
                model_name="gemma3-1b",
                credits_charged=10,
                processing_time_ms=1500,
                user_id=1
            ),
            Mock(
                created_at=datetime.utcnow() - timedelta(days=2),
                model_name="gemma3-12b",
                credits_charged=50,
                processing_time_ms=3000,
                user_id=2
            )
        ]
        
        # Mock transactions
        mock_transactions = [
            Mock(
                created_at=datetime.utcnow() - timedelta(days=1),
                amount=-10,
                transaction_type="charge"
            ),
            Mock(
                created_at=datetime.utcnow() - timedelta(days=2),
                amount=-50,
                transaction_type="charge"
            )
        ]
        
        with patch('app.models.crud.ModelInteractionCRUD.get_by_user') as mock_get_interactions, \
             patch('app.models.crud.CreditTransactionCRUD.get_by_type') as mock_get_transactions:
            
            mock_get_interactions.return_value = mock_interactions
            mock_get_transactions.return_value = mock_transactions
            mock_db.query.return_value.scalar.return_value = 2  # total users
            
            # Test
            analytics = monitoring_service.get_usage_analytics(7)
            
            # Assertions
            assert analytics["period"]["days"] == 7
            assert analytics["models"]["total_interactions"] == 2
            assert analytics["models"]["total_credits_used"] == 60
            assert analytics["users"]["total_users"] == 2
            assert analytics["users"]["active_users"] == 2
    
    def test_get_health_status_healthy(self, monitoring_service, mock_db):
        """Test health status when system is healthy"""
        with patch('app.services.monitoring_service.psutil') as mock_psutil:
            # Mock healthy system
            mock_memory = Mock()
            mock_memory.percent = 60.0  # Below 90% threshold
            mock_psutil.virtual_memory.return_value = mock_memory
            
            mock_disk = Mock()
            mock_disk.total = 1000 * 1024**3
            mock_disk.used = 600 * 1024**3  # 60% usage
            mock_psutil.disk_usage.return_value = mock_disk
            
            # Mock successful DB query
            mock_db.execute.return_value = None
            
            # Test
            health = monitoring_service.get_health_status()
            
            # Assertions
            assert health["status"] == "healthy"
            assert len(health["issues"]) == 0
            assert health["components"]["database"] == "healthy"
            assert health["components"]["memory"] == "normal"
            assert health["components"]["disk"] == "normal"
    
    def test_get_health_status_with_issues(self, monitoring_service, mock_db):
        """Test health status when system has issues"""
        with patch('app.services.monitoring_service.psutil') as mock_psutil:
            # Mock system with issues
            mock_memory = Mock()
            mock_memory.percent = 95.0  # Above 90% threshold
            mock_psutil.virtual_memory.return_value = mock_memory
            
            mock_disk = Mock()
            mock_disk.total = 1000 * 1024**3
            mock_disk.used = 950 * 1024**3  # 95% usage
            mock_psutil.disk_usage.return_value = mock_disk
            
            # Mock DB connection failure
            mock_db.execute.side_effect = Exception("Connection failed")
            
            # Test
            health = monitoring_service.get_health_status()
            
            # Assertions
            assert health["status"] in ["warning", "critical"]
            assert len(health["issues"]) > 0
            assert "High memory usage" in health["issues"]
            assert "High disk usage" in health["issues"]
            assert "Database connectivity issues" in health["issues"]
            assert health["components"]["database"] == "unhealthy"
    
    def test_generate_report_success(self, monitoring_service):
        """Test successful report generation"""
        with patch.object(monitoring_service, 'get_system_metrics') as mock_metrics, \
             patch.object(monitoring_service, 'get_usage_analytics') as mock_analytics, \
             patch.object(monitoring_service, 'get_health_status') as mock_health:
            
            # Mock responses
            mock_metrics.return_value = {"cpu": {"percent": 50}}
            mock_analytics.return_value = {"models": {"total_interactions": 100}}
            mock_health.return_value = {"status": "healthy"}
            
            # Test
            report = monitoring_service.generate_report(7)
            
            # Assertions
            assert "report_generated" in report
            assert report["period_days"] == 7
            assert "system_metrics" in report
            assert "usage_analytics" in report
            assert "health_status" in report
            assert "summary" in report
    
    def test_error_handling(self, monitoring_service):
        """Test error handling in monitoring methods"""
        with patch('app.services.monitoring_service.psutil.cpu_percent') as mock_cpu:
            # Mock exception
            mock_cpu.side_effect = Exception("System error")
            
            # Test
            metrics = monitoring_service.get_system_metrics()
            
            # Should return error response
            assert "error" in metrics
            assert metrics["error"] == "Failed to get system metrics"