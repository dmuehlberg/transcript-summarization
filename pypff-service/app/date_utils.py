# date_utils.py
import struct
from datetime import datetime, timedelta
from fastapi import UploadFile, File, Form, HTTPException

def convert_filetime_to_datetime(filetime_bytes):
    """
    Konvertiert einen binären FILETIME-Wert (8 Bytes) in ein lesbares Datum.
    
    FILETIME ist ein 64-Bit-Wert, der die Anzahl der 100-Nanosekunden-Intervalle 
    seit dem 1. Januar 1601 darstellt.
    
    Args:
        filetime_bytes: FILETIME als Bytes-Objekt
        
    Returns:
        Ein ISO-formatierter Datumsstring oder None bei Fehler
    """
    if not filetime_bytes or len(filetime_bytes) != 8:
        return None
        
    try:
        # Bytes in eine 64-Bit-Ganzzahl konvertieren (little-endian)
        filetime = int.from_bytes(filetime_bytes, byteorder='little')
        
        # FILETIME in einen Unix-Timestamp umwandeln
        # FILETIME ist die Anzahl der 100-Nanosekunden-Intervalle seit dem 1. Januar 1601
        # Unix-Timestamp ist die Anzahl der Sekunden seit dem 1. Januar 1970
        # Differenz in Sekunden zwischen 1601-01-01 und 1970-01-01
        epoch_diff = 11644473600
        
        # Umrechnen von 100-Nanosekunden in Sekunden und Epochendifferenz abziehen
        unix_timestamp = filetime / 10000000 - epoch_diff
        
        # In ein Datetime-Objekt umwandeln
        import datetime
        dt = datetime.datetime.fromtimestamp(unix_timestamp)
        
        # Als ISO-Format zurückgeben
        return dt.isoformat()
    except Exception as e:
        print(f"Fehler bei der Datumskonvertierung: {str(e)}")
        return f"Binäres Datum: {filetime_bytes.hex()}"

def try_convert_binary_date(value, formats=None):
    """
    Versucht, einen binären Wert in ein Datum zu konvertieren, indem verschiedene Formate ausprobiert werden.
    
    Args:
        value: Der zu konvertierende binäre Wert (bytes)
        formats: Optionale Liste von zu versuchenden Formaten 
                 (gültige Werte: 'filetime', 'ole', 'unix', 'systemtime')
                 
    Returns:
        Ein ISO-formatierter Datumsstring oder None bei Fehler
    """
    if not formats:
        formats = ['filetime', 'ole', 'systemtime', 'unix']
    
    if not value or not isinstance(value, bytes):
        return None
    
    results = {}
    
    # 1. FILETIME-Format testen (8 Bytes)
    if 'filetime' in formats and len(value) >= 8:
        try:
            filetime_data = value[:8]
            date = convert_filetime_to_datetime(filetime_data)
            if date:
                results['filetime'] = date
        except Exception:
            pass
    
    # 2. OLE Automation Date testen (8 Bytes als Double)
    if 'ole' in formats and len(value) >= 8:
        try:
            import struct
            double_data = value[:8]
            double_value = struct.unpack('<d', double_data)[0]
            
            # OLE Datum (Tage seit 30.12.1899)
            import datetime
            base_date = datetime.datetime(1899, 12, 30)
            
            days = int(double_value)
            day_fraction = double_value - days
            
            date_part = base_date + datetime.timedelta(days=days)
            seconds = int(day_fraction * 86400)
            time_part = datetime.timedelta(seconds=seconds)
            
            ole_date = date_part + time_part
            
            # Plausibilitätsprüfung
            if 0 <= double_value <= 2958465:  # Etwa bis zum Jahr 9999
                results['ole'] = ole_date.isoformat()
        except Exception:
            pass
    
    # 3. Unix-Timestamp testen (4 Bytes)
    if 'unix' in formats and len(value) >= 4:
        try:
            unix_data = value[:4]
            unix_timestamp = int.from_bytes(unix_data, byteorder='little')
            
            import datetime
            unix_date = datetime.datetime.fromtimestamp(unix_timestamp)
            
            # Plausibilitätsprüfung: Zwischen 1980 und 2040
            if 315532800 <= unix_timestamp <= 2208988800:
                results['unix'] = unix_date.isoformat()
        except Exception:
            pass
    
    # 4. SYSTEMTIME-Struktur testen (16 Bytes)
    if 'systemtime' in formats and len(value) >= 16:
        try:
            systemtime_data = value[:16]
            year = int.from_bytes(systemtime_data[0:2], byteorder='little')
            month = int.from_bytes(systemtime_data[2:4], byteorder='little')
            day = int.from_bytes(systemtime_data[6:8], byteorder='little')
            hour = int.from_bytes(systemtime_data[8:10], byteorder='little')
            minute = int.from_bytes(systemtime_data[10:12], byteorder='little')
            second = int.from_bytes(systemtime_data[12:14], byteorder='little')
            millisecond = int.from_bytes(systemtime_data[14:16], byteorder='little')
            
            if (1601 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31 and
                0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
                
                import datetime
                try:
                    systemtime_date = datetime.datetime(
                        year, month, day, hour, minute, second, millisecond * 1000
                    )
                    results['systemtime'] = systemtime_date.isoformat()
                except ValueError:
                    pass
        except Exception:
            pass
    
    # Ergebnisse auswerten
    if results:
        # Prioritätsreihenfolge: FILETIME, SYSTEMTIME, OLE, UNIX
        for fmt in ['filetime', 'systemtime', 'ole', 'unix']:
            if fmt in results:
                return results[fmt]
        
        # Falls die Prioritätsformate nicht vorhanden sind, erstes gefundenes Ergebnis nehmen
        return next(iter(results.values()))
    
    return None

async def convert_binary_date(
    file: UploadFile = File(None),
    hex_value: str = Form(None)
):
    """
    Konvertiert binäre Datumswerte aus PST-Dateien in lesbare Formate.
    
    Parameters:
    - file: Optional, eine Datei, die binäre Daten enthält
    - hex_value: Optional, ein Hex-String (z.B. "0080F29544A5CA01")
    """
    result = {
        "input_type": None,
        "input_value": None,
        "converted_date": None,
        "datetime_formats": {},
        "error": None
    }
    
    try:
        # Entweder Datei oder Hex-Wert verwenden
        binary_data = None
        
        if hex_value:
            result["input_type"] = "hex_string"
            result["input_value"] = hex_value
            # Hex-String in Bytes umwandeln
            try:
                # Leerzeichen entfernen und in Bytes konvertieren
                cleaned_hex = hex_value.replace(" ", "")
                binary_data = bytes.fromhex(cleaned_hex)
            except Exception as e:
                result["error"] = f"Ungültiger Hex-String: {str(e)}"
                return result
        
        elif file:
            result["input_type"] = "file"
            # Datei lesen (maximal die ersten 1024 Bytes)
            content = await file.read(1024)
            binary_data = content
            result["input_value"] = content.hex()
        
        else:
            result["error"] = "Es muss entweder eine Datei oder ein Hex-Wert angegeben werden"
            return result
        
        # Analysieren der Bytes für verschiedene Datumsformate
        
        # 1. FILETIME (8 Bytes)
        if len(binary_data) >= 8:
            try:
                filetime_data = binary_data[:8]
                filetime_date = convert_filetime_to_datetime(filetime_data)
                if filetime_date:
                    result["datetime_formats"]["filetime"] = {
                        "description": "Windows FILETIME (8 Bytes, 100-Nanosekunden seit 1601-01-01)",
                        "bytes": filetime_data.hex(),
                        "date": filetime_date
                    }
                    
                    # Den ersten erfolgreichen Wert als Hauptergebnis setzen
                    if not result["converted_date"]:
                        result["converted_date"] = filetime_date
            except Exception as e:
                result["datetime_formats"]["filetime_error"] = str(e)
        
        # 2. OLE Automation Date (8 Bytes, Doublewert)
        if len(binary_data) >= 8:
            try:
                import struct
                double_data = binary_data[:8]
                # Als Double dekodieren
                double_value = struct.unpack('<d', double_data)[0]
                
                # OLE Automation Datum: Anzahl der Tage seit 30.12.1899
                # Ganzzahliger Teil = Tage, Bruchteil = Tagesanteil
                import datetime
                base_date = datetime.datetime(1899, 12, 30)
                
                days = int(double_value)
                day_fraction = double_value - days
                
                # Datumsteil berechnen
                date_part = base_date + datetime.timedelta(days=days)
                
                # Tagesbruchteil in Stunden/Minuten/Sekunden umrechnen
                seconds = int(day_fraction * 86400)  # 24*60*60 Sekunden pro Tag
                time_part = datetime.timedelta(seconds=seconds)
                
                # Kombiniertes Datum
                ole_date = date_part + time_part
                
                if 0 <= double_value <= 2958465:  # Plausibilitätsprüfung
                    result["datetime_formats"]["ole_automation"] = {
                        "description": "OLE Automation Date (8 Bytes Double, Tage seit 1899-12-30)",
                        "bytes": double_data.hex(),
                        "double_value": double_value,
                        "date": ole_date.isoformat()
                    }
                    
                    # Als Hauptergebnis setzen, falls noch nicht gesetzt
                    if not result["converted_date"]:
                        result["converted_date"] = ole_date.isoformat()
            except Exception as e:
                result["datetime_formats"]["ole_automation_error"] = str(e)
        
        # 3. Unix-Timestamp (4 Bytes, Sekunden seit 1970-01-01)
        if len(binary_data) >= 4:
            try:
                unix_data = binary_data[:4]
                # Als 32-Bit Integer dekodieren
                unix_timestamp = int.from_bytes(unix_data, byteorder='little')
                
                # In Datetime umwandeln
                import datetime
                unix_date = datetime.datetime.fromtimestamp(unix_timestamp)
                
                # Plausibilitätsprüfung: Zwischen 1980 und 2040
                if 315532800 <= unix_timestamp <= 2208988800:
                    result["datetime_formats"]["unix_timestamp"] = {
                        "description": "Unix-Timestamp (4 Bytes, Sekunden seit 1970-01-01)",
                        "bytes": unix_data.hex(),
                        "timestamp": unix_timestamp,
                        "date": unix_date.isoformat()
                    }
                    
                    # Als Hauptergebnis setzen, falls noch nicht gesetzt
                    if not result["converted_date"]:
                        result["converted_date"] = unix_date.isoformat()
            except Exception as e:
                result["datetime_formats"]["unix_timestamp_error"] = str(e)
        
        # 4. Windows SYSTEMTIME-Struktur (16 Bytes)
        if len(binary_data) >= 16:
            try:
                systemtime_data = binary_data[:16]
                # SYSTEMTIME-Struktur: Jahr, Monat, Tag, Wochentag, Stunde, Minute, Sekunde, Millisekunde
                # Jeweils als 16-Bit-Wort (2 Bytes)
                year = int.from_bytes(systemtime_data[0:2], byteorder='little')
                month = int.from_bytes(systemtime_data[2:4], byteorder='little')
                day = int.from_bytes(systemtime_data[6:8], byteorder='little')
                hour = int.from_bytes(systemtime_data[8:10], byteorder='little')
                minute = int.from_bytes(systemtime_data[10:12], byteorder='little')
                second = int.from_bytes(systemtime_data[12:14], byteorder='little')
                millisecond = int.from_bytes(systemtime_data[14:16], byteorder='little')
                
                # Plausibilitätsprüfung
                if (1601 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31 and
                    0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
                    
                    import datetime
                    try:
                        systemtime_date = datetime.datetime(
                            year, month, day, hour, minute, second, millisecond * 1000
                        )
                        
                        result["datetime_formats"]["systemtime"] = {
                            "description": "Windows SYSTEMTIME (16 Bytes)",
                            "bytes": systemtime_data.hex(),
                            "year": year,
                            "month": month,
                            "day": day,
                            "hour": hour,
                            "minute": minute,
                            "second": second,
                            "millisecond": millisecond,
                            "date": systemtime_date.isoformat()
                        }
                        
                        # Als Hauptergebnis setzen, falls noch nicht gesetzt
                        if not result["converted_date"]:
                            result["converted_date"] = systemtime_date.isoformat()
                    except ValueError:
                        # Ungültiges Datum
                        pass
            except Exception as e:
                result["datetime_formats"]["systemtime_error"] = str(e)
        
        # Wenn kein Format erkannt wurde
        if not result["converted_date"] and not result["error"]:
            result["error"] = "Keine bekannten Datumsformate erkannt"
        
        return result
        
    except Exception as e:
        result["error"] = f"Allgemeiner Fehler: {str(e)}"
        return result