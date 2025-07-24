"""
Unit Tests für Workflow-Utilities.
"""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock
import requests

# Importe
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.workflow_utils import N8nWorkflowClient

class TestN8nWorkflowClient:
    """Tests für N8nWorkflowClient."""
    
    def test_init(self):
        """Test der Initialisierung."""
        client = N8nWorkflowClient("http://test:5678", 30)
        
        assert client.base_url == "http://test:5678"
        assert client.timeout == 30
        assert client.session is not None
    
    @patch('utils.workflow_utils.requests.Session')
    def test_create_session(self, mock_session_class):
        """Test der Session-Erstellung."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        client = N8nWorkflowClient()
        
        mock_session_class.assert_called_once()
        assert client.session == mock_session
    
    @patch('utils.workflow_utils.requests.Session')
    def test_start_transcription_workflow_success(self, mock_session_class):
        """Test erfolgreicher Workflow-Start."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = N8nWorkflowClient()
        result = client.start_transcription_workflow()
        
        assert result["success"] is True
        assert result["status_code"] == 200
        assert "erfolgreich gestartet" in result["message"]
        mock_session.get.assert_called_once_with(
            "http://n8n:5678/webhook/start-transcription",
            timeout=30
        )
    
    @patch('utils.workflow_utils.requests.Session')
    def test_start_transcription_workflow_failure(self, mock_session_class):
        """Test fehlgeschlagener Workflow-Start."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 500
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = N8nWorkflowClient()
        result = client.start_transcription_workflow()
        
        assert result["success"] is False
        assert result["status_code"] == 500
        assert "fehlgeschlagen" in result["message"]
    
    @patch('utils.workflow_utils.requests.Session')
    def test_start_transcription_workflow_timeout(self, mock_session_class):
        """Test Timeout beim Workflow-Start."""
        mock_session = Mock()
        mock_session.get.side_effect = requests.exceptions.Timeout()
        mock_session_class.return_value = mock_session
        
        client = N8nWorkflowClient()
        result = client.start_transcription_workflow()
        
        assert result["success"] is False
        assert result["status_code"] is None
        assert "Timeout" in result["message"]
    
    @patch('utils.workflow_utils.requests.Session')
    def test_start_transcription_workflow_connection_error(self, mock_session_class):
        """Test Verbindungsfehler beim Workflow-Start."""
        mock_session = Mock()
        mock_session.get.side_effect = requests.exceptions.ConnectionError()
        mock_session_class.return_value = mock_session
        
        client = N8nWorkflowClient()
        result = client.start_transcription_workflow()
        
        assert result["success"] is False
        assert result["status_code"] is None
        assert "Verbindungsfehler" in result["message"]
    
    @patch('utils.workflow_utils.requests.Session')
    def test_start_transcription_workflow_unexpected_error(self, mock_session_class):
        """Test unerwarteter Fehler beim Workflow-Start."""
        mock_session = Mock()
        mock_session.get.side_effect = Exception("Unexpected error")
        mock_session_class.return_value = mock_session
        
        client = N8nWorkflowClient()
        result = client.start_transcription_workflow()
        
        assert result["success"] is False
        assert result["status_code"] is None
        assert "Unerwarteter Fehler" in result["message"]
    
    @patch('utils.workflow_utils.requests.Session')
    def test_test_connection_success(self, mock_session_class):
        """Test erfolgreicher Verbindungstest."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = N8nWorkflowClient()
        result = client.test_connection()
        
        assert result is True
        mock_session.get.assert_called_once_with("http://n8n:5678/", timeout=5)
    
    @patch('utils.workflow_utils.requests.Session')
    def test_test_connection_failure(self, mock_session_class):
        """Test fehlgeschlagener Verbindungstest."""
        mock_session = Mock()
        mock_session.get.side_effect = Exception("Connection failed")
        mock_session_class.return_value = mock_session
        
        client = N8nWorkflowClient()
        result = client.test_connection()
        
        assert result is False
    
    def test_close(self):
        """Test des Schließens der Session."""
        mock_session = Mock()
        client = N8nWorkflowClient()
        client.session = mock_session
        
        client.close()
        
        mock_session.close.assert_called_once()

if __name__ == "__main__":
    pytest.main([__file__]) 