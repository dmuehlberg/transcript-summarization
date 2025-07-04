# Debugging: NULL-Werte in Timestamp-Feldern

## Problem
Nach der Implementierung der Zeitzonenunterstützung zeigen `start_date`, `end_date` und andere Timestamp-Felder NULL-Werte in der Datenbank.

## Debugging-Schritte

### 1. Debug-Logging aktivieren

Fügen Sie in der `.env`-Datei hinzu:
```bash
LOG_LEVEL=DEBUG
```

### 2. CSV-Analyse durchführen

Verwenden Sie den neuen Debug-Endpoint:

```bash
curl -X POST "http://localhost:8200/debug/analyze-csv-timestamps" \
  -F "file=@Calendar.csv"
```

Dies zeigt:
- Welche Timestamp-Formate in der CSV stehen
- Ob das Parsing erfolgreich ist
- Wo die Konvertierung fehlschlägt

### 3. Container-Logs prüfen

```bash
docker-compose logs xstexport-service
```

Suchen Sie nach:
- `"Beispieldaten vor Konvertierung"`
- `"Beispieldaten nach Konvertierung"`
- `"Fehler bei Zeile"`
- `"Konnte Timestamp nicht parsen"`

### 4. Häufige Probleme und Lösungen

#### Problem 1: Unbekannte Timestamp-Formate
**Symptom:** `"Konnte Timestamp nicht parsen"`
**Lösung:** Neue Formate in `timezone_utils.py` hinzufügen

#### Problem 2: Leere/NaN-Werte
**Symptom:** `"Timestamp ist leer/None"`
**Lösung:** Datenbereinigung vor Import

#### Problem 3: Zeitzonenkonvertierung fehlgeschlagen
**Symptom:** `"Zeitzonenkonvertierung fehlgeschlagen"`
**Lösung:** TIMEZONE-Einstellung prüfen

### 5. Temporäre Lösung: Zeitzonenkonvertierung deaktivieren

Falls das Problem weiterhin besteht, können Sie die Zeitzonenkonvertierung temporär deaktivieren:

```bash
# In .env setzen:
TIMEZONE=UTC
```

### 6. Manuelle Datenbankprüfung

```sql
-- Prüfen Sie die tatsächlichen Werte in der Datenbank
SELECT 
    start_date, 
    end_date, 
    creation_time,
    COUNT(*) as count
FROM calendar_data 
GROUP BY start_date, end_date, creation_time
LIMIT 10;
```

## Erwartete Debug-Ausgabe

### Erfolgreiche Konvertierung:
```
INFO: Beispieldaten vor Konvertierung (start_date): ['2025-01-15 14:00:00', '2025-01-16 09:30:00']
INFO: Timestamp erfolgreich geparst mit Format '%Y-%m-%d %H:%M:%S': 2025-01-15 14:00:00
INFO: Zeitzonenkonvertierung erfolgreich: 2025-01-15 14:00:00 -> 2025-01-15 15:00:00
INFO: Beispieldaten nach Konvertierung (start_date): [2025-01-15 15:00:00, 2025-01-16 10:30:00]
```

### Fehlgeschlagene Konvertierung:
```
ERROR: Konnte Timestamp nicht parsen: '15.01.2025 14:00'
ERROR: Fehler bei Zeile 5, Wert '15.01.2025 14:00' für Feld start_date: ...
```

## Nächste Schritte

1. **Führen Sie die CSV-Analyse durch** und teilen Sie die Ergebnisse mit
2. **Prüfen Sie die Container-Logs** auf spezifische Fehlermeldungen
3. **Testen Sie mit einer kleinen CSV-Datei** (1-2 Zeilen)
4. **Prüfen Sie das ursprüngliche Timestamp-Format** in der PST-Datei

## Support

Falls das Problem weiterhin besteht, teilen Sie bitte mit:
- Ausgabe von `/debug/analyze-csv-timestamps`
- Relevante Container-Logs
- Beispieldaten aus der CSV-Datei 