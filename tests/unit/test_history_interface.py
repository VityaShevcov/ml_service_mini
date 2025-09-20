"""
Unit tests for HistoryInterface
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import requests

from app.ui.history_interface import HistoryInterface


class TestHistoryInterface:
    """Test cases for HistoryInterface"""
    
    @pytest.fixture
    def history_interface(self):
        """HistoryInterface instance for testing"""
        return HistoryInterface("http://localhost:8000")
    
    def test_init(self, history_interface):
        """Test HistoryInterface initialization"""
        assert history_interface.api_base_url == "http://localhost:8000"
        assert history_interface.current_token is None
        assert history_interface.current_page == 1
        assert history_interface.page_size == 20
    
    def test_set_auth(self, history_interface):
        """Test setting authentication token"""
        token = "test_token_123"
        history_interface.set_auth(token)
        assert history_interface.current_token == token
    
    @patch('app.ui.history_interface.requests.get')
    def test_get_chat_history_success(self, mock_get, history_interface):
        """Test successful chat history retrieval"""
        # Set auth token
        history_interface.set_auth("test_token")
        
        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "history": [
                {
                    "id": 1,
                    "created_at": "2024-01-01T12:00:00Z",
                    "model_name": "gemma3-1b",
                    "prompt": "Hello world",
                    "response": "Hello! How can I help you?",
                    "credits_charged": 10,
                    "processing_time_ms": 1500
                },
                {
                    "id": 2,
                    "created_at": "2024-01-01T13:00:00Z",
                    "model_name": "gemma3-12b",
                    "prompt": "What is AI?",
                    "response": "AI stands for Artificial Intelligence...",
                    "credits_charged": 50,
                    "processing_time_ms": 3000
                }
            ],
            "total": 2
        }
        mock_get.return_value = mock_response
        
        # Test
        history, status, total = history_interface.get_chat_history()
        
        # Assertions
        assert len(history) == 2
        assert "✅ Loaded 2 of 2 interactions" in status
        assert total == 2
        
        # Check first item format
        first_item = history[0]
        assert len(first_item) == 6  # timestamp, model, prompt, response, credits, time
        assert first_item[1] == "gemma3-1b"
        assert first_item[4] == "10 credits"
        assert first_item[5] == "1500ms"
        
        # Verify API call
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "Authorization" in call_args[1]["headers"]
        assert call_args[1]["headers"]["Authorization"] == "Bearer test_token"
    
    @patch('app.ui.history_interface.requests.get')
    def test_get_chat_history_with_filters(self, mock_get, history_interface):
        """Test chat history retrieval with filters"""
        history_interface.set_auth("test_token")
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "history": [],
            "total": 0
        }
        mock_get.return_value = mock_response
        
        # Test with filters
        history_interface.get_chat_history(
            page=2, page_size=10, model_filter="gemma3-1b",
            date_from="2024-01-01", date_to="2024-01-31"
        )
        
        # Verify API call with parameters
        call_args = mock_get.call_args
        params = call_args[1]["params"]
        assert params["page"] == 2
        assert params["page_size"] == 10
        assert params["model_name"] == "gemma3-1b"
        assert params["date_from"] == "2024-01-01"
        assert params["date_to"] == "2024-01-31"
    
    def test_get_chat_history_not_authenticated(self, history_interface):
        """Test chat history when not authenticated"""
        # Don't set auth token
        history, status, total = history_interface.get_chat_history()
        
        assert history == []
        assert "❌ Not authenticated" in status
        assert total == 0
    
    @patch('app.ui.history_interface.requests.get')
    def test_get_chat_history_api_error(self, mock_get, history_interface):
        """Test chat history with API error"""
        history_interface.set_auth("test_token")
        
        # Mock API error
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        # Test
        history, status, total = history_interface.get_chat_history()
        
        # Assertions
        assert history == []
        assert "❌ Failed to load history: HTTP 500" in status
        assert total == 0
    
    @patch('app.ui.history_interface.requests.get')
    def test_get_chat_history_unauthorized(self, mock_get, history_interface):
        """Test chat history with unauthorized response"""
        history_interface.set_auth("invalid_token")
        
        # Mock unauthorized response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response
        
        # Test
        history, status, total = history_interface.get_chat_history()
        
        # Assertions
        assert history == []
        assert "❌ Authentication failed. Please login again." in status
        assert total == 0
    
    @patch('app.ui.history_interface.requests.get')
    def test_get_available_models_success(self, mock_get, history_interface):
        """Test successful model list retrieval"""
        history_interface.set_auth("test_token")
        
        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "gemma3-1b"},
                {"name": "gemma3-12b"}
            ]
        }
        mock_get.return_value = mock_response
        
        # Test
        models = history_interface.get_available_models()
        
        # Assertions
        assert models == ["all", "gemma3-1b", "gemma3-12b"]
    
    def test_get_available_models_not_authenticated(self, history_interface):
        """Test model list when not authenticated"""
        models = history_interface.get_available_models()
        assert models == ["all"]
    
    @patch('app.ui.history_interface.requests.get')
    def test_get_available_models_fallback(self, mock_get, history_interface):
        """Test model list fallback on API error"""
        history_interface.set_auth("test_token")
        
        # Mock API error
        mock_get.side_effect = Exception("Network error")
        
        # Test
        models = history_interface.get_available_models()
        
        # Should return fallback
        assert models == ["all", "gemma3-1b", "gemma3-12b"]
    
    @patch('app.ui.history_interface.requests.get')
    def test_get_usage_statistics_success(self, mock_get, history_interface):
        """Test successful usage statistics retrieval"""
        history_interface.set_auth("test_token")
        
        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "analytics": {
                "models": {
                    "total_interactions": 100,
                    "total_credits_used": 500,
                    "by_model": {
                        "gemma3-1b": {"count": 70, "credits_used": 350},
                        "gemma3-12b": {"count": 30, "credits_used": 150}
                    }
                },
                "users": {
                    "active_users": 5
                }
            }
        }
        mock_get.return_value = mock_response
        
        # Test
        analytics, status = history_interface.get_usage_statistics(7)
        
        # Assertions
        assert analytics["models"]["total_interactions"] == 100
        assert "✅ Statistics loaded for last 7 days" in status
    
    def test_get_usage_statistics_not_authenticated(self, history_interface):
        """Test usage statistics when not authenticated"""
        analytics, status = history_interface.get_usage_statistics()
        
        assert analytics == {}
        assert "❌ Not authenticated" in status
    
    @patch('app.ui.history_interface.pd.DataFrame')
    def test_export_history_csv_success(self, mock_dataframe, history_interface):
        """Test successful CSV export"""
        history_interface.set_auth("test_token")
        
        # Mock get_chat_history
        with patch.object(history_interface, 'get_chat_history') as mock_get_history:
            mock_get_history.return_value = (
                [["2024-01-01 12:00:00", "gemma3-1b", "Hello", "Hi there", "10 credits", "1500ms"]],
                "Success",
                1
            )
            
            # Mock DataFrame
            mock_df = Mock()
            mock_dataframe.return_value = mock_df
            
            # Test
            filename, status = history_interface.export_history_csv()
            
            # Assertions
            assert filename.endswith(".csv")
            assert "✅ Exported 1 interactions" in status
            mock_df.to_csv.assert_called_once()
    
    def test_export_history_csv_not_authenticated(self, history_interface):
        """Test CSV export when not authenticated"""
        filename, status = history_interface.export_history_csv()
        
        assert filename == ""
        assert "❌ Not authenticated" in status
    
    def test_export_history_csv_no_data(self, history_interface):
        """Test CSV export with no data"""
        history_interface.set_auth("test_token")
        
        # Mock get_chat_history to return empty
        with patch.object(history_interface, 'get_chat_history') as mock_get_history:
            mock_get_history.return_value = ([], "No data", 0)
            
            # Test
            filename, status = history_interface.export_history_csv()
            
            # Assertions
            assert filename == ""
            assert "❌ No data to export" in status
    
    def test_create_interface(self, history_interface):
        """Test interface creation"""
        interface = history_interface.create_interface()
        
        # Should return a Gradio Blocks object
        assert hasattr(interface, 'launch')  # Basic check for Gradio interface
    
    @patch('app.ui.history_interface.requests.get')
    def test_long_text_truncation(self, mock_get, history_interface):
        """Test that long text is properly truncated in display"""
        history_interface.set_auth("test_token")
        
        # Mock API response with long text
        long_text = "A" * 150  # 150 characters
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "history": [
                {
                    "id": 1,
                    "created_at": "2024-01-01T12:00:00Z",
                    "model_name": "gemma3-1b",
                    "prompt": long_text,
                    "response": long_text,
                    "credits_charged": 10,
                    "processing_time_ms": 1500
                }
            ],
            "total": 1
        }
        mock_get.return_value = mock_response
        
        # Test
        history, status, total = history_interface.get_chat_history()
        
        # Check truncation
        first_item = history[0]
        prompt_display = first_item[2]  # prompt column
        response_display = first_item[3]  # response column
        
        assert len(prompt_display) <= 103  # 100 + "..."
        assert len(response_display) <= 103  # 100 + "..."
        assert prompt_display.endswith("...")
        assert response_display.endswith("...")