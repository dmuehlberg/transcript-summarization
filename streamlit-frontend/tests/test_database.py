"""
Unit Tests für Datenbankfunktionen.
"""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Importe
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import DatabaseManager
from utils.db_utils import prepare_transcriptions_data, prepare_calendar_data, format_duration, get_status_color

class TestDatabaseManager:
    """Tests für DatabaseManager."""
    
    @patch('database.psycopg2.pool.SimpleConnectionPool')
    def test_init_connection_pool(self, mock_pool):
        """Test der Connection Pool Initialisierung."""
        mock_pool.return_value = Mock()
        
        db_manager = DatabaseManager()
        
        mock_pool.assert_called_once()
        assert db_manager.connection_pool is not None
    
    @patch('database.psycopg2.pool.SimpleConnectionPool')
    def test_get_connection_context_manager(self, mock_pool):
        """Test des Connection Context Managers."""
        mock_conn = Mock()
        mock_pool.return_value.getconn.return_value = mock_conn
        
        db_manager = DatabaseManager()
        
        with db_manager.get_connection() as conn:
            assert conn == mock_conn
        
        mock_pool.return_value.putconn.assert_called_once_with(mock_conn)
    
    @patch('database.psycopg2.pool.SimpleConnectionPool')
    def test_test_connection_success(self, mock_pool):
        """Test erfolgreicher Datenbankverbindung."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_pool.return_value.getconn.return_value = mock_conn
        
        db_manager = DatabaseManager()
        result = db_manager.test_connection()
        
        assert result is True
        mock_cursor.execute.assert_called_once_with("SELECT 1")
    
    @patch('database.psycopg2.pool.SimpleConnectionPool')
    def test_test_connection_failure(self, mock_pool):
        """Test fehlgeschlagener Datenbankverbindung."""
        mock_pool.return_value.getconn.side_effect = Exception("Connection failed")
        
        db_manager = DatabaseManager()
        result = db_manager.test_connection()
        
        assert result is False
    
    @patch('database.psycopg2.pool.SimpleConnectionPool')
    def test_get_transcriptions(self, mock_pool):
        """Test des Abrufens von Transkriptionen."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            {'id': 1, 'filename': 'test.mp3', 'transcription_status': 'completed'},
            {'id': 2, 'filename': 'test2.mp3', 'transcription_status': 'processing'}
        ]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_pool.return_value.getconn.return_value = mock_conn
        
        db_manager = DatabaseManager()
        result = db_manager.get_transcriptions()
        
        assert len(result) == 2
        assert result[0]['id'] == 1
        assert result[1]['filename'] == 'test2.mp3'
    
    @patch('database.psycopg2.pool.SimpleConnectionPool')
    def test_update_transcription_language(self, mock_pool):
        """Test des Aktualisierens der Sprache."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.rowcount = 1
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_pool.return_value.getconn.return_value = mock_conn
        
        db_manager = DatabaseManager()
        result = db_manager.update_transcription_language(1, "de")
        
        assert result is True
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

class TestDatabaseUtils:
    """Tests für Datenbank-Utilities."""
    
    def test_prepare_transcriptions_data_empty(self):
        """Test mit leeren Transkriptionsdaten."""
        result = prepare_transcriptions_data([])
        assert result.empty
    
    def test_prepare_transcriptions_data_with_data(self):
        """Test mit Transkriptionsdaten."""
        data = [
            {
                'id': 1,
                'filename': 'test.mp3',
                'transcription_status': 'completed',
                'set_language': 'de',
                'meeting_title': 'Test Meeting',
                'meeting_start_date': '2023-01-01 10:00:00',
                'created_at': '2023-01-01 09:00:00'
            }
        ]
        
        result = prepare_transcriptions_data(data)
        
        assert not result.empty
        assert 'Select Meeting' in result.columns
        assert result.iloc[0]['id'] == 1
    
    def test_prepare_calendar_data_empty(self):
        """Test mit leeren Kalenderdaten."""
        result = prepare_calendar_data([])
        assert result.empty
    
    def test_prepare_calendar_data_with_data(self):
        """Test mit Kalenderdaten."""
        data = [
            {
                'subject': 'Test Meeting',
                'start_date': '2023-01-01 10:00:00'
            }
        ]
        
        result = prepare_calendar_data(data)
        
        assert not result.empty
        assert 'Select' in result.columns
        assert result.iloc[0]['subject'] == 'Test Meeting'
    
    def test_format_duration_none(self):
        """Test der Dauer-Formatierung mit None."""
        result = format_duration(None)
        assert result == ''
    
    def test_format_duration_seconds(self):
        """Test der Dauer-Formatierung mit Sekunden."""
        result = format_duration(125)
        assert result == '02:05'
    
    def test_get_status_color(self):
        """Test der Status-Farben."""
        assert get_status_color('completed') == '#28a745'
        assert get_status_color('processing') == '#ffc107'
        assert get_status_color('failed') == '#dc3545'
        assert get_status_color('unknown') == '#6c757d'

if __name__ == "__main__":
    pytest.main([__file__]) 