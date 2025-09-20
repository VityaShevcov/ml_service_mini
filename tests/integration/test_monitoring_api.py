"""
Integration tests for monitoring API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock

from main import app
from app.database import get_db
from tests.conftest import override_get_db, create_test_user, get_test_token


client = TestClient(app)


class TestMonitoringAPI:
    """Test cases for monitoring API endpoints"""
    
    def setup_method(self):
        """Setup test dependencies"""
        app.dependency_overrides[get_db] = override_get_db
    
    def teardown_method(self):
        """Cleanup after tests"""
        app.dependency_overrides.clear()
    
    def test_health_endpoint_public(self):
        """Test public health endpoint"""
        with patch('app.services.monitoring_service.MonitoringService.get_health_status') as mock_health:
            mock_health.return_value = {
                "status": "healthy",
                "timestamp": "2024-01-01T00:00:00",
                "uptime_seconds": 3600,
                "issues": [],
                "components": {
                    "database": "healthy",
                    "gpu": "available",
                    "memory": "normal",
                    "disk": "normal"
                }
            }
            
            response = client.get("/monitoring/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["components"]["database"] == "healthy"
    
    def test_health_endpoint_error(self):
        """Test health endpoint when service fails"""
        with patch('app.services.monitoring_service.MonitoringService.get_health_status') as mock_health:
            mock_health.side_effect = Exception("Service error")
            
            response = client.get("/monitoring/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "error"
            assert "error" in data
    
    def test_metrics_endpoint_authenticated(self):
        """Test metrics endpoint with authentication"""
        # Create test user and get token
        user = create_test_user()
        token = get_test_token(user.email)
        
        with patch('app.services.monitoring_service.MonitoringService.get_system_metrics') as mock_metrics:
            mock_metrics.return_value = {
                "timestamp": "2024-01-01T00:00:00",
                "uptime_seconds": 3600,
                "cpu": {"percent": 45.5, "count": 8},
                "memory": {
                    "total_gb": 16.0,
                    "used_gb": 8.0,
                    "available_gb": 8.0,
                    "percent": 50.0
                },
                "disk": {
                    "total_gb": 1000.0,
                    "used_gb": 500.0,
                    "free_gb": 500.0,
                    "percent": 50.0
                },
                "gpu": {"available": False}
            }
            
            response = client.get(
                "/monitoring/metrics",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
            assert "metrics" in data
            assert data["metrics"]["cpu"]["percent"] == 45.5
    
    def test_metrics_endpoint_unauthorized(self):
        """Test metrics endpoint without authentication"""
        response = client.get("/monitoring/metrics")
        
        assert response.status_code == 401
    
    def test_analytics_endpoint_success(self):
        """Test analytics endpoint with valid parameters"""
        user = create_test_user()
        token = get_test_token(user.email)
        
        with patch('app.services.monitoring_service.MonitoringService.get_usage_analytics') as mock_analytics:
            mock_analytics.return_value = {
                "period": {
                    "start_date": "2024-01-01T00:00:00",
                    "end_date": "2024-01-08T00:00:00",
                    "days": 7
                },
                "models": {
                    "total_interactions": 150,
                    "total_credits_used": 750,
                    "avg_processing_time_ms": 2500.0,
                    "by_model": {
                        "gemma3-1b": {"count": 100, "credits_used": 500},
                        "gemma3-12b": {"count": 50, "credits_used": 250}
                    }
                },
                "users": {
                    "total_users": 10,
                    "active_users": 8,
                    "activity_rate": 80.0
                },
                "credits": {
                    "total_charged": 750,
                    "total_added": 1000,
                    "net_usage": -250
                }
            }
            
            response = client.get(
                "/monitoring/analytics?days=7",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
            assert "analytics" in data
            assert data["analytics"]["models"]["total_interactions"] == 150
    
    def test_analytics_endpoint_invalid_days(self):
        """Test analytics endpoint with invalid days parameter"""
        user = create_test_user()
        token = get_test_token(user.email)
        
        # Test days > 30
        response = client.get(
            "/monitoring/analytics?days=35",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 422
        
        # Test days < 1
        response = client.get(
            "/monitoring/analytics?days=0",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 422
    
    def test_report_endpoint_success(self):
        """Test report generation endpoint"""
        user = create_test_user()
        token = get_test_token(user.email)
        
        with patch('app.services.monitoring_service.MonitoringService.generate_report') as mock_report:
            mock_report.return_value = {
                "report_generated": "2024-01-01T00:00:00",
                "period_days": 7,
                "system_metrics": {"cpu": {"percent": 50}},
                "usage_analytics": {"models": {"total_interactions": 100}},
                "health_status": {"status": "healthy"},
                "summary": {
                    "key_metrics": {
                        "daily_avg_interactions": 14.3,
                        "daily_avg_credits": 107.1,
                        "active_users": 8
                    },
                    "insights": [
                        "System processed 100 interactions in 7 days",
                        "Total credits consumed: 750",
                        "Active users: 8"
                    ]
                }
            }
            
            response = client.get(
                "/monitoring/report?days=7",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
            assert "report" in data
            assert data["report"]["period_days"] == 7
    
    def test_logs_endpoint_success(self):
        """Test error logs endpoint"""
        user = create_test_user()
        token = get_test_token(user.email)
        
        with patch('app.services.monitoring_service.MonitoringService.get_error_logs') as mock_logs:
            mock_logs.return_value = [
                {
                    "timestamp": "2024-01-01T00:00:00",
                    "level": "ERROR",
                    "message": "Model loading failed",
                    "component": "ml_service"
                },
                {
                    "timestamp": "2024-01-01T01:00:00",
                    "level": "WARNING",
                    "message": "High memory usage detected",
                    "component": "monitoring_service"
                }
            ]
            
            response = client.get(
                "/monitoring/logs?hours=24&limit=100",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
            assert "logs" in data
            assert data["count"] == 2
            assert len(data["logs"]) == 2
    
    def test_status_endpoint_success(self):
        """Test service status endpoint"""
        user = create_test_user()
        token = get_test_token(user.email)
        
        with patch('app.services.monitoring_service.MonitoringService.get_health_status') as mock_health, \
             patch('app.services.monitoring_service.MonitoringService.get_system_metrics') as mock_metrics, \
             patch('app.services.monitoring_service.MonitoringService.get_usage_analytics') as mock_analytics:
            
            mock_health.return_value = {"status": "healthy"}
            mock_metrics.return_value = {
                "cpu": {"percent": 45},
                "memory": {"percent": 60},
                "disk": {"percent": 70},
                "gpu": {"available": True}
            }
            mock_analytics.return_value = {
                "models": {"total_interactions": 50},
                "credits": {"total_charged": 250},
                "users": {"active_users": 5}
            }
            
            response = client.get(
                "/monitoring/status",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
            assert "status" in data
            assert data["status"]["health"]["status"] == "healthy"
            assert data["status"]["system"]["cpu_percent"] == 45
            assert data["status"]["usage_24h"]["interactions"] == 50
    
    def test_monitoring_service_error_handling(self):
        """Test error handling in monitoring endpoints"""
        user = create_test_user()
        token = get_test_token(user.email)
        
        with patch('app.services.monitoring_service.MonitoringService.get_system_metrics') as mock_metrics:
            mock_metrics.side_effect = Exception("Service error")
            
            response = client.get(
                "/monitoring/metrics",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            assert response.status_code == 500
            data = response.json()
            assert "Failed to get system metrics" in data["detail"]