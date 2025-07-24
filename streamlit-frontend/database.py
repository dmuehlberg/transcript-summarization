"""
Datenbankverbindung und CRUD-Operationen für die Streamlit-App.
"""
import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os
import logging
from typing import List, Dict, Optional, Any
from contextlib import contextmanager

# Lade Umgebungsvariablen
load_dotenv()

# Logger konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Verwaltet die PostgreSQL-Datenbankverbindung mit Connection Pooling."""
    
    def __init__(self):
        """Initialisiert den Database Manager mit Connection Pool."""
        self.connection_pool = None
        self._create_connection_pool()
    
    def _create_connection_pool(self) -> None:
        """Erstellt einen Connection Pool für die Datenbankverbindung."""
        try:
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                host=os.getenv('POSTGRES_HOST', 'n8n'),
                database=os.getenv('POSTGRES_DB', 'n8n'),
                user=os.getenv('POSTGRES_USER'),
                password=os.getenv('POSTGRES_PASSWORD'),
                port=os.getenv('POSTGRES_PORT', 5432),
                cursor_factory=RealDictCursor
            )
            logger.info("Datenbankverbindung erfolgreich erstellt")
        except Exception as e:
            logger.error(f"Fehler beim Erstellen der Datenbankverbindung: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """Context Manager für Datenbankverbindungen."""
        conn = None
        try:
            conn = self.connection_pool.getconn()
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Datenbankfehler: {e}")
            raise
        finally:
            if conn:
                self.connection_pool.putconn(conn)
    
    def test_connection(self) -> bool:
        """Testet die Datenbankverbindung."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    return True
        except Exception as e:
            logger.error(f"Verbindungstest fehlgeschlagen: {e}")
            return False
    
    def get_transcriptions(self) -> List[Dict[str, Any]]:
        """Holt alle Transkriptionen aus der Datenbank."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT 
                            id, filename, transcription_status, set_language,
                            meeting_title, meeting_start_date, participants,
                            transcription_duration, audio_duration, created_at,
                            detected_language, transcript_text, corrected_text,
                            recording_date
                        FROM transcriptions
                        ORDER BY created_at DESC
                    """)
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Transkriptionen: {e}")
            return []
    
    def update_transcription_language(self, transcription_id: int, language: str) -> bool:
        """Aktualisiert die Sprache einer Transkription."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE transcriptions 
                        SET set_language = %s 
                        WHERE id = %s
                    """, (language, transcription_id))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren der Sprache: {e}")
            return False
    
    def get_calendar_data_by_date(self, start_date: str) -> List[Dict[str, Any]]:
        """Holt Kalenderdaten für ein bestimmtes Datum."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT subject, start_date
                        FROM calendar_data
                        WHERE DATE(start_date) = %s
                        ORDER BY start_date
                    """, (start_date,))
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Kalenderdaten: {e}")
            return []
    
    def update_meeting_data(self, transcription_id: int, meeting_title: str, 
                          start_date: str, participants: str) -> bool:
        """Aktualisiert Meeting-Daten einer Transkription."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE transcriptions 
                        SET meeting_title = %s, meeting_start_date = %s, participants = %s
                        WHERE id = %s
                    """, (meeting_title, start_date, participants, transcription_id))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren der Meeting-Daten: {e}")
            return False
    
    def delete_transcriptions(self, transcription_ids: List[int]) -> bool:
        """Löscht mehrere Transkriptionen."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Erstelle Platzhalter für IN-Klausel
                    placeholders = ','.join(['%s'] * len(transcription_ids))
                    cur.execute(f"""
                        DELETE FROM transcriptions 
                        WHERE id IN ({placeholders})
                    """, transcription_ids)
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Fehler beim Löschen der Transkriptionen: {e}")
            return False
    
    def close(self) -> None:
        """Schließt alle Datenbankverbindungen."""
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("Datenbankverbindungen geschlossen")

# Globale Instanz des Database Managers (nur erstellen wenn nicht in Test-Umgebung)
if not os.getenv('TESTING'):
    db_manager = DatabaseManager()
else:
    db_manager = None 