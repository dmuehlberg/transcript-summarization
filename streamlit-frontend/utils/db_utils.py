"""
Datenbank-Utilities für AG-Grid Integration.
"""
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def prepare_transcriptions_data(transcriptions: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Bereitet Transkriptionsdaten für AG-Grid vor.
    
    Args:
        transcriptions: Liste der Transkriptionen aus der Datenbank
        
    Returns:
        DataFrame für AG-Grid
    """
    try:
        if transcriptions is None or len(transcriptions) == 0:
            return pd.DataFrame()
        
        # Erstelle DataFrame
        df = pd.DataFrame(transcriptions)
        
        # Formatiere Datumsfelder
        date_columns = ['meeting_start_date', 'created_at', 'recording_date']
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col]).dt.strftime('%Y-%m-%d %H:%M')
        
        # Füge Select Meeting Button hinzu
        df['Select Meeting'] = 'Select Meeting'
        
        # Reorganisiere Spalten für bessere Anzeige
        column_order = [
            'id', 'filename', 'transcription_status', 'set_language',
            'meeting_title', 'meeting_start_date', 'participants',
            'transcription_duration', 'audio_duration', 'created_at',
            'detected_language', 'Select Meeting'
        ]
        
        # Füge fehlende Spalten hinzu
        for col in column_order:
            if col not in df.columns:
                df[col] = ''
        
        # Wähle nur die gewünschten Spalten in der richtigen Reihenfolge
        df = df[column_order]
        
        return df
        
    except Exception as e:
        logger.error(f"Fehler beim Vorbereiten der Transkriptionsdaten: {e}")
        return pd.DataFrame()

def prepare_calendar_data(calendar_data: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Bereitet Kalenderdaten für AG-Grid vor.
    
    Args:
        calendar_data: Liste der Kalenderdaten aus der Datenbank
        
    Returns:
        DataFrame für AG-Grid
    """
    try:
        if calendar_data is None or len(calendar_data) == 0:
            return pd.DataFrame()
        
        # Erstelle DataFrame
        df = pd.DataFrame(calendar_data)
        
        # Formatiere Datumsfelder
        if 'start_date' in df.columns:
            df['start_date'] = pd.to_datetime(df['start_date']).dt.strftime('%Y-%m-%d %H:%M')
        
        # Füge Select Button hinzu
        df['Select'] = 'Select'
        
        # Reorganisiere Spalten
        column_order = ['subject', 'start_date', 'Select']
        df = df[column_order]
        
        return df
        
    except Exception as e:
        logger.error(f"Fehler beim Vorbereiten der Kalenderdaten: {e}")
        return pd.DataFrame()

def format_duration(seconds: Optional[float]) -> str:
    """
    Formatiert Dauer in Sekunden zu einem lesbaren Format.
    
    Args:
        seconds: Dauer in Sekunden
        
    Returns:
        Formatierte Dauer als String
    """
    if seconds is None:
        return ''
    
    try:
        minutes = int(seconds // 60)
        remaining_seconds = int(seconds % 60)
        return f"{minutes:02d}:{remaining_seconds:02d}"
    except:
        return str(seconds)

def get_status_color(status: str) -> str:
    """
    Gibt die Farbe für einen Status zurück.
    
    Args:
        status: Status der Transkription
        
    Returns:
        CSS-Farbe
    """
    status_colors = {
        'completed': '#28a745',
        'processing': '#ffc107',
        'failed': '#dc3545',
        'pending': '#6c757d'
    }
    return status_colors.get(status.lower(), '#6c757d') 