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
                        
                        df_mapped[pg_field] = df_mapped[pg_field].replace('', None)
            
            # Importiere in die Datenbank
            df_mapped.to_sql(table_name, self.engine, if_exists='append', index=False)
            logger.info(f"Daten erfolgreich in Tabelle {table_name} importiert")
            
        except Exception as e:
            logger.error(f"Fehler beim Importieren der CSV-Datei: {str(e)}")
            raise 