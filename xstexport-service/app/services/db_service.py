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

# Importiere Zeitzonen-Utilities
from app.utils.timezone_utils import parse_and_convert_timestamp, get_target_timezone

logger = logging.getLogger(__name__)

class DatabaseService:
    def __init__(self, db_config: Dict[str, Any]):
        """Initialisiert den DatabaseService mit der gegebenen Konfiguration."""
        self.db_config = db_config
        self.engine = None
        self.mapping = {}
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
        """Liest eine CSV-Datei sicher ein und behandelt verschiedene Trennzeichen und Encodings."""
        
        # Verschiedene Encodings versuchen
        encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'iso-8859-1', 'windows-1252', 'cp1252']
        
        for encoding in encodings:
            try:
                logger.info(f"Versuche CSV mit Encoding '{encoding}' zu lesen")
                
                # Versuche zuerst mit Semikolon
                try:
                    df = pd.read_csv(file_path, sep=';', encoding=encoding, low_memory=False)
                    logger.info(f"CSV erfolgreich mit Semikolon und Encoding '{encoding}' gelesen")
                    break
                except Exception as e:
                    logger.warning(f"Fehler beim Lesen mit Semikolon und Encoding '{encoding}': {str(e)}, versuche mit Komma")
                    try:
                        df = pd.read_csv(file_path, sep=',', encoding=encoding, low_memory=False)
                        logger.info(f"CSV erfolgreich mit Komma und Encoding '{encoding}' gelesen")
                        break
                    except Exception as e2:
                        logger.warning(f"Fehler beim Lesen mit Komma und Encoding '{encoding}': {str(e2)}")
                        continue
                        
            except Exception as e:
                logger.warning(f"Fehler beim Lesen mit Encoding '{encoding}': {str(e)}")
                continue
        else:
            # Wenn alle Encodings fehlgeschlagen sind
            raise ValueError(f"Konnte CSV-Datei mit keinem der Encodings {encodings} lesen")

        # Bereinige Spaltennamen
        df.columns = df.columns.str.replace('"', '').str.strip()
        
        # Überprüfe, ob die Spaltennamen als einzelner String gelesen wurden
        if len(df.columns) == 1 and ';' in df.columns[0]:
            # Teile die Spaltennamen
            column_names = df.columns[0].split(';')
            # Erstelle ein neues DataFrame mit den korrekten Spaltennamen
            df = pd.read_csv(file_path, sep=';', encoding=encoding, names=column_names, skiprows=1, low_memory=False)
            logger.info("Spaltennamen wurden korrekt aufgeteilt")
        
        return df

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
            logger.info(f"CSV erfolgreich gelesen: {len(df)} Zeilen, {len(df.columns)} Spalten")
            
            # Erstelle Tabelle, falls sie noch nicht existiert
            self.create_table_if_not_exists(table_name)
            
            # Finde übereinstimmende Spalten
            column_mapping = {}
            for csv_col in df.columns:
                if csv_col in self.mapping:
                    column_mapping[csv_col] = self.mapping[csv_col]['pg_field']
            
            logger.info(f"Gefundene Spalten-Mappings: {column_mapping}")
            
            if not column_mapping:
                raise ValueError("Keine übereinstimmenden Spalten zwischen CSV und Mapping gefunden")
            
            # Wähle nur die gemappten Spalten aus
            df_mapped = df[list(column_mapping.keys())].copy()
            df_mapped.columns = [column_mapping[col] for col in df_mapped.columns]
            
            # Konvertiere Datentypen mit Zeitzonenunterstützung
            for field_name, field_info in self.mapping.items():
                if field_name in df.columns:
                    pg_field = field_info['pg_field']
                    pg_type = field_info.get('pg_type', 'TEXT')
                    
                    if pg_type == 'timestamp':
                        # Zeitzonenkonvertierung für Timestamp-Felder
                        logger.info(f"Konvertiere Timestamps für Feld {pg_field} mit Zeitzone {get_target_timezone()}")
                        
                        # Zeige Beispieldaten vor Konvertierung
                        sample_before = df_mapped[pg_field].dropna().head(3).tolist()
                        logger.info(f"Beispieldaten vor Konvertierung ({pg_field}): {sample_before}")
                        
                        # Konvertiere mit Fehlerbehandlung
                        converted_values = []
                        for idx, value in enumerate(df_mapped[pg_field]):
                            try:
                                if pd.notna(value):
                                    converted = parse_and_convert_timestamp(str(value), 'UTC')
                                    converted_values.append(converted)
                                else:
                                    converted_values.append(None)
                            except Exception as e:
                                logger.error(f"Fehler bei Zeile {idx}, Wert '{value}' für Feld {pg_field}: {str(e)}")
                                converted_values.append(None)
                        
                        df_mapped[pg_field] = converted_values
                        
                        # Zeige Beispieldaten nach Konvertierung
                        sample_after = [v for v in converted_values if v is not None][:3]
                        logger.info(f"Beispieldaten nach Konvertierung ({pg_field}): {sample_after}")
                        
                    elif pg_type == 'timestamp with time zone':
                        # Für den Fall, dass noch alte TIMESTAMPTZ Felder existieren
                        df_mapped[pg_field] = pd.to_datetime(df_mapped[pg_field], errors='coerce')
                    elif pg_type == 'INTEGER':
                        df_mapped[pg_field] = pd.to_numeric(df_mapped[pg_field], errors='coerce').fillna(0).astype(int)
                    elif pg_type == 'BOOLEAN':
                        df_mapped[pg_field] = df_mapped[pg_field].map({'true': True, 'false': False, 'True': True, 'False': False})
            
            # Prüfe auf NULL-Werte in Timestamp-Feldern
            timestamp_fields = [field_info['pg_field'] for field_info in self.mapping.values() if field_info.get('pg_type') == 'timestamp']
            for field in timestamp_fields:
                if field in df_mapped.columns:
                    null_count = df_mapped[field].isna().sum()
                    total_count = len(df_mapped[field])
                    logger.info(f"Feld {field}: {null_count}/{total_count} NULL-Werte ({null_count/total_count*100:.1f}%)")
            
            # Importiere in die Datenbank
            df_mapped.to_sql(table_name, self.engine, if_exists='append', index=False)
            logger.info(f"Daten erfolgreich in Tabelle {table_name} importiert")
            
        except Exception as e:
            logger.error(f"Fehler beim Importieren der CSV-Datei: {str(e)}")
            raise

    def insert_calendar_events(self, events: List[Dict[str, Any]], table_name: str = "calendar_data", truncate: bool = False) -> None:
        """
        Fügt eine Liste von Kalender-Events in die Datenbank ein. Optional kann die Tabelle vorher geleert werden.
        """
        try:
            df = pd.DataFrame(events)
            if df.empty:
                logger.warning("Keine Kalender-Events zum Einfügen übergeben.")
                return
            
            # Zeitzonenkonvertierung für start_date und end_date
            if 'start_date' in df.columns:
                logger.info(f"Konvertiere start_date Timestamps mit Zeitzone {get_target_timezone()}")
                df['start_date'] = df['start_date'].apply(
                    lambda x: parse_and_convert_timestamp(str(x), 'UTC') if pd.notna(x) else None
                )
            
            if 'end_date' in df.columns:
                logger.info(f"Konvertiere end_date Timestamps mit Zeitzone {get_target_timezone()}")
                df['end_date'] = df['end_date'].apply(
                    lambda x: parse_and_convert_timestamp(str(x), 'UTC') if pd.notna(x) else None
                )
            
            self.create_table_if_not_exists(table_name)
            if truncate:
                with self.engine.connect() as conn:
                    conn.execute(text(f"TRUNCATE TABLE {table_name}"))
                    conn.commit()
                logger.info(f"Tabelle {table_name} wurde vor dem Import geleert.")
            df.to_sql(table_name, self.engine, if_exists='append', index=False)
            logger.info(f"{len(df)} Kalender-Events erfolgreich in Tabelle {table_name} eingefügt.")
        except Exception as e:
            logger.error(f"Fehler beim Einfügen der Kalender-Events: {str(e)}")
            raise 