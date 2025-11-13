import os
import json
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import logging
import time
import numpy as np
import csv
import petl as etl
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import tempfile
import pytz
import asyncio
import threading

logger = logging.getLogger(__name__)

class DatabaseService:
    def __init__(self, db_config: Dict[str, Any]):
        """Initialisiert den DatabaseService mit der gegebenen Konfiguration."""
        self.db_config = db_config
        self.engine = None
        self.mapping = {}
        self.external_mapping = {}
        self.mapping_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'calendar_mapping.json')
        self.wait_for_db()
        self.load_mapping()
        self.create_table_if_not_exists()

    def wait_for_db(self, max_retries: int = 5, retry_delay: int = 5) -> None:
        """Wartet auf die Verfügbarkeit der Datenbank."""
        for attempt in range(max_retries):
            try:
                self.engine = create_engine(
                    f"postgresql://{self.db_config['user']}:{self.db_config['password']}@"
                    f"{self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}"
                )
                # Teste die Verbindung
                with self.engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                logger.info("Datenbankverbindung erfolgreich hergestellt")
                return
            except SQLAlchemyError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Verbindungsversuch {attempt + 1} fehlgeschlagen: {str(e)}")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Konnte keine Verbindung zur Datenbank herstellen: {str(e)}")
                    raise

    def load_mapping(self) -> None:
        """Lädt das Mapping aus der JSON-Datei."""
        try:
            with open(self.mapping_file, 'r') as f:
                mapping_data = json.load(f)
                self.mapping = mapping_data.get('mappings', {})
                self.external_mapping = mapping_data.get('external_mappings', {})
            logger.info("Mapping erfolgreich geladen")
        except Exception as e:
            logger.error(f"Fehler beim Laden des Mappings: {str(e)}")
            raise

    def create_table_if_not_exists(self, table_name: str = "calendar_data") -> None:
        """Erstellt die Tabelle, falls sie noch nicht existiert."""
        try:
            # Erstelle die Tabelle basierend auf dem Mapping
            columns = []
            for field_name, field_info in self.mapping.items():
                pg_type = field_info.get('pg_type', 'TEXT')
                columns.append(f"{field_info['pg_field']} {pg_type}")
            
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id SERIAL PRIMARY KEY,
                {', '.join(columns)}
            )
            """
            
            with self.engine.connect() as conn:
                conn.execute(text(create_table_sql))
                conn.commit()
            
            logger.info(f"Tabelle {table_name} wurde erfolgreich erstellt oder existiert bereits")
        except SQLAlchemyError as e:
            logger.error(f"Fehler beim Erstellen der Tabelle: {str(e)}")
            raise

    def read_csv_safely(self, file_path: str) -> pd.DataFrame:
        """Liest eine CSV-Datei sicher ein und behandelt verschiedene Trennzeichen."""
        try:
            # Versuche zuerst mit Semikolon
            df = pd.read_csv(file_path, sep=';', encoding='utf-8-sig', low_memory=False)
            logger.info("CSV erfolgreich mit Semikolon gelesen")
        except Exception as e:
            logger.warning(f"Fehler beim Lesen mit Semikolon: {str(e)}, versuche mit Komma")
            try:
                df = pd.read_csv(file_path, sep=',', encoding='utf-8-sig', low_memory=False)
                logger.info("CSV erfolgreich mit Komma gelesen")
            except Exception as e:
                logger.error(f"Fehler beim Lesen der CSV-Datei: {str(e)}")
                raise

        # Bereinige Spaltennamen
        df.columns = df.columns.str.replace('"', '').str.strip()
        
        # Überprüfe, ob die Spaltennamen als einzelner String gelesen wurden
        if len(df.columns) == 1 and ';' in df.columns[0]:
            # Teile die Spaltennamen
            column_names = df.columns[0].split(';')
            # Erstelle ein neues DataFrame mit den korrekten Spaltennamen
            df = pd.read_csv(file_path, sep=';', encoding='utf-8-sig', names=column_names, skiprows=1, low_memory=False)
            logger.info("Spaltennamen wurden korrekt aufgeteilt")
        
        return df

    def import_csv_to_db(self, csv_path: str, table_name: str = "calendar_data", source: str = "internal") -> None:
        """Importiert Daten aus einer CSV-Datei in die Datenbank."""
        try:
            # Lösche vorhandene Daten
            with self.engine.connect() as conn:
                conn.execute(text(f"TRUNCATE TABLE {table_name}"))
                conn.commit()
            logger.info(f"Vorhandene Daten in Tabelle {table_name} wurden gelöscht")
            
            # Lese CSV-Datei
            df = self.read_csv_safely(csv_path)
            
            # Erstelle Tabelle, falls sie noch nicht existiert
            self.create_table_if_not_exists(table_name)
            
            # Wähle das entsprechende Mapping basierend auf der Quelle
            if source == "external":
                mapping_to_use = self.external_mapping
                logger.info("Verwende externes Mapping für CSV-Import")
            else:
                mapping_to_use = self.mapping
                logger.info("Verwende internes Mapping für CSV-Import")
            
            # Finde übereinstimmende Spalten
            column_mapping = {}
            for csv_col in df.columns:
                if csv_col in mapping_to_use:
                    column_mapping[csv_col] = mapping_to_use[csv_col]['pg_field']
            
            if not column_mapping:
                raise ValueError(f"Keine übereinstimmenden Spalten zwischen CSV und {source}-Mapping gefunden")
            
            # Wähle nur die gemappten Spalten aus
            df_mapped = df[list(column_mapping.keys())].copy()
            df_mapped.columns = [column_mapping[col] for col in df_mapped.columns]
            
            # Konvertiere Datentypen
            for field_name, field_info in mapping_to_use.items():
                if field_name in df.columns:
                    pg_field = field_info['pg_field']
                    pg_type = field_info.get('pg_type', 'TEXT')
                    
                    if pg_type == 'TIMESTAMP' or pg_type == 'timestamp with time zone':
                        # Konvertiere zu datetime und setze UTC Zeitzone
                        df_mapped[pg_field] = pd.to_datetime(df_mapped[pg_field], errors='coerce')
                        # Setze UTC Zeitzone für alle Datumsfelder (da PST-Daten in UTC+0 kommen)
                        # Nur setzen wenn noch keine Zeitzone gesetzt ist
                        if df_mapped[pg_field].dt.tz is None:
                            df_mapped[pg_field] = df_mapped[pg_field].dt.tz_localize('UTC', ambiguous='infer', nonexistent='shift_forward')
                            logger.info(f"Zeitzone für {pg_field} auf UTC gesetzt")
                        else:
                            # Falls bereits Zeitzone gesetzt ist, konvertiere zu UTC
                            df_mapped[pg_field] = df_mapped[pg_field].dt.tz_convert('UTC')
                            logger.info(f"Zeitzone für {pg_field} zu UTC konvertiert")
                    elif pg_type == 'INTEGER':
                        df_mapped[pg_field] = pd.to_numeric(df_mapped[pg_field], errors='coerce').fillna(0).astype(int)
                    elif pg_type == 'BOOLEAN':
                        df_mapped[pg_field] = df_mapped[pg_field].map({'true': True, 'false': False, 'True': True, 'False': False})
            
            # Bereinige Textfelder (Subject, etc.) - entferne Leading/Trailing Whitespaces und Control Characters
            for field_name, field_info in mapping_to_use.items():
                if field_info.get('pg_type') == 'text':  # Nur Textfelder
                    pg_field = field_info['pg_field']
                    
                    if pg_field in df_mapped.columns:
                        # Bereinige Whitespaces und ersetze leere Strings durch None
                        df_mapped[pg_field] = df_mapped[pg_field].astype(str).str.strip()
                        
                        # Entferne nur leading Control Characters (ASCII 0-31, 127), aber behalte Zeilenumbrüche im Text
                        df_mapped[pg_field] = df_mapped[pg_field].str.replace(r'^[\x00-\x1F\x7F]+', '', regex=True)
                        
                        # Ersetze leere Strings und NaN-Werte durch None
                        df_mapped[pg_field] = df_mapped[pg_field].replace(['', 'nan', 'NaN', 'None'], None)
                        
                        # Konvertiere alle verbleibenden NaN-Werte zu None (für pandas NaN)
                        df_mapped[pg_field] = df_mapped[pg_field].where(pd.notna(df_mapped[pg_field]), None)
            
            # Importiere in die Datenbank
            df_mapped.to_sql(table_name, self.engine, if_exists='append', index=False)
            logger.info(f"Daten erfolgreich in Tabelle {table_name} importiert")
            
            # Nach erfolgreichem CSV-Import: LLM-Verarbeitung starten
            try:
                # Rufe die async Methode in einem neuen Event Loop auf
                # (wird in einem separaten Thread ausgeführt, um Konflikte zu vermeiden)
                stats = self._run_async_llm_processing(table_name)
                logger.info(f"LLM-Verarbeitung abgeschlossen: {stats}")
            except Exception as e:
                logger.warning(f"LLM-Verarbeitung fehlgeschlagen, aber CSV-Import erfolgreich: {str(e)}")
                # Nicht als kritischer Fehler behandeln
            
        except Exception as e:
            logger.error(f"Fehler beim Importieren der CSV-Datei: {str(e)}")
            raise
    
    def get_rows_with_meeting_series(self, table_name: str = "calendar_data") -> List[Dict[str, Any]]:
        """
        Ruft alle Zeilen mit gefülltem meeting_series_rhythm ab.
        
        Args:
            table_name: Name der Tabelle (Standard: "calendar_data")
        
        Returns:
            Liste von Dictionaries mit id, meeting_series_rhythm, meeting_series_start_date, meeting_series_end_date
        """
        try:
            sql = text(f"""
                SELECT id, meeting_series_rhythm, meeting_series_start_date, meeting_series_end_date
                FROM {table_name}
                WHERE meeting_series_rhythm IS NOT NULL 
                  AND meeting_series_rhythm != ''
                  AND (meeting_series_start_time IS NULL OR meeting_series_end_time IS NULL)
            """)
            
            with self.engine.connect() as conn:
                result = conn.execute(sql)
                rows = []
                for row in result:
                    rows.append({
                        'id': row[0],
                        'meeting_series_rhythm': row[1],
                        'meeting_series_start_date': row[2],
                        'meeting_series_end_date': row[3]
                    })
                
                logger.info(f"Gefunden: {len(rows)} Zeilen mit meeting_series_rhythm zum Verarbeiten")
                return rows
        except SQLAlchemyError as e:
            logger.error(f"Fehler beim Abrufen der Zeilen mit meeting_series_rhythm: {str(e)}")
            raise
    
    def update_meeting_series_fields(
        self, 
        row_id: int, 
        rrule_data: Dict[str, Any], 
        table_name: str = "calendar_data"
    ) -> None:
        """
        Aktualisiert eine Zeile mit den LLM-generierten RRULE-Feldern.
        
        Args:
            row_id: ID der zu aktualisierenden Zeile
            rrule_data: Dictionary mit RRULE-Feldern
            table_name: Name der Tabelle (Standard: "calendar_data")
        """
        try:
            # Konvertiere Datentypen für PostgreSQL
            start_time = rrule_data.get('meeting_series_start_time')
            end_time = rrule_data.get('meeting_series_end_time')
            frequency = self._convert_to_text(rrule_data.get('meeting_series_frequency'))
            interval = self._convert_to_int(rrule_data.get('meeting_series_interval'))
            weekdays = self._convert_to_text(rrule_data.get('meeting_series_weekdays'))
            monthday = self._convert_to_int(rrule_data.get('meeting_series_monthday'))
            weekday_nth = self._convert_to_int(rrule_data.get('meeting_series_weekday_nth'))
            months = self._convert_to_text(rrule_data.get('meeting_series_months'))
            exceptions = self._convert_to_text(rrule_data.get('meeting_series_exceptions'))
            
            sql = text(f"""
                UPDATE {table_name}
                SET 
                    meeting_series_start_time = :start_time,
                    meeting_series_end_time = :end_time,
                    meeting_series_frequency = :frequency,
                    meeting_series_interval = :interval,
                    meeting_series_weekdays = :weekdays,
                    meeting_series_monthday = :monthday,
                    meeting_series_weekday_nth = :weekday_nth,
                    meeting_series_months = :months,
                    meeting_series_exceptions = :exceptions
                WHERE id = :id
            """)
            
            with self.engine.connect() as conn:
                conn.execute(sql, {
                    'id': row_id,
                    'start_time': start_time,
                    'end_time': end_time,
                    'frequency': frequency if frequency else None,
                    'interval': interval,
                    'weekdays': weekdays if weekdays else None,
                    'monthday': monthday,
                    'weekday_nth': weekday_nth,
                    'months': months if months else None,
                    'exceptions': exceptions
                })
                conn.commit()
            
            logger.debug(f"Zeile {row_id} erfolgreich aktualisiert")
        except SQLAlchemyError as e:
            logger.error(f"Fehler beim Aktualisieren der Zeile {row_id}: {str(e)}")
            raise
    
    async def process_meeting_series_with_llm(
        self, 
        table_name: str = "calendar_data",
        llm_service: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Orchestriert die gesamte LLM-Verarbeitung für Meeting-Series.
        
        Args:
            table_name: Name der Tabelle (Standard: "calendar_data")
            llm_service: Optionaler LLMService (wird erstellt falls None)
        
        Returns:
            Dictionary mit Statistik (total, success, failed)
        """
        if llm_service is None:
            from app.services.llm_service import LLMService
            from app.config.database import get_ollama_config
            ollama_config = get_ollama_config()
            llm_service = LLMService(ollama_config['base_url'], ollama_config['model'])
        
        rows = self.get_rows_with_meeting_series(table_name)
        stats = {'total': len(rows), 'success': 0, 'failed': 0}
        
        for row in rows:
            try:
                # Konvertiere start_date und end_date zu Strings falls nötig
                start_date = row['meeting_series_start_date']
                end_date = row['meeting_series_end_date']
                
                if isinstance(start_date, datetime):
                    start_date = start_date.isoformat()
                elif start_date is None:
                    start_date = ""
                else:
                    start_date = str(start_date)
                
                if isinstance(end_date, datetime):
                    end_date = end_date.isoformat()
                elif end_date is None:
                    end_date = ""
                else:
                    end_date = str(end_date)
                
                rrule_data = await llm_service.parse_meeting_series(
                    row['meeting_series_rhythm'],
                    start_date,
                    end_date
                )
                self.update_meeting_series_fields(row['id'], rrule_data, table_name)
                stats['success'] += 1
            except Exception as e:
                logger.error(f"Fehler bei LLM-Verarbeitung für Zeile {row['id']}: {str(e)}")
                stats['failed'] += 1
        
        return stats
    
    def _convert_to_int(self, value: Any) -> Optional[int]:
        """Hilfsmethode zur Konvertierung zu Integer."""
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    
    def _convert_to_text(self, value: Any) -> Optional[str]:
        """Hilfsmethode zur Konvertierung zu Text."""
        if value is None or value == "":
            return None
        return str(value).strip()
    
    def _run_async_llm_processing(self, table_name: str) -> Dict[str, Any]:
        """
        Führt die async LLM-Verarbeitung in einem neuen Event Loop aus.
        Diese Methode ist synchron und kann von synchronen Methoden aufgerufen werden.
        """
        def run_in_thread():
            # Erstelle einen neuen Event Loop für diesen Thread
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                return new_loop.run_until_complete(self.process_meeting_series_with_llm(table_name))
            finally:
                new_loop.close()
        
        # Führe die async Funktion in einem separaten Thread aus
        result_container = {}
        exception_container = {}
        
        def thread_target():
            try:
                result_container['result'] = run_in_thread()
            except Exception as e:
                exception_container['exception'] = e
        
        thread = threading.Thread(target=thread_target)
        thread.start()
        thread.join()
        
        if 'exception' in exception_container:
            raise exception_container['exception']
        
        return result_container['result'] 