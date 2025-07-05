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
        
        # Lese die ersten Zeilen als Text um das Format zu analysieren
        with open(file_path, 'rb') as f:
            raw_content = f.read()
        
        # Versuche verschiedene Encodings für die Analyse
        encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'iso-8859-1', 'windows-1252', 'cp1252']
        text_content = None
        
        for encoding in encodings:
            try:
                text_content = raw_content.decode(encoding, errors='replace')
                logger.info(f"Erfolgreich mit Encoding '{encoding}' dekodiert")
                break
            except Exception as e:
                logger.warning(f"Fehler beim Dekodieren mit '{encoding}': {str(e)}")
                continue
        
        if text_content is None:
            # Fallback: Verwende latin-1 mit Fehlerersetzung
            text_content = raw_content.decode('latin-1', errors='replace')
            logger.info("Verwende Fallback-Encoding latin-1 mit Fehlerersetzung")
        
        # Analysiere die ersten Zeilen
        lines = text_content.split('\n')[:20]  # Erste 20 Zeilen
        logger.info(f"Analysiere erste {len(lines)} Zeilen")
        
        # Automatische Trennzeichen-Erkennung
        separators = [';', ',', '\t', '|']
        detected_sep = None
        max_fields = 0
        
        # Überspringe leere Zeilen und suche nach der ersten Datenzeile
        data_lines = []
        for line in lines:
            if line.strip() and not line.strip().startswith('#'):
                data_lines.append(line)
                if len(data_lines) >= 5:  # Analysiere mindestens 5 Datenzeilen
                    break
        
        logger.info(f"Gefundene {len(data_lines)} Datenzeilen für Trennzeichen-Analyse")
        
        for sep in separators:
            field_counts = []
            for line in data_lines:
                if line.strip():
                    field_count = len(line.split(sep))
                    field_counts.append(field_count)
            
            if field_counts:
                avg_fields = sum(field_counts) / len(field_counts)
                consistency = max(field_counts) - min(field_counts)
                
                logger.info(f"Trennzeichen '{sep}': Durchschnitt {avg_fields:.1f} Felder, Konsistenz {consistency}")
                
                # Bevorzuge Semikolon für deutsche CSV-Dateien
                if sep == ';' and avg_fields > 5:
                    detected_sep = sep
                    max_fields = avg_fields
                    logger.info(f"Semikolon bevorzugt: {avg_fields:.1f} Felder")
                    break
                elif avg_fields > max_fields and consistency <= 5:  # Erhöhe Toleranz für Inkonsistenz
                    max_fields = avg_fields
                    detected_sep = sep
        
        if detected_sep is None:
            detected_sep = ';'  # Fallback
            logger.warning("Konnte Trennzeichen nicht automatisch erkennen, verwende ';'")
        
        logger.info(f"Verwende Trennzeichen '{detected_sep}'")
        
        # Jetzt versuche pandas mit dem erkannten Trennzeichen
        df = None
        for encoding in encodings:
            try:
                logger.info(f"Versuche pandas mit Encoding '{encoding}' und Trennzeichen '{detected_sep}'")
                
                # Versuche mit verschiedenen pandas-Optionen
                try:
                    df = pd.read_csv(file_path, sep=detected_sep, encoding=encoding, 
                                   engine='python', on_bad_lines='skip')
                    logger.info(f"Erfolgreich mit pandas engine='python' gelesen")
                    break
                except Exception as e:
                    logger.warning(f"Fehler mit engine='python': {str(e)}, versuche engine='c'")
                    try:
                        df = pd.read_csv(file_path, sep=detected_sep, encoding=encoding,
                                       engine='c', on_bad_lines='skip')
                        logger.info(f"Erfolgreich mit pandas engine='c' gelesen")
                        break
                    except Exception as e2:
                        logger.warning(f"Fehler mit engine='c': {str(e2)}")
                        continue
                        
            except Exception as e:
                logger.warning(f"Fehler beim Lesen mit Encoding '{encoding}': {str(e)}")
                continue
        
        if df is None:
            # Letzter Versuch: Manuelles Parsing
            logger.warning("Pandas fehlgeschlagen, versuche manuelles Parsing")
            df = self._manual_csv_parse(file_path, detected_sep)

        # Bereinige Spaltennamen
        df.columns = df.columns.str.replace('"', '').str.strip()
        
        # Überprüfe, ob die Spaltennamen als einzelner String gelesen wurden
        if len(df.columns) == 1:
            logger.warning("Nur eine Spalte gefunden, versuche Header-Zeile zu erkennen")
            first_column = df.columns[0]
            
            # Prüfe, ob die Spalte Kommas enthält (wahrscheinlich CSV-Header)
            if ',' in first_column:
                logger.info("Spalte enthält Kommas, versuche Aufteilung der Spaltennamen")
                # Entferne Anführungszeichen und teile an Kommas
                column_names = [col.strip().replace('"', '') for col in first_column.split(',')]
                logger.info(f"Spaltennamen aufgeteilt: {len(column_names)} Spalten gefunden")
                
                # Zeige die ersten paar Spaltennamen zur Überprüfung
                logger.info(f"Erste 5 Spaltennamen: {column_names[:5]}")
                
                try:
                    # Erstelle ein neues DataFrame mit den korrekten Spaltennamen
                    df = pd.read_csv(file_path, sep=detected_sep, encoding=encoding, 
                                   names=column_names, skiprows=1, low_memory=False, 
                                   on_bad_lines='skip', error_bad_lines=False)
                    logger.info(f"Spaltennamen wurden korrekt aufgeteilt: {len(df.columns)} Spalten")
                except Exception as e:
                    logger.error(f"Fehler beim Neulesen mit aufgeteilten Spaltennamen: {str(e)}")
                    # Fallback: Manuelles Parsing mit den aufgeteilten Spaltennamen
                    logger.info("Versuche manuelles Parsing mit aufgeteilten Spaltennamen")
                    df = self._manual_csv_parse_with_headers(file_path, detected_sep, column_names)
            else:
                logger.error("Konnte keine gültige Header-Zeile finden")
        
        return df

    def _manual_csv_parse(self, file_path: str, separator: str) -> pd.DataFrame:
        """Manuelles CSV-Parsing als Fallback."""
        logger.info(f"Starte manuelles CSV-Parsing mit Trennzeichen '{separator}'")
        
        try:
            with open(file_path, 'rb') as f:
                raw_content = f.read()
            
            # Verwende latin-1 mit Fehlerersetzung
            text_content = raw_content.decode('latin-1', errors='replace')
            lines = text_content.split('\n')
            
            logger.info(f"Datei hat {len(lines)} Zeilen")
            
            # Finde die erste gültige Zeile (Header)
            header_line = None
            data_start = 0
            
            for i, line in enumerate(lines[:100]):  # Begrenze auf erste 100 Zeilen für Header-Suche
                if line.strip() and separator in line:
                    fields = line.split(separator)
                    if len(fields) > 1:
                        header_line = line
                        data_start = i + 1
                        logger.info(f"Header gefunden in Zeile {i}: {len(fields)} Felder")
                        break
            
            if header_line is None:
                logger.error("Konnte keine gültige Header-Zeile finden")
                # Fallback: Erstelle einfache Spaltennamen
                headers = [f"Column_{i}" for i in range(10)]
                logger.info(f"Verwende Fallback-Header: {headers}")
            else:
                # Parse Header
                headers = [h.strip().replace('"', '') for h in header_line.split(separator)]
                logger.info(f"Gefundene Spalten: {headers}")
            
            # Parse Daten mit Begrenzung
            data = []
            max_lines = min(1000, len(lines))  # Begrenze auf 1000 Zeilen
            
            for i, line in enumerate(lines[data_start:max_lines], data_start):
                if line.strip():
                    try:
                        fields = line.split(separator)
                        # Stelle sicher, dass wir genug Felder haben
                        while len(fields) < len(headers):
                            fields.append('')
                        # Schneide ab falls zu viele Felder
                        fields = fields[:len(headers)]
                        
                        data.append(fields)
                        
                        # Logge Fortschritt
                        if len(data) % 100 == 0:
                            logger.info(f"{len(data)} Zeilen geparst")
                            
                    except Exception as e:
                        logger.warning(f"Fehler beim Parsen von Zeile {i}: {str(e)}")
                        continue
            
            logger.info(f"Manuell {len(data)} Zeilen geparst")
            
            if not data:
                logger.warning("Keine Daten gefunden, erstelle leeres DataFrame")
                return pd.DataFrame(columns=headers)
            
            return pd.DataFrame(data, columns=headers)
            
        except Exception as e:
            logger.error(f"Kritischer Fehler beim manuellen Parsing: {str(e)}")
            # Fallback: Leeres DataFrame
            return pd.DataFrame(columns=[f"Column_{i}" for i in range(5)])

    def _manual_csv_parse_with_headers(self, file_path: str, separator: str, headers: list) -> pd.DataFrame:
        """Manuelles CSV-Parsing mit vorgegebenen Headern."""
        logger.info(f"Starte manuelles CSV-Parsing mit {len(headers)} Headern")
        
        try:
            with open(file_path, 'rb') as f:
                raw_content = f.read()
            
            # Verwende latin-1 mit Fehlerersetzung
            text_content = raw_content.decode('latin-1', errors='replace')
            lines = text_content.split('\n')
            
            logger.info(f"Datei hat {len(lines)} Zeilen")
            
            # Überspringe die Header-Zeile und parse Daten
            data = []
            max_lines = min(1000, len(lines))  # Begrenze auf 1000 Zeilen für Performance
            
            for i, line in enumerate(lines[1:max_lines], 1):  # Überspringe erste Zeile (Header)
                if line.strip():
                    try:
                        fields = line.split(separator)
                        # Stelle sicher, dass wir genug Felder haben
                        while len(fields) < len(headers):
                            fields.append('')
                        # Schneide ab falls zu viele Felder
                        fields = fields[:len(headers)]
                        
                        data.append(fields)
                        
                        # Logge Fortschritt
                        if len(data) % 100 == 0:
                            logger.info(f"{len(data)} Zeilen geparst")
                            
                    except Exception as e:
                        logger.warning(f"Fehler beim Parsen von Zeile {i}: {str(e)}")
                        continue
            
            logger.info(f"Manuell {len(data)} Zeilen geparst")
            
            if not data:
                logger.warning("Keine Daten gefunden, erstelle leeres DataFrame")
                return pd.DataFrame(columns=headers)
            
            return pd.DataFrame(data, columns=headers)
            
        except Exception as e:
            logger.error(f"Kritischer Fehler beim manuellen Parsing: {str(e)}")
            # Fallback: Leeres DataFrame mit den Headern
            return pd.DataFrame(columns=headers)

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
            
            # Debug: Zeige die ersten Zeilen und Spaltennamen
            logger.info(f"Spaltennamen: {list(df.columns)}")
            if len(df) > 0:
                logger.info(f"Erste Zeile: {df.iloc[0].tolist()}")
                if len(df) > 1:
                    logger.info(f"Zweite Zeile: {df.iloc[1].tolist()}")
            
            logger.info(f"Tabelle calendar_data wurde erfolgreich erstellt oder existiert bereits")
            
            # Erstelle Tabelle, falls sie noch nicht existiert
            self.create_table_if_not_exists(table_name)
            
            # Finde übereinstimmende Spalten
            matching_columns = {}
            logger.info(f"Suche nach Spalten-Mappings...")
            logger.info(f"CSV-Spalten ({len(df.columns)}): {list(df.columns)}")
            logger.info(f"Mapping-Erwartungen: {[info['csv_field'] for info in self.mapping.values()]}")
            
            for csv_col in df.columns:
                csv_col_clean = csv_col.strip().replace('"', '')
                csv_col_lower = csv_col_clean.lower()
                
                for mapping_key, mapping_info in self.mapping.items():
                    mapping_field_clean = mapping_info['csv_field'].strip()
                    mapping_field_lower = mapping_field_clean.lower()
                    
                    if mapping_field_lower == csv_col_lower:
                        matching_columns[mapping_key] = csv_col
                        logger.info(f"Spalte gefunden: '{csv_col_clean}' -> '{mapping_key}'")
                        break
            
            logger.info(f"Gefundene Spalten-Mappings: {matching_columns}")
            
            if not matching_columns:
                # Versuche Fuzzy-Matching für wichtige Felder
                logger.warning("Keine exakten Matches gefunden, versuche Fuzzy-Matching")
                important_fields = ['Subject', 'Start Date', 'End Date', 'Sent Representing Name']
                
                for field in important_fields:
                    field_lower = field.lower()
                    for csv_col in df.columns:
                        csv_col_clean = csv_col.strip().replace('"', '')
                        csv_col_lower = csv_col_clean.lower()
                        
                        if field_lower in csv_col_lower or csv_col_lower in field_lower:
                            # Finde das entsprechende Mapping
                            for mapping_key, mapping_info in self.mapping.items():
                                if mapping_info['csv_field'].lower() == field_lower:
                                    matching_columns[mapping_key] = csv_col
                                    logger.info(f"Fuzzy-Match gefunden: '{csv_col_clean}' -> '{mapping_key}'")
                                    break
                            break
                
                if not matching_columns:
                    raise ValueError("Keine übereinstimmenden Spalten zwischen CSV und Mapping gefunden")
            
            # Debug: Zeige die gefundenen Spalten
            logger.info(f"Gefundene Spalten-Mappings: {matching_columns}")
            logger.info(f"DataFrame Spalten: {list(df.columns)}")
            logger.info(f"DataFrame Shape: {df.shape}")
            
            # Wähle nur die gemappten Spalten aus
            available_columns = []
            available_mappings = {}
            
            for mapping_key, csv_col in matching_columns.items():
                if csv_col in df.columns:
                    available_columns.append(csv_col)
                    available_mappings[mapping_key] = csv_col
                    logger.info(f"Spalte verfügbar: {csv_col} -> {mapping_key}")
                else:
                    logger.warning(f"Spalte nicht verfügbar: {csv_col}")
            
            if not available_columns:
                raise ValueError("Keine der gemappten Spalten ist im DataFrame verfügbar")
            
            logger.info(f"Verfügbare Spalten: {available_columns}")
            df_mapped = df[available_columns].copy()
            df_mapped.columns = [mapping_key for mapping_key in available_mappings.keys()]
            
            # Konvertiere Datentypen mit Zeitzonenunterstützung
            for field_name, field_info in self.mapping.items():
                if field_name in df_mapped.columns and field_name in available_mappings:
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
                if field in df_mapped.columns and field in available_mappings:
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