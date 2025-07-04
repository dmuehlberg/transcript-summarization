import os
import pytz
from datetime import datetime
from typing import Optional, Union
import logging

logger = logging.getLogger(__name__)

def get_target_timezone() -> str:
    """
    Liest die Zielzeitzone aus der Umgebungsvariable TIMEZONE.
    Standard ist 'Europe/Berlin' (UTC+2).
    """
    timezone = os.getenv('TIMEZONE', 'Europe/Berlin')
    logger.info(f"Verwende Zielzeitzone: {timezone}")
    return timezone

def convert_utc_to_local(utc_datetime: Union[datetime, str], source_timezone: str = 'UTC') -> Optional[datetime]:
    """
    Konvertiert ein UTC-Datetime zu lokaler Zeit basierend auf der TIMEZONE-Umgebungsvariable.
    
    Args:
        utc_datetime: UTC-Datetime oder String-Repräsentation
        source_timezone: Quellzeitzone (Standard: UTC)
        
    Returns:
        Lokales datetime-Objekt oder None bei Fehler
    """
    try:
        # Zielzeitzone aus .env lesen
        target_tz = get_target_timezone()
        
        # Wenn UTC gewünscht ist, keine Konvertierung
        if target_tz.upper() == 'UTC':
            logger.debug("Keine Zeitzonenkonvertierung - UTC gewünscht")
            if isinstance(utc_datetime, str):
                return datetime.fromisoformat(utc_datetime.replace('Z', '+00:00'))
            return utc_datetime
        
        # Quellzeitzone
        source_tz = pytz.timezone(source_timezone)
        
        # Zielzeitzone
        target_timezone = pytz.timezone(target_tz)
        
        # Datetime parsen falls String
        if isinstance(utc_datetime, str):
            # Entferne 'Z' und ersetze durch '+00:00' für UTC
            if utc_datetime.endswith('Z'):
                utc_datetime = utc_datetime[:-1] + '+00:00'
            dt = datetime.fromisoformat(utc_datetime)
        else:
            dt = utc_datetime
        
        # Lokalisieren falls naive datetime
        if dt.tzinfo is None:
            dt = source_tz.localize(dt)
        
        # Konvertieren zur Zielzeitzone
        local_dt = dt.astimezone(target_timezone)
        
        # Als naive datetime zurückgeben (ohne Zeitzone)
        local_naive = local_dt.replace(tzinfo=None)
        
        logger.debug(f"Konvertiert {dt} ({source_timezone}) -> {local_naive} ({target_tz})")
        return local_naive
        
    except Exception as e:
        logger.error(f"Fehler bei Zeitzonenkonvertierung: {str(e)}")
        return None

def convert_local_to_utc(local_datetime: Union[datetime, str], source_timezone: str = None) -> Optional[datetime]:
    """
    Konvertiert ein lokales Datetime zu UTC.
    
    Args:
        local_datetime: Lokales datetime oder String
        source_timezone: Quellzeitzone (wird aus .env gelesen falls None)
        
    Returns:
        UTC datetime-Objekt oder None bei Fehler
    """
    try:
        # Quellzeitzone bestimmen
        if source_timezone is None:
            source_timezone = get_target_timezone()
        
        # Wenn UTC als Quellzeitzone, keine Konvertierung
        if source_timezone.upper() == 'UTC':
            if isinstance(local_datetime, str):
                return datetime.fromisoformat(local_datetime.replace('Z', '+00:00'))
            return local_datetime
        
        # Datetime parsen falls String
        if isinstance(local_datetime, str):
            dt = datetime.fromisoformat(local_datetime)
        else:
            dt = local_datetime
        
        # Lokalisieren
        source_tz = pytz.timezone(source_timezone)
        if dt.tzinfo is None:
            dt = source_tz.localize(dt)
        
        # Konvertieren zu UTC
        utc_dt = dt.astimezone(pytz.UTC)
        
        logger.debug(f"Konvertiert {dt} ({source_timezone}) -> {utc_dt} (UTC)")
        return utc_dt
        
    except Exception as e:
        logger.error(f"Fehler bei UTC-Konvertierung: {str(e)}")
        return None

def parse_and_convert_timestamp(timestamp_str: str, source_timezone: str = 'UTC') -> Optional[datetime]:
    """
    Parst einen Timestamp-String und konvertiert ihn zur lokalen Zeitzone.
    
    Args:
        timestamp_str: Timestamp als String
        source_timezone: Quellzeitzone (Standard: UTC)
        
    Returns:
        Lokales datetime-Objekt oder None bei Fehler
    """
    try:
        # Debug: Zeige den ursprünglichen Timestamp
        logger.debug(f"Versuche Timestamp zu parsen: '{timestamp_str}' (Typ: {type(timestamp_str)})")
        
        # Prüfe auf None/NaN/leere Werte
        if timestamp_str is None or str(timestamp_str).lower() in ['nan', 'none', 'null', '']:
            logger.debug(f"Timestamp ist leer/None: {timestamp_str}")
            return None
        
        # Bereinige den String
        timestamp_str = str(timestamp_str).strip()
        if not timestamp_str:
            logger.debug("Timestamp ist leer nach Strip")
            return None
        
        # Verschiedene Timestamp-Formate versuchen
        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%Y-%m-%d %H:%M:%S.%f',
            '%d.%m.%Y %H:%M:%S',
            '%m/%d/%Y %H:%M:%S',
            '%Y-%m-%d',  # Nur Datum
            '%d.%m.%Y',  # Nur Datum (deutsch)
            '%m/%d/%Y',  # Nur Datum (US)
        ]
        
        dt = None
        used_format = None
        
        for fmt in formats:
            try:
                dt = datetime.strptime(timestamp_str, fmt)
                used_format = fmt
                logger.debug(f"Timestamp erfolgreich geparst mit Format '{fmt}': {dt}")
                break
            except ValueError:
                continue
        
        if dt is None:
            logger.warning(f"Konnte Timestamp nicht parsen: '{timestamp_str}' - Versuche pandas.to_datetime")
            # Fallback: Versuche pandas.to_datetime
            try:
                import pandas as pd
                dt = pd.to_datetime(timestamp_str)
                if pd.isna(dt):
                    logger.error(f"pandas.to_datetime konnte Timestamp nicht parsen: '{timestamp_str}'")
                    return None
                dt = dt.to_pydatetime()
                logger.debug(f"Timestamp erfolgreich mit pandas geparst: {dt}")
            except Exception as e:
                logger.error(f"pandas.to_datetime fehlgeschlagen: {str(e)}")
                return None
        
        # Konvertieren zur lokalen Zeitzone
        result = convert_utc_to_local(dt, source_timezone)
        if result:
            logger.debug(f"Zeitzonenkonvertierung erfolgreich: {dt} -> {result}")
        else:
            logger.error(f"Zeitzonenkonvertierung fehlgeschlagen für: {dt}")
        
        return result
        
    except Exception as e:
        logger.error(f"Fehler beim Parsen des Timestamps '{timestamp_str}': {str(e)}")
        return None 