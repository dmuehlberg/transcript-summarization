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
            logger.info(f"Starte Zeitzonenkonvertierung für {len(timestamp_series)} Timestamps")
            logger.info(f"Ursprünglicher Datentyp: {timestamp_series.dtype}")
            logger.info(f"Erste 3 Werte vor Konvertierung: {timestamp_series.head(3).tolist()}")
            
            # Konvertiere zu datetime, falls es noch nicht ist
            if timestamp_series.dtype == 'object':
                logger.info("Konvertiere object zu datetime")
                timestamp_series = pd.to_datetime(timestamp_series, errors='coerce')
                logger.info(f"Datentyp nach pd.to_datetime: {timestamp_series.dtype}")
            
            # Prüfe, ob wir gültige Timestamps haben
            if timestamp_series.isna().all():
                logger.warning("Alle Timestamps sind NaN, keine Konvertierung möglich")
                return timestamp_series
            
            # Versuche pandas Zeitzonenkonvertierung
            try:
                # Füge UTC-Zeitzone hinzu (falls nicht vorhanden)
                if timestamp_series.dt.tz is None:
                    logger.info("Füge UTC-Zeitzone hinzu")
                    timestamp_series = timestamp_series.dt.tz_localize('UTC')
                    logger.info(f"Zeitzone nach tz_localize: {timestamp_series.dt.tz}")
                else:
                    logger.info(f"Timestamps haben bereits Zeitzone: {timestamp_series.dt.tz}")
                
                # Konvertiere zur Zielzeitzone
                logger.info(f"Konvertiere zu Zielzeitzone: {self.target_timezone}")
                target_time = timestamp_series.dt.tz_convert(self.target_timezone)
                logger.info(f"Zeitzone nach Konvertierung: {target_time.dt.tz}")
                logger.info(f"Erste 3 Werte nach Konvertierung: {target_time.head(3).tolist()}")
                
                # Prüfe, ob die Konvertierung erfolgreich war
                if target_time.dt.tz is None:
                    raise ValueError("Zeitzonenkonvertierung fehlgeschlagen")
                
                logger.info(f"Zeitzonenkonvertierung erfolgreich: UTC -> {self.target_timezone}")
                return target_time
                
            except Exception as pandas_error:
                logger.warning(f"Pandas Zeitzonenkonvertierung fehlgeschlagen: {str(pandas_error)}")
                logger.info("Versuche manuelle Zeitzonenkonvertierung (+2 Stunden für Berlin)")
                
                # Manuelle Konvertierung: Addiere 2 Stunden für Berlin-Zeit
                if self.target_timezone == 'Europe/Berlin':
                    manual_offset = pd.Timedelta(hours=2)
                    manual_converted = timestamp_series + manual_offset
                    logger.info(f"Manuelle Konvertierung: +2 Stunden hinzugefügt")
                    logger.info(f"Erste 3 Werte nach manueller Konvertierung: {manual_converted.head(3).tolist()}")
                    return manual_converted
                else:
                    # Für andere Zeitzonen: Versuche andere Offsets
                    logger.warning(f"Manuelle Konvertierung für {self.target_timezone} nicht implementiert")
                    return timestamp_series
            
        except Exception as e:
            logger.error(f"Fehler bei der Zeitzonenkonvertierung: {str(e)}")
            logger.error(f"Exception-Typ: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            logger.warning("Verwende ursprüngliche Timestamps")
            return timestamp_series

    def debug_timezone_conversion(self, csv_path: str) -> None:
        """
        Debug-Funktion zum Testen der Zeitzonenkonvertierung.
        
        Args:
            csv_path: Pfad zur CSV-Datei
        """
        try:
            logger.info("=== DEBUG: Zeitzonenkonvertierung ===")
            
            # Lese CSV-Datei
            df = self.read_csv_safely(csv_path)
            logger.info(f"CSV gelesen, {len(df)} Zeilen, {len(df.columns)} Spalten")
            logger.info(f"Spalten: {list(df.columns)}")
            
            # Finde Timestamp-Spalten
            timestamp_columns = []
            for field_name, field_info in self.mapping.items():
                if field_name in df.columns and 'timestamp' in field_info.get('pg_type', '').lower():
                    timestamp_columns.append(field_name)
                    logger.info(f"Timestamp-Spalte gefunden: {field_name} -> {field_info['pg_field']}")
            
            if not timestamp_columns:
                logger.warning("Keine Timestamp-Spalten gefunden!")
                return
            
            # Teste jede Timestamp-Spalte
            for col in timestamp_columns:
                logger.info(f"\n--- Teste Spalte: {col} ---")
                sample_values = df[col].head(3)
                logger.info(f"Beispielwerte: {sample_values.tolist()}")
                logger.info(f"Datentyp: {df[col].dtype}")
                
                # Teste Zeitzonenkonvertierung
                converted = self.convert_utc_to_target_timezone(df[col])
                logger.info(f"Konvertierte Werte: {converted.head(3).tolist()}")
                logger.info(f"Konvertierter Datentyp: {converted.dtype}")
                
                # Prüfe Unterschied
                if len(sample_values) > 0 and len(converted) > 0:
                    original = sample_values.iloc[0]
                    converted_val = converted.iloc[0]
                    if pd.notna(original) and pd.notna(converted_val):
                        try:
                            diff = converted_val - original
                            logger.info(f"Zeitdifferenz: {diff}")
                        except:
                            logger.info("Zeitdifferenz konnte nicht berechnet werden")
            
            logger.info("=== DEBUG ENDE ===")
            
        except Exception as e:
            logger.error(f"Fehler beim Debugging: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    def check_imported_data(self, table_name: str = "calendar_data") -> None:
        """
        Überprüft die importierten Daten in der Datenbank.
        
        Args:
            table_name: Name der Tabelle
        """
        try:
            logger.info("=== DEBUG: Überprüfe importierte Daten ===")
            
            # Finde Timestamp-Spalten
            timestamp_columns = []
            for field_name, field_info in self.mapping.items():
                if 'timestamp' in field_info.get('pg_type', '').lower():
                    timestamp_columns.append(field_info['pg_field'])
            
            if not timestamp_columns:
                logger.warning("Keine Timestamp-Spalten gefunden!")
                return
            
            # Lese die ersten 3 Zeilen aus der DB
            query = f"SELECT {', '.join(timestamp_columns)} FROM {table_name} LIMIT 3"
            
            with self.engine.connect() as conn:
                result = conn.execute(text(query))
                rows = result.fetchall()
                
                logger.info(f"Anzahl Zeilen aus DB: {len(rows)}")
                
                for i, row in enumerate(rows):
                    logger.info(f"Zeile {i+1}:")
                    for j, col in enumerate(timestamp_columns):
                        value = row[j]
                        logger.info(f"  {col}: {value} (Typ: {type(value)})")
            
            logger.info("=== DEBUG ENDE ===")
            
        except Exception as e:
            logger.error(f"Fehler beim Überprüfen der Daten: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

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
            
            # Debug: Zeitzonenkonvertierung testen
            self.debug_timezone_conversion(csv_path)
            
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
            logger.info("=== DEBUG: Vor SQLAlchemy Import ===")
            logger.info(f"DataFrame Shape: {df_mapped.shape}")
            logger.info(f"DataFrame Spalten: {list(df_mapped.columns)}")
            
            # Zeige Timestamp-Spalten vor dem Import
            timestamp_cols = [col for col in df_mapped.columns if 'timestamp' in col.lower()]
            for col in timestamp_cols:
                sample_values = df_mapped[col].head(3)
                logger.info(f"Timestamp-Spalte {col} vor DB-Import: {sample_values.tolist()}")
                logger.info(f"Datentyp: {df_mapped[col].dtype}")
            
            df_mapped.to_sql(table_name, self.engine, if_exists='append', index=False)
            logger.info("=== DEBUG: Nach SQLAlchemy Import ===")
            logger.info(f"Daten erfolgreich in Tabelle {table_name} importiert")
            
            # Überprüfe die importierten Daten
            self.check_imported_data(table_name)
            
        except Exception as e:
            logger.error(f"Fehler beim Importieren der CSV-Datei: {str(e)}")
            raise 