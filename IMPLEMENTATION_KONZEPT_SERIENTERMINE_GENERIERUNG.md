# Implementierungskonzept: Generierung einzelner Kalendereinträge aus Serientermindefinitionen
## Übersicht
Dieses Dokument beschreibt die Implementierung einer automatischen Generierung einzelner Kalendereinträge aus Serientermindefinitionen in der Tabelle `calendar_data`. Basierend auf den LLM-generierten Serienterminfeldern werden alle Termine der Serie berechnet und als separate Einträge in derselben Tabelle gespeichert.
## Architektur-Übersicht
```
LLM-Verarbeitung → Serienterminfelder → Termin-Generierung → DB-Insert
     ↓                    ↓                    ↓                ↓
calendar_data      meeting_series_*      dateutil.rrule    calendar_data
(mit rhythm)       (strukturiert)        (Terminliste)     (einzelne Termine)
```
## 1. Anforderungen
### 1.1 Eingabefelder (aus calendar_data)
Für jeden Serientermin-Datensatz werden folgende Felder verwendet:
- `meeting_series_start_time` (timestamp with time zone) - Startzeitpunkt der Serie
- `meeting_series_end_time` (timestamp with time zone) - Endzeitpunkt der Serie
- `meeting_series_frequency` (text) - Frequenz: DAILY, WEEKLY, MONTHLY, YEARLY
- `meeting_series_interval` (INTEGER) - Intervall (z.B. alle 2 Wochen = 2)
- `meeting_series_weekdays` (text) - Komma-separierte Wochentage: MO,TU,WE,TH,FR,SA,SU
- `meeting_series_monthday` (INTEGER) - Tag des Monats (1-31)
- `meeting_series_weekday_nth` (INTEGER) - N-ter Wochentag (-5..-1 für letzte, 1..5 für erste)
- `meeting_series_months` (text) - Komma-separierte Monate (1-12)
- `meeting_series_exceptions` (text) - Ausnahmen (ISO-Datum-Liste oder Text)
### 1.2 Zu kopierende Felder vom Serientermin
Für jeden generierten Termin werden folgende Felder vom ursprünglichen Serientermin-Datensatz übernommen:
- `subject`
- `client_submit_time`
- `sent_representing_name`
- `conversation_topic`
- `sender_name`
- `display_cc`
- `display_to`
- `unknown_0e05`
- `message_delivery_time`
- `unknown_0f02`
- `unknown_0f0a`
- `last_verb_execution_time`
- `creation_time`
- `last_modification_time`
- `unknown_3fd9`
- `unknown_4038`
- `unknown_4039`
- `sender_smtp_address`
- `sent_representing_smtp_address`
- `user_entry_id`
- `address_book_folder_pathname`
- `address_book_manager`
- `file_under_id`
- `meeting_series_start_date` (wird vom ursprünglichen Datensatz übernommen)
- `has_picture`
- `unknown_8016`
- `unknown_8021`
- `postal_address_id`
- `unknown_802a`
- `html`
- `instant_messaging_address`
- `unknown_8063`
- `unknown_806c`
- `unknown_80b0`
- `unknown_816b`
- `unknown_817a`
### 1.3 Neu berechnete Felder
- `id` - Neue ID gemäß PRIMARY KEY Definition (SERIAL)
- `start_date` - Datum und Uhrzeit entsprechend der Serienterminregel
- `end_date` - Datum und Uhrzeit, resultierend aus der Dauer zwischen ursprünglichem `start_date` und `end_date`, angewendet auf das neue `start_date`
### 1.4 Logik für end_date Berechnung
```python
# Pseudocode
original_duration = original_end_date - original_start_date
new_start_date = berechneter_termin_start  # aus RRULE
new_end_date = new_start_date + original_duration
```
## 2. Abhängigkeiten
### 2.1 Neue Python-Pakete
**Datei:** `/Volumes/Samsung 512GB/transcript-summarization/xstexport-service/requirements.txt`
**Hinzuzufügen:**
```
# Für RRULE-Berechnungen (RFC 5545)
python-dateutil>=2.8.2
```
**Begründung:**
- `python-dateutil` enthält `dateutil.rrule`, das RFC 5545 RRULE implementiert
- Ermöglicht Berechnung wiederkehrender Termine basierend auf Frequenz, Intervall, Wochentagen, etc.
- Standard-Bibliothek für wiederkehrende Termine in Python
### 2.2 Alternative Bibliotheken
Falls `python-dateutil` nicht ausreicht, kann `rrule` (separates Paket) verwendet werden:
```
rrule>=0.10.0
```
## 3. Neue Service-Klasse: CalendarSeriesService
### 3.1 Datei-Struktur
**Neue Datei:** `/Volumes/Samsung 512GB/transcript-summarization/xstexport-service/app/services/calendar_series_service.py`
**Zweck:**
- Kapselung der Logik zur Generierung einzelner Termine aus Serientermindefinitionen
- RRULE-Konvertierung und -Berechnung
- Duplikat-Erkennung
- Batch-Insert in die Datenbank
### 3.2 Klassen-Design
```python
class CalendarSeriesService:
    def __init__(self, db_service: DatabaseService)
    def generate_series_occurrences(
        self, 
        series_row: Dict[str, Any],
        until_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]
    def _build_rrule(
        self, 
        frequency: str,
        interval: int,
        weekdays: Optional[str],
        monthday: Optional[int],
        weekday_nth: Optional[int],
        months: Optional[str],
        dtstart: datetime,
        until: Optional[datetime]
    ) -> rrule
    def _parse_weekdays(self, weekdays_str: str) -> List[int]
    def _parse_months(self, months_str: str) -> List[int]
    def _parse_exceptions(self, exceptions_str: str) -> List[date]
    def _calculate_end_date(
        self, 
        new_start: datetime, 
        original_start: datetime, 
        original_end: datetime
    ) -> datetime
    def _copy_series_fields(self, series_row: Dict[str, Any]) -> Dict[str, Any]
```
### 3.3 Methode: `generate_series_occurrences`
**Zweck:**
- Generiert alle Termine einer Serie basierend auf den Serienterminfeldern
- Berücksichtigt Ausnahmen (exceptions)
- Berechnet `start_date` und `end_date` für jeden Termin
- Kopiert alle anderen Felder vom Serientermin
**Parameter:**
- `series_row`: Dictionary mit allen Feldern des Serientermin-Datensatzes
- `until_date`: Optionales Enddatum für die Generierung (Standard: `meeting_series_end_time` oder 1 Jahr in die Zukunft)
**Rückgabe:**
- Liste von Dictionaries, jeder repräsentiert einen einzelnen Termin
**Implementierungslogik:**
1. Extrahiere Serienterminfelder aus `series_row`
2. Validiere, dass alle erforderlichen Felder vorhanden sind
3. Berechne `original_duration` aus ursprünglichem `start_date` und `end_date`
4. Erstelle RRULE-Objekt mit `_build_rrule`
5. Generiere alle Termine mit `rrule.between()` oder `rrule`
6. Filtere Ausnahmen heraus
7. Für jeden Termin:
   - Setze `start_date` = generierter Termin
   - Berechne `end_date` = `start_date + original_duration`
   - Kopiere alle anderen Felder mit `_copy_series_fields`
   - Setze `id` = None (wird von DB generiert)
### 3.4 Methode: `_build_rrule`
**Zweck:**
- Konvertiert die Serienterminfelder in ein `dateutil.rrule.rrule` Objekt
**Parameter:**
- `frequency`: DAILY, WEEKLY, MONTHLY, YEARLY
- `interval`: Integer >= 1
- `weekdays`: Komma-separierte String (z.B. "MO,WE,FR") oder None
- `monthday`: Integer 1-31 oder None
- `weekday_nth`: Integer -5..-1 oder 1..5 oder None
- `months`: Komma-separierte String (z.B. "1,3,6") oder None
- `dtstart`: Startdatum der Serie
- `until`: Enddatum der Serie
**Rückgabe:**
- `dateutil.rrule.rrule` Objekt
**Implementierungslogik:**
```python
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, YEARLY, MO, TU, WE, TH, FR, SA, SU
# Frequenz-Mapping
freq_map = {
    "DAILY": DAILY,
    "WEEKLY": WEEKLY,
    "MONTHLY": MONTHLY,
    "YEARLY": YEARLY
}
# Wochentag-Mapping
weekday_map = {
    "MO": MO, "TU": TU, "WE": WE, "TH": TH,
    "FR": FR, "SA": SA, "SU": SU
}
# Basis-RRULE erstellen
rule = rrule(
    freq=freq_map[frequency],
    interval=interval,
    dtstart=dtstart,
    until=until
)
# Wochentage hinzufügen (für WEEKLY)
if weekdays:
    weekday_list = self._parse_weekdays(weekdays)
    rule = rrule(
        freq=freq_map[frequency],
        interval=interval,
        byweekday=weekday_list,
        dtstart=dtstart,
        until=until
    )
# Monatstag hinzufügen (für MONTHLY)
if monthday:
    rule = rrule(
        freq=freq_map[frequency],
        interval=interval,
        bymonthday=monthday,
        dtstart=dtstart,
        until=until
    )
# N-ter Wochentag hinzufügen (für MONTHLY)
if weekday_nth:
    # weekday_nth: 1=first, 2=second, ..., -1=last
    if weekdays:
        weekday_list = self._parse_weekdays(weekdays)
        bysetpos = [weekday_nth] if weekday_nth > 0 else [weekday_nth]
        rule = rrule(
            freq=freq_map[frequency],
            interval=interval,
            byweekday=weekday_list,
            bysetpos=bysetpos,
            dtstart=dtstart,
            until=until
        )
# Monate hinzufügen (für YEARLY)
if months:
    month_list = self._parse_months(months)
    rule = rrule(
        freq=freq_map[frequency],
        interval=interval,
        bymonth=month_list,
        dtstart=dtstart,
        until=until
    )
```
### 3.5 Methode: `_parse_weekdays`
**Zweck:**
- Konvertiert String "MO,WE,FR" in Liste von `dateutil.rrule` Wochentag-Objekten
**Implementierung:**
```python
def _parse_weekdays(self, weekdays_str: str) -> List[int]:
    """Konvertiert 'MO,WE,FR' in [MO, WE, FR]"""
    weekday_map = {
        "MO": MO, "TU": TU, "WE": WE, "TH": TH,
        "FR": FR, "SA": SA, "SU": SU
    }
    days = [d.strip().upper() for d in weekdays_str.split(",")]
    return [weekday_map[d] for d in days if d in weekday_map]
```
### 3.6 Methode: `_parse_months`
**Zweck:**
- Konvertiert String "1,3,6" in Liste von Integers [1, 3, 6]
**Implementierung:**
```python
def _parse_months(self, months_str: str) -> List[int]:
    """Konvertiert '1,3,6' in [1, 3, 6]"""
    months = [int(m.strip()) for m in months_str.split(",") if m.strip().isdigit()]
    return [m for m in months if 1 <= m <= 12]
```
### 3.7 Methode: `_parse_exceptions`
**Zweck:**
- Parst `meeting_series_exceptions` String in Liste von Datum-Objekten
- Unterstützt ISO-8601 Format (z.B. "2025-11-15,2025-12-20") oder Text
**Implementierung:**
```python
def _parse_exceptions(self, exceptions_str: str) -> List[date]:
    """Parst Ausnahmen-String in Liste von Datum-Objekten"""
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
```
### 3.8 Methode: `_calculate_end_date`
**Zweck:**
- Berechnet `end_date` für einen neuen Termin basierend auf der ursprünglichen Dauer
**Implementierung:**
```python
def _calculate_end_date(
    self, 
    new_start: datetime, 
    original_start: datetime, 
    original_end: datetime
) -> datetime:
    """Berechnet end_date basierend auf ursprünglicher Dauer"""
    if original_start and original_end:
        duration = original_end - original_start
        return new_start + duration
    # Fallback: Falls original_start/end nicht vorhanden, verwende meeting_series_end_time
    # oder setze Standard-Dauer (z.B. 30 Minuten)
    return new_start + timedelta(minutes=30)
```
### 3.9 Methode: `_copy_series_fields`
**Zweck:**
- Kopiert alle relevanten Felder vom Serientermin-Datensatz in einen neuen Termin-Datensatz
**Implementierung:**
```python
def _copy_series_fields(self, series_row: Dict[str, Any]) -> Dict[str, Any]:
    """Kopiert alle Felder vom Serientermin (außer id, start_date, end_date, meeting_series_*)"""
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
```
## 4. Erweiterung DatabaseService
### 4.1 Neue Methode: `get_series_rows_to_process`
**Datei:** `/Volumes/Samsung 512GB/transcript-summarization/xstexport-service/app/services/db_service.py`
**Zweck:**
- Ruft alle Serientermin-Datensätze ab, die noch nicht verarbeitet wurden
- Identifiziert Serientermine anhand vorhandener `meeting_series_*` Felder
**SQL-Query:**
```sql
SELECT *
FROM calendar_data
WHERE meeting_series_start_time IS NOT NULL
  AND meeting_series_end_time IS NOT NULL
  AND meeting_series_frequency IS NOT NULL
  AND meeting_series_frequency != ''
```
**Implementierung:**
```python
def get_series_rows_to_process(
    self, 
    table_name: str = "calendar_data"
) -> List[Dict[str, Any]]:
    """
    Ruft alle Serientermin-Datensätze ab, die noch nicht in einzelne Termine aufgeteilt wurden.
    
    Args:
        table_name: Name der Tabelle (Standard: "calendar_data")
    
    Returns:
        Liste von Dictionaries mit allen Feldern des Serientermin-Datensatzes
    """
    try:
        sql = text(f"""
            SELECT *
            FROM {table_name}
            WHERE meeting_series_start_time IS NOT NULL
              AND meeting_series_end_time IS NOT NULL
              AND meeting_series_frequency IS NOT NULL
              AND meeting_series_frequency != ''
        """)
        
        with self.engine.connect() as conn:
            result = conn.execute(sql)
            columns = result.keys()
            rows = []
            for row in result:
                row_dict = dict(zip(columns, row))
                rows.append(row_dict)
            
            logger.info(f"Gefunden: {len(rows)} Serientermine zum Verarbeiten")
            return rows
    except SQLAlchemyError as e:
        logger.error(f"Fehler beim Abrufen der Serientermine: {str(e)}")
        raise
```
### 4.2 Neue Methode: `check_occurrence_exists`
**Zweck:**
- Prüft, ob ein Termin mit bestimmten `start_date` und `subject` bereits existiert
- Verhindert Duplikate
**SQL-Query:**
```sql
SELECT COUNT(*) 
FROM calendar_data
WHERE start_date = :start_date
  AND subject = :subject
  AND (meeting_series_start_time IS NULL OR meeting_series_start_time != :series_start_time)
```
**Implementierung:**
```python
def check_occurrence_exists(
    self,
    start_date: datetime,
    subject: str,
    series_start_time: datetime,
    table_name: str = "calendar_data"
) -> bool:
    """
    Prüft, ob ein Termin mit bestimmten start_date und subject bereits existiert.
    
    Args:
        start_date: Startdatum des zu prüfenden Termins
        subject: Betreff des Termins
        series_start_time: Startzeitpunkt der Serie (zum Ausschließen des Serientermins selbst)
        table_name: Name der Tabelle (Standard: "calendar_data")
    
    Returns:
        True wenn Termin bereits existiert, False sonst
    """
    try:
        sql = text(f"""
            SELECT COUNT(*) 
            FROM {table_name}
            WHERE start_date = :start_date
              AND subject = :subject
              AND (meeting_series_start_time IS NULL 
                   OR meeting_series_start_time != :series_start_time)
        """)
        
        with self.engine.connect() as conn:
            result = conn.execute(sql, {
                'start_date': start_date,
                'subject': subject,
                'series_start_time': series_start_time
            })
            count = result.scalar()
            return count > 0
    except SQLAlchemyError as e:
        logger.error(f"Fehler beim Prüfen auf Duplikate: {str(e)}")
        return False  # Bei Fehler: nicht als Duplikat behandeln
```
### 4.3 Neue Methode: `insert_occurrences_batch`
**Zweck:**
- Fügt mehrere Termine in einem Batch-Insert ein
- Verwendet `execute_values` für bessere Performance
**Implementierung:**
```python
def insert_occurrences_batch(
    self,
    occurrences: List[Dict[str, Any]],
    table_name: str = "calendar_data"
) -> int:
    """
    Fügt mehrere Termine in einem Batch-Insert ein.
    
    Args:
        occurrences: Liste von Dictionaries, jeder repräsentiert einen Termin
        table_name: Name der Tabelle (Standard: "calendar_data")
    
    Returns:
        Anzahl der eingefügten Zeilen
    """
    if not occurrences:
        return 0
    
    try:
        # Lade Mapping, um alle Spaltennamen zu erhalten
        columns = []
        for field_name, field_info in self.mapping.items():
            columns.append(field_info['pg_field'])
        
        # Filtere nur Spalten, die in occurrences vorhanden sind
        first_occurrence = occurrences[0]
        available_columns = [col for col in columns if col in first_occurrence]
        
        # Erstelle VALUES-Liste
        values_list = []
        for occ in occurrences:
            values = [occ.get(col) for col in available_columns]
            values_list.append(values)
        
        # Batch-Insert mit execute_values
        with self.engine.raw_connection() as conn:
            cursor = conn.cursor()
            execute_values(
                cursor,
                f"""
                INSERT INTO {table_name} ({', '.join(available_columns)})
                VALUES %s
                """,
                values_list,
                page_size=100
            )
            conn.commit()
            cursor.close()
        
        inserted_count = len(occurrences)
        logger.info(f"{inserted_count} Termine erfolgreich eingefügt")
        return inserted_count
    except Exception as e:
        logger.error(f"Fehler beim Batch-Insert: {str(e)}")
        raise
```
### 4.4 Neue Methode: `process_series_to_occurrences`
**Zweck:**
- Orchestriert die gesamte Verarbeitung: Abrufen von Serienterminen, Generierung von Terminen, Einfügen in DB
**Implementierung:**
```python
def process_series_to_occurrences(
    self,
    table_name: str = "calendar_data",
    calendar_series_service: Optional[Any] = None,
    until_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Verarbeitet alle Serientermine und generiert einzelne Termine.
    
    Args:
        table_name: Name der Tabelle (Standard: "calendar_data")
        calendar_series_service: Optionaler CalendarSeriesService (wird erstellt falls None)
        until_date: Optionales Enddatum für Termin-Generierung
    
    Returns:
        Dictionary mit Statistik (total_series, total_occurrences, inserted, skipped_duplicates, errors)
    """
    if calendar_series_service is None:
        from app.services.calendar_series_service import CalendarSeriesService
        calendar_series_service = CalendarSeriesService(self)
    
    series_rows = self.get_series_rows_to_process(table_name)
    stats = {
        'total_series': len(series_rows),
        'total_occurrences': 0,
        'inserted': 0,
        'skipped_duplicates': 0,
        'errors': 0
    }
    
    for series_row in series_rows:
        try:
            # Generiere alle Termine für diese Serie
            occurrences = calendar_series_service.generate_series_occurrences(
                series_row,
                until_date
            )
            
            stats['total_occurrences'] += len(occurrences)
            
            # Prüfe auf Duplikate und filtere sie heraus
            series_start_time = series_row.get('meeting_series_start_time')
            subject = series_row.get('subject', '')
            
            valid_occurrences = []
            for occ in occurrences:
                if self.check_occurrence_exists(
                    occ['start_date'],
                    subject,
                    series_start_time,
                    table_name
                ):
                    stats['skipped_duplicates'] += 1
                else:
                    valid_occurrences.append(occ)
            
            # Batch-Insert der gültigen Termine
            if valid_occurrences:
                inserted = self.insert_occurrences_batch(valid_occurrences, table_name)
                stats['inserted'] += inserted
            
        except Exception as e:
            logger.error(f"Fehler bei Verarbeitung von Serientermin {series_row.get('id')}: {str(e)}")
            stats['errors'] += 1
    
    return stats
```
## 5. Integration in den Verarbeitungsablauf
### 5.1 Erweiterung: `process_meeting_series_with_llm`
**Datei:** `/Volumes/Samsung 512GB/transcript-summarization/xstexport-service/app/services/db_service.py`
**Änderung:** Nach erfolgreicher LLM-Verarbeitung automatisch Termine generieren
**Implementierung:**
```python
async def process_meeting_series_with_llm(
    self, 
    table_name: str = "calendar_data",
    llm_service: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Orchestriert die gesamte LLM-Verarbeitung für Meeting-Series.
    Nach erfolgreicher LLM-Verarbeitung werden automatisch einzelne Termine generiert.
    
    Args:
        table_name: Name der Tabelle (Standard: "calendar_data")
        llm_service: Optionaler LLMService (wird erstellt falls None)
    
    Returns:
        Dictionary mit Statistik (total, success, failed, occurrences_stats)
    """
    # ... bestehender Code für LLM-Verarbeitung ...
    
    # Nach erfolgreicher LLM-Verarbeitung: Termine generieren
    try:
        from app.services.calendar_series_service import CalendarSeriesService
        calendar_series_service = CalendarSeriesService(self)
        
        occurrences_stats = self.process_series_to_occurrences(
            table_name,
            calendar_series_service
        )
        
        stats['occurrences_stats'] = occurrences_stats
        logger.info(f"Termin-Generierung abgeschlossen: {occurrences_stats}")
    except Exception as e:
        logger.warning(f"Termin-Generierung fehlgeschlagen: {str(e)}")
        # Nicht als kritischer Fehler behandeln
    
    return stats
```
### 5.2 Neuer Endpoint (optional)
**Datei:** `/Volumes/Samsung 512GB/transcript-summarization/xstexport-service/app/main.py`
**Endpoint:** `POST /generate-series-occurrences`
**Zweck:**
- Manuelle Auslösung der Termin-Generierung
- Nützlich für Re-Processing oder nach manuellen DB-Updates
**Implementierung:**
```python
@app.post("/generate-series-occurrences")
async def generate_series_occurrences(
    table_name: str = Form("calendar_data", description="Name der Tabelle"),
    until_date: Optional[str] = Form(None, description="Enddatum für Generierung (ISO 8601)")
):
    """
    Generiert einzelne Termine aus allen Serientermindefinitionen.
    """
    try:
        from app.services.calendar_series_service import CalendarSeriesService
        from datetime import datetime
        
        until_dt = None
        if until_date:
            until_dt = datetime.fromisoformat(until_date.replace('Z', '+00:00'))
        
        calendar_series_service = CalendarSeriesService(db_service)
        stats = db_service.process_series_to_occurrences(
            table_name,
            calendar_series_service,
            until_dt
        )
        
        return JSONResponse(
            content={
                "status": "success",
                "message": "Termin-Generierung abgeschlossen",
                "statistics": stats
            }
        )
    except Exception as e:
        logger.error(f"Fehler bei Termin-Generierung: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Fehler bei Termin-Generierung: {str(e)}"
        )
```
## 6. Duplikat-Erkennung
### 6.1 Strategie
Um zu verhindern, dass Termine mehrfach generiert werden:
1. **Prüfung vor Insert:** `check_occurrence_exists` prüft, ob ein Termin mit gleichem `start_date` und `subject` bereits existiert
2. **Serientermin-Ausschluss:** Der ursprüngliche Serientermin-Datensatz wird ausgeschlossen (über `meeting_series_start_time` Vergleich)
3. **Idempotenz:** Mehrfaches Ausführen der Generierung sollte keine Duplikate erzeugen
### 6.2 Alternative: Marker-Feld
Optional kann ein Marker-Feld hinzugefügt werden, um zu markieren, welche Serientermine bereits verarbeitet wurden:
```sql
ALTER TABLE calendar_data ADD COLUMN IF NOT EXISTS series_processed BOOLEAN DEFAULT FALSE;
```
Dann in `get_series_rows_to_process`:
```sql
WHERE meeting_series_start_time IS NOT NULL
  AND meeting_series_end_time IS NOT NULL
  AND meeting_series_frequency IS NOT NULL
  AND meeting_series_frequency != ''
  AND (series_processed IS NULL OR series_processed = FALSE)
```
Und nach erfolgreicher Generierung:
```sql
UPDATE calendar_data SET series_processed = TRUE WHERE id = :series_id
```
## 7. Fehlerbehandlung und Logging
### 7.1 Logging-Strategie
- **INFO:** Start/Ende der Termin-Generierung, Statistik
- **WARNING:** Einzelne Serientermin-Fehler, Duplikate übersprungen
- **ERROR:** Kritische Fehler (DB-Verbindung, RRULE-Parsing)
### 7.2 Fehlerbehandlung
- **RRULE-Parsing fehlgeschlagen:** Logge Warnung, überspringe Serientermin
- **Einzelner Termin-Fehler:** Weiter mit nächstem Termin
- **Batch-Insert fehlgeschlagen:** Rollback, logge Fehler, überspringe Serie
## 8. Performance-Überlegungen
### 8.1 Batch-Insert
- Verwende `execute_values` für Batch-Inserts (100-1000 Termine pro Batch)
- Reduziert DB-Roundtrips erheblich
### 8.2 Duplikat-Prüfung
- Prüfe Duplikate vor Batch-Insert, nicht währenddessen
- Optional: Index auf `(start_date, subject)` für schnellere Duplikat-Prüfung
### 8.3 Begrenzung der Generierung
- Standard: Generiere Termine bis `meeting_series_end_time` oder 1 Jahr in die Zukunft
- Konfigurierbar über Parameter `until_date`
## 9. Implementierungsreihenfolge
1. ✅ **requirements.txt erweitern** (python-dateutil hinzufügen)
2. ✅ **CalendarSeriesService erstellen** (calendar_series_service.py)
3. ✅ **DatabaseService erweitern** (get_series_rows_to_process, check_occurrence_exists, insert_occurrences_batch, process_series_to_occurrences)
4. ✅ **Integration in process_meeting_series_with_llm** (automatischer Aufruf nach LLM-Verarbeitung)
5. ✅ **Optional: Neuer Endpoint** (/generate-series-occurrences)

## 11. Rollback-Strategie
- **Bei Fehlern:** Nur fehlgeschlagene Serientermine werden nicht verarbeitet, bereits generierte Termine bleiben erhalten
- **Manuelle Löschung:** Über SQL möglich: `DELETE FROM calendar_data WHERE meeting_series_start_time IS NULL AND ...`
- **Re-Processing:** Über `/generate-series-occurrences` Endpoint möglich
## 12. Zukünftige Erweiterungen
- **Inkrementelle Generierung:** Nur neue Termine generieren (z.B. für laufende Serien)
- **Update bestehender Termine:** Wenn Serientermin geändert wird, aktualisiere entsprechende Termine
- **Löschung abgelaufener Termine:** Automatische Bereinigung alter Termine
- **Konfigurierbare Generierungsgrenze:** Über .env oder DB-Settings