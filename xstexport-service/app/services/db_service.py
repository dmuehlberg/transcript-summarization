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
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import tempfile

logger = logging.getLogger(__name__)

class DatabaseService:
    def __init__(self, db_config: Dict[str, Any]):
        """Initialisiert den DatabaseService mit der gegebenen Konfiguration."""
        self.db_config = db_config
        self.engine = None
        self.mapping = {}
        self.mapping_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'calendar_mapping.json')
        # Zeitzone aus Umgebungsvariable oder Standard (Berlin)
        self.target_timezone = os.getenv('TARGET_TIMEZONE', 'Europe/Berlin')
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

    def convert_utc_to_target_timezone(self, timestamp_series: pd.Series) -> pd.Series:
        """
        Konvertiert UTC-Timestamps zur Zielzeitzone.
        
        Args:
            timestamp_series: Pandas Series mit UTC-Timestamps
            
        Returns:
            Pandas Series mit Timestamps in der Zielzeitzone
        """
        try:
            # Konvertiere zu datetime, falls es noch nicht ist
            if timestamp_series.dtype == 'object':
                timestamp_series = pd.to_datetime(timestamp_series, errors='coerce')
            
            # Füge UTC-Zeitzone hinzu (falls nicht vorhanden)
            if timestamp_series.dt.tz is None:
                timestamp_series = timestamp_series.dt.tz_localize('UTC')
            
            # Konvertiere zur Zielzeitzone
            target_time = timestamp_series.dt.tz_convert(self.target_timezone)
            
            logger.info(f"Zeitzonenkonvertierung erfolgreich: UTC -> {self.target_timezone}")
            return target_time
            
        except Exception as e:
            logger.warning(f"Fehler bei der Zeitzonenkonvertierung: {str(e)}. Verwende ursprüngliche Timestamps.")
            return timestamp_series

    def import_csv_to_db(self, csv_path: str, table_name: str = "calendar_data") -> None:
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
            
            # Finde übereinstimmende Spalten
            column_mapping = {}
            for csv_col in df.columns:
                if csv_col in self.mapping:
                    column_mapping[csv_col] = self.mapping[csv_col]['pg_field']
            
            if not column_mapping:
                raise ValueError("Keine übereinstimmenden Spalten zwischen CSV und Mapping gefunden")
            
            # Wähle nur die gemappten Spalten aus
            df_mapped = df[list(column_mapping.keys())].copy()
            df_mapped.columns = [column_mapping[col] for col in df_mapped.columns]
            
            # Konvertiere Datentypen und Zeitzonen
            for field_name, field_info in self.mapping.items():
                if field_name in df.columns:
                    pg_field = field_info['pg_field']
                    pg_type = field_info.get('pg_type', 'TEXT')
                    
                    if 'timestamp' in pg_type.lower():
                        # Konvertiere Timestamps von UTC zur Zielzeitzone
                        df_mapped[pg_field] = self.convert_utc_to_target_timezone(df_mapped[pg_field])
                        logger.info(f"Timestamp-Feld {pg_field} von UTC zu {self.target_timezone} konvertiert")
                    elif pg_type == 'INTEGER':
                        df_mapped[pg_field] = pd.to_numeric(df_mapped[pg_field], errors='coerce').fillna(0).astype(int)
                    elif pg_type == 'BOOLEAN':
                        df_mapped[pg_field] = df_mapped[pg_field].map({'true': True, 'false': False, 'True': True, 'False': False})
            
            # Importiere in die Datenbank
            df_mapped.to_sql(table_name, self.engine, if_exists='append', index=False)
            logger.info(f"Daten erfolgreich in Tabelle {table_name} importiert")
            
        except Exception as e:
            logger.error(f"Fehler beim Importieren der CSV-Datei: {str(e)}")
            raise 