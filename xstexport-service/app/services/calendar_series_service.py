import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, YEARLY, MO, TU, WE, TH, FR, SA, SU
import pytz

logger = logging.getLogger(__name__)


class CalendarSeriesService:
    """
    Service-Klasse zur Generierung einzelner Kalendereinträge aus Serientermindefinitionen.
    """
    
    def __init__(self, db_service: Any):
        """
        Initialisiert den CalendarSeriesService.
        
        Args:
            db_service: DatabaseService Instanz
        """
        self.db_service = db_service
    
    def generate_series_occurrences(
        self, 
        series_row: Dict[str, Any],
        until_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Generiert alle Termine einer Serie basierend auf den Serienterminfeldern.
        
        Args:
            series_row: Dictionary mit allen Feldern des Serientermin-Datensatzes
            until_date: Optionales Enddatum für die Generierung (Standard: meeting_series_end_time oder 1 Jahr in die Zukunft)
        
        Returns:
            Liste von Dictionaries, jeder repräsentiert einen einzelnen Termin
        """
        try:
            # Extrahiere Serienterminfelder
            meeting_series_start_time = series_row.get('meeting_series_start_time')
            meeting_series_end_time = series_row.get('meeting_series_end_time')
            frequency = series_row.get('meeting_series_frequency')
            interval = series_row.get('meeting_series_interval', 1)
            weekdays = series_row.get('meeting_series_weekdays')
            monthday = series_row.get('meeting_series_monthday')
            weekday_nth = series_row.get('meeting_series_weekday_nth')
            months = series_row.get('meeting_series_months')
            exceptions_str = series_row.get('meeting_series_exceptions', '')
            
            # Original start_date und end_date für Dauer-Berechnung
            original_start = series_row.get('start_date')
            original_end = series_row.get('end_date')
            
            # Validiere erforderliche Felder
            if not meeting_series_start_time or not frequency:
                logger.warning(f"Serientermin {series_row.get('id')} hat unvollständige Daten, überspringe")
                return []
            
            # Konvertiere meeting_series_start_time zu datetime falls nötig
            if isinstance(meeting_series_start_time, str):
                dtstart_utc = datetime.fromisoformat(meeting_series_start_time.replace('Z', '+00:00'))
            elif isinstance(meeting_series_start_time, datetime):
                dtstart_utc = meeting_series_start_time
            else:
                logger.warning(f"[TIMEZONE] Ungültiges meeting_series_start_time für Serientermin {series_row.get('id')}")
                return []
            
            # WICHTIG: Konvertiere dtstart zu lokaler Zeit für die rrule
            # Die rrule muss mit lokaler Zeit arbeiten, damit die Termine für jedes Datum
            # die korrekte lokale Zeit haben und die UTC-Konvertierung basierend auf
            # Sommer-/Winterzeit korrekt durchgeführt wird.
            timezone_str = os.getenv("TIMEZONE", "Europe/Berlin")
            local_tz = pytz.timezone(timezone_str)
            logger.info(f"[TIMEZONE] Verwende Zeitzone: {timezone_str}")
            
            # Konvertiere UTC zu lokaler Zeit
            if dtstart_utc.tzinfo is None:
                # Falls keine Zeitzone: interpretiere als UTC
                dtstart_utc = pytz.UTC.localize(dtstart_utc)
            elif dtstart_utc.tzinfo != pytz.UTC:
                # Falls andere Zeitzone: konvertiere zu UTC
                dtstart_utc = dtstart_utc.astimezone(pytz.UTC)
            
            dtstart = dtstart_utc.astimezone(local_tz)
            
            # Bestimme until-Datum
            if until_date:
                if isinstance(until_date, datetime):
                    if until_date.tzinfo is None:
                        until = pytz.UTC.localize(until_date).astimezone(local_tz)
                    else:
                        until = until_date.astimezone(local_tz)
                else:
                    until = until_date
            elif meeting_series_end_time:
                if isinstance(meeting_series_end_time, str):
                    until_utc = datetime.fromisoformat(meeting_series_end_time.replace('Z', '+00:00'))
                    if until_utc.tzinfo is None:
                        until_utc = pytz.UTC.localize(until_utc)
                    until = until_utc.astimezone(local_tz)
                elif isinstance(meeting_series_end_time, datetime):
                    if meeting_series_end_time.tzinfo is None:
                        until_utc = pytz.UTC.localize(meeting_series_end_time)
                    else:
                        until_utc = meeting_series_end_time.astimezone(pytz.UTC)
                    until = until_utc.astimezone(local_tz)
                else:
                    until = dtstart + timedelta(days=365)  # Fallback: 1 Jahr
            else:
                until = dtstart + timedelta(days=365)  # Fallback: 1 Jahr
            
            # Erstelle RRULE-Objekt
            rule = self._build_rrule(
                frequency=frequency,
                interval=interval,
                weekdays=weekdays,
                monthday=monthday,
                weekday_nth=weekday_nth,
                months=months,
                dtstart=dtstart,
                until=until
            )
            
            if not rule:
                logger.warning(f"Konnte RRULE nicht erstellen für Serientermin {series_row.get('id')}")
                return []
            
            # Generiere alle Termine
            occurrences_dates = list(rule)
            
            # Parse Ausnahmen
            exceptions = self._parse_exceptions(exceptions_str)
            
            # Filtere Ausnahmen heraus
            valid_occurrences_dates = [
                occ_date for occ_date in occurrences_dates
                if occ_date.date() not in exceptions
            ]
            
            # Erstelle Termin-Dictionaries
            occurrences = []
            logger.info(f"[TIMEZONE] Generiere {len(valid_occurrences_dates)} Termine aus rrule")
            
            for idx, occ_start in enumerate(valid_occurrences_dates):
                # KRITISCH: Die rrule behält die Zeitzone des dtstart bei, auch wenn das Datum
                # in eine andere Zeitzone (Sommer-/Winterzeit) fällt.
                # Beispiel: dtstart = 2025-04-03 09:30:00+02:00 (Sommerzeit)
                #           rrule generiert: 2025-11-26 09:30:00+02:00 (falsch! sollte +01:00 sein)
                #
                # Lösung: Extrahiere die naive Zeit (09:30) und lokalisiere sie für das
                # spezifische Datum neu, damit die korrekte Zeitzone (Sommer-/Winterzeit)
                # automatisch angewendet wird.
                
                if occ_start.tzinfo is not None:
                    # Extrahiere naive Zeit (Datum + Uhrzeit ohne Zeitzone)
                    occ_start_naive = occ_start.replace(tzinfo=None)
                    
                    # Lokalisiere für das spezifische Datum neu (berücksichtigt automatisch DST)
                    occ_start_corrected = local_tz.localize(occ_start_naive, is_dst=None)
                    
                    # Konvertiere zu UTC
                    occ_start_utc = occ_start_corrected.astimezone(pytz.UTC)
                else:
                    # Falls naive: lokalisiere direkt
                    occ_start_localized = local_tz.localize(occ_start, is_dst=None)
                    occ_start_utc = occ_start_localized.astimezone(pytz.UTC)
                
                # Berechne end_date basierend auf ursprünglicher Dauer
                occ_end = self._calculate_end_date(
                    occ_start_utc,
                    original_start,
                    original_end,
                    meeting_series_start_time
                )
                
                logger.info(f"[TIMEZONE] Termin {idx+1}: start_date (UTC) = {occ_start_utc}, end_date (UTC) = {occ_end}")
                
                # Kopiere alle Felder vom Serientermin
                new_occurrence = self._copy_series_fields(series_row)
                
                # Setze neue start_date und end_date (in UTC)
                new_occurrence['start_date'] = occ_start_utc
                new_occurrence['end_date'] = occ_end
                
                # Setze id = None (wird von DB generiert)
                new_occurrence['id'] = None
                
                occurrences.append(new_occurrence)
            
            logger.info(f"Generiert {len(occurrences)} Termine für Serientermin {series_row.get('id')}")
            return occurrences
            
        except Exception as e:
            logger.error(f"Fehler bei Generierung von Terminen für Serientermin {series_row.get('id')}: {str(e)}")
            return []
    
    def _build_rrule(
        self, 
        frequency: str,
        interval: int,
        weekdays: Optional[str],
        monthday: Optional[int],
        weekday_nth: Optional[int],
        months: Optional[str],
        dtstart: datetime,
        until: datetime
    ) -> Optional[rrule]:
        """
        Konvertiert die Serienterminfelder in ein dateutil.rrule.rrule Objekt.
        
        Args:
            frequency: DAILY, WEEKLY, MONTHLY, YEARLY
            interval: Integer >= 1
            weekdays: Komma-separierte String (z.B. "MO,WE,FR") oder None
            monthday: Integer 1-31 oder None
            weekday_nth: Integer -5..-1 oder 1..5 oder None
            months: Komma-separierte String (z.B. "1,3,6") oder None
            dtstart: Startdatum der Serie
            until: Enddatum der Serie
        
        Returns:
            dateutil.rrule.rrule Objekt oder None bei Fehler
        """
        try:
            # Frequenz-Mapping
            freq_map = {
                "DAILY": DAILY,
                "WEEKLY": WEEKLY,
                "MONTHLY": MONTHLY,
                "YEARLY": YEARLY
            }
            
            if frequency not in freq_map:
                logger.warning(f"Ungültige Frequenz: {frequency}")
                return None
            
            freq = freq_map[frequency]
            
            # Basis-Parameter
            rule_params = {
                'freq': freq,
                'interval': interval if interval else 1,
                'dtstart': dtstart,
                'until': until
            }
            
            # Wochentage hinzufügen (für WEEKLY oder MONTHLY mit weekday_nth)
            if weekdays:
                weekday_list = self._parse_weekdays(weekdays)
                if weekday_list:
                    rule_params['byweekday'] = weekday_list
            
            # Monatstag hinzufügen (für MONTHLY)
            if monthday:
                rule_params['bymonthday'] = monthday
            
            # N-ter Wochentag hinzufügen (für MONTHLY)
            if weekday_nth:
                # weekday_nth: 1=first, 2=second, ..., -1=last
                if 'byweekday' in rule_params:
                    rule_params['bysetpos'] = [weekday_nth]
            
            # Monate hinzufügen (für YEARLY)
            if months:
                month_list = self._parse_months(months)
                if month_list:
                    rule_params['bymonth'] = month_list
            
            # Erstelle RRULE
            rule = rrule(**rule_params)
            return rule
            
        except Exception as e:
            logger.error(f"Fehler beim Erstellen der RRULE: {str(e)}")
            return None
    
    def _parse_weekdays(self, weekdays_str: str) -> List[Any]:
        """
        Konvertiert String "MO,WE,FR" in Liste von dateutil.rrule Wochentag-Objekten.
        
        Args:
            weekdays_str: Komma-separierte Wochentage (z.B. "MO,WE,FR")
        
        Returns:
            Liste von Wochentag-Objekten
        """
        weekday_map = {
            "MO": MO, "TU": TU, "WE": WE, "TH": TH,
            "FR": FR, "SA": SA, "SU": SU
        }
        
        days = [d.strip().upper() for d in weekdays_str.split(",")]
        return [weekday_map[d] for d in days if d in weekday_map]
    
    def _parse_months(self, months_str: str) -> List[int]:
        """
        Konvertiert String "1,3,6" in Liste von Integers [1, 3, 6].
        
        Args:
            months_str: Komma-separierte Monate (z.B. "1,3,6")
        
        Returns:
            Liste von Monaten (1-12)
        """
        try:
            months = [int(m.strip()) for m in months_str.split(",") if m.strip().isdigit()]
            return [m for m in months if 1 <= m <= 12]
        except (ValueError, AttributeError):
            return []
    
    def _parse_exceptions(self, exceptions_str: str) -> List[date]:
        """
        Parst meeting_series_exceptions String in Liste von Datum-Objekten.
        
        Args:
            exceptions_str: Komma-separierte ISO-8601 Datums-Strings oder Text
        
        Returns:
            Liste von date-Objekten
        """
        if not exceptions_str or exceptions_str.strip() == "":
            return []
        
        exceptions = []
        for exc_str in exceptions_str.split(","):
            exc_str = exc_str.strip()
            try:
                # Versuche ISO-8601 Format
                exc_date = datetime.fromisoformat(exc_str.replace('Z', '+00:00')).date()
                exceptions.append(exc_date)
            except (ValueError, AttributeError):
                # Falls Parsing fehlschlägt, logge Warnung und überspringe
                logger.warning(f"Konnte Ausnahme-Datum nicht parsen: {exc_str}")
        
        return exceptions
    
    def _calculate_end_date(
        self, 
        new_start: datetime, 
        original_start: Optional[datetime],
        original_end: Optional[datetime],
        meeting_series_start_time: Any
    ) -> datetime:
        """
        Berechnet end_date für einen neuen Termin basierend auf der ursprünglichen Dauer.
        
        Args:
            new_start: Neues Startdatum des Termins
            original_start: Ursprüngliches start_date vom Serientermin
            original_end: Ursprüngliches end_date vom Serientermin
            meeting_series_start_time: meeting_series_start_time als Fallback
        
        Returns:
            Berechnetes end_date
        """
        # Versuche zuerst original_start und original_end
        if original_start and original_end:
            # Konvertiere zu datetime falls nötig
            if isinstance(original_start, str):
                orig_start = datetime.fromisoformat(original_start.replace('Z', '+00:00'))
            else:
                orig_start = original_start
            
            if isinstance(original_end, str):
                orig_end = datetime.fromisoformat(original_end.replace('Z', '+00:00'))
            else:
                orig_end = original_end
            
            duration = orig_end - orig_start
            return new_start + duration
        
        # Fallback: Verwende meeting_series_start_time und meeting_series_end_time
        if meeting_series_start_time:
            try:
                if isinstance(meeting_series_start_time, str):
                    series_start = datetime.fromisoformat(meeting_series_start_time.replace('Z', '+00:00'))
                else:
                    series_start = meeting_series_start_time
                
                # Standard-Dauer: 30 Minuten
                return new_start + timedelta(minutes=30)
            except Exception:
                pass
        
        # Letzter Fallback: 30 Minuten
        return new_start + timedelta(minutes=30)
    
    def _copy_series_fields(self, series_row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Kopiert alle relevanten Felder vom Serientermin-Datensatz in einen neuen Termin-Datensatz.
        
        Args:
            series_row: Dictionary mit allen Feldern des Serientermin-Datensatzes
        
        Returns:
            Neues Dictionary mit kopierten Feldern
        """
        fields_to_copy = [
            'subject', 'client_submit_time', 'sent_representing_name',
            'conversation_topic', 'sender_name', 'display_cc', 'display_to',
            'unknown_0e05', 'message_delivery_time', 'unknown_0f02', 'unknown_0f0a',
            'last_verb_execution_time', 'creation_time', 'last_modification_time',
            'unknown_3fd9', 'unknown_4038', 'unknown_4039', 'sender_smtp_address',
            'sent_representing_smtp_address', 'user_entry_id',
            'address_book_folder_pathname', 'address_book_manager', 'file_under_id',
            'meeting_series_start_date', 'has_picture', 'unknown_8016', 'unknown_8021',
            'postal_address_id', 'unknown_802a', 'html', 'instant_messaging_address',
            'unknown_8063', 'unknown_806c', 'unknown_80b0', 'unknown_816b', 'unknown_817a'
        ]
        
        new_row = {}
        for field in fields_to_copy:
            if field in series_row:
                new_row[field] = series_row[field]
        
        return new_row

