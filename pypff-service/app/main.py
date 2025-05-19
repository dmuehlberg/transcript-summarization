from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse
import os

# Importe aus den neu erstellten Modulen
from extractor import export_pffexport
from calendar_service import (
    export_calendar,
    export_calendar_debug,
    advanced_calendar_extraction
)
from debug_tools import (
    pffexport_help,
    check_system_tools,
    pffexport_options,
    raw_pst_inspector,
    inspect_calendar_properties
)
from file_utils import export_simple, download_file
from date_utils import convert_binary_date

app = FastAPI()

# Export-Endpoints
@app.post("/export/pffexport")
async def export_pffexport_endpoint(
    file: UploadFile = File(...),
    scope: str = Form("all")  # Optionen: all, debug, items, recovered
):
    """
    Exportiert Items (inkl. Kalender) via pffexport CLI.
    
    Parameter:
    - file: PST/OST-Datei zum Exportieren
    - scope: Export-Modus (all, debug, items, recovered)
    """
    return await export_pffexport(file, scope)

@app.post("/export/simple")
async def export_simple_endpoint(
    file: UploadFile = File(...),
    item_type: str = Form("all")  # Optionen: all, message, appointment, contact
):
    """
    Einfache Version des Exports, die das ZIP-File direkt ins /data/ost Verzeichnis schreibt,
    aus dem auch die PST-Dateien gelesen werden.
    """
    return await export_simple(file, item_type)

@app.get("/download/{filename}")
async def download_file_endpoint(filename: str):
    """
    Endpunkt zum direkten Download einer Datei aus dem /data/ost Verzeichnis.
    """
    return await download_file(filename)

# Kalender-Endpoints
@app.post("/export/calendar")
async def export_calendar_endpoint(
    file: UploadFile = File(...),
    extended: bool = Form(False)  # Erweiterte Eigenschaften für Kalendereinträge extrahieren
):
    """
    Exportiert speziell Kalendereinträge aus PST/OST-Dateien mit Fokus auf die relevanten Eigenschaften.
    
    Parameters:
    - file: PST/OST-Datei
    - extended: Falls true, werden zusätzliche MAPI-Eigenschaften extrahiert
    """
    return await export_calendar(file, extended)

@app.post("/export/calendar-debug")
async def export_calendar_debug_endpoint(
    file: UploadFile = File(...),
    extended: bool = Form(False),
    debug_mode: bool = Form(True)  # Aktiviert das Debugging
):
    """
    Exportiert Kalendereinträge mit zusätzlichen Debugging-Informationen.
    
    Parameters:
    - file: PST/OST-Datei
    - extended: Falls true, werden zusätzliche MAPI-Eigenschaften extrahiert
    - debug_mode: Speichert zusätzliche Debugging-Informationen
    """
    return await export_calendar_debug(file, extended, debug_mode)

@app.post("/calendar/advanced")
async def advanced_calendar_extraction_endpoint(
    file: UploadFile = File(...),
    folder_path: str = Form(""),  # Optionaler spezifischer Kalenderpfad
    export_format: str = Form("json"),  # Format: json oder text
    use_extended_props: bool = Form(True)  # Erweiterte Eigenschaftssuche aktivieren
):
    """
    Erweiterter Kalenderexport mit verbesserten Methoden zur Eigenschaftsextraktion
    
    Parameters:
    - file: PST/OST-Datei
    - folder_path: Optionaler Pfad zum Kalenderordner (leer = automatische Suche)
    - export_format: Ausgabeformat (json oder text)
    - use_extended_props: Aktiviert die erweiterte Suche nach Kalendereigenschaften
    """
    return await advanced_calendar_extraction(file, folder_path, export_format, use_extended_props)

# Debug-Endpoints
@app.get("/debug/pffexport-help")
async def pffexport_help_endpoint():
    """
    Zeigt die Hilfe-Ausgabe des pffexport-Tools an, um die korrekten Optionen zu ermitteln.
    """
    return await pffexport_help()

@app.get("/debug/check-tools")
async def check_system_tools_endpoint():
    """
    Überprüft, welche relevanten Tools im System installiert sind.
    """
    return await check_system_tools()

@app.get("/debug/pffexport-options")
async def pffexport_options_endpoint():
    """
    Versucht auf verschiedene Weisen, die verfügbaren Optionen des pffexport-Tools zu ermitteln.
    """
    return await pffexport_options()

@app.post("/debug/raw-pst")
async def raw_pst_inspector_endpoint(
    file: UploadFile = File(...),
    folder_path: str = Form("/")  # Optionaler Pfad zu einem bestimmten Ordner
):
    """
    Analysiert eine PST-Datei auf niedrigster Ebene, um alle zugänglichen Informationen zu extrahieren.
    
    Parameters:
    - file: PST/OST-Datei
    - folder_path: Optionaler Pfad zu einem bestimmten Ordner (z.B. "/Top of Personal Folders/Kalender")
    """
    return await raw_pst_inspector(file, folder_path)

@app.post("/debug/inspect-calendar-properties")
async def inspect_calendar_properties_endpoint(
    file: UploadFile = File(...),
    folder_path: str = Form(""),  # Optionaler Pfad zum Kalenderordner
    max_items: int = Form(5)      # Maximale Anzahl zu inspizierender Kalendereinträge
):
    """
    Inspiziert detailliert die Kalendereigenschaften in einer PST-Datei.
    
    Besonders nützlich, um alle verfügbaren Eigenschaften und ihre Werte anzuzeigen,
    damit die korrekten Property-IDs für die Kalenderextraktion bestimmt werden können.
    
    Parameters:
    - file: PST/OST-Datei
    - folder_path: Optionaler Pfad zum spezifischen Kalenderordner
    - max_items: Maximale Anzahl zu inspizierender Kalendereinträge
    """
    return await inspect_calendar_properties(file, folder_path, max_items)

@app.post("/tools/convert-binary-date")
async def convert_binary_date_endpoint(
    file: UploadFile = File(None),
    hex_value: str = Form(None)
):
    """
    Konvertiert binäre Datumswerte aus PST-Dateien in lesbare Formate.
    
    Parameters:
    - file: Optional, eine Datei, die binäre Daten enthält
    - hex_value: Optional, ein Hex-String (z.B. "0080F29544A5CA01")
    """
    return await convert_binary_date(file, hex_value)

@app.post("/debug/message-diagnostics")
async def message_diagnostics(
    file: UploadFile = File(...),
    folder_path: str = Form(""),
    index: int = Form(0)
):
    """
    Zeigt detaillierte Diagnose-Informationen für eine bestimmte Nachricht.
    
    Parameters:
    - file: PST/OST-Datei
    - folder_path: Pfad zum Ordner (z.B. "/Unnamed/Top of Personal Folders/mail@david-muehlberg.de/Kalender")
    - index: Index der Nachricht im Ordner (z.B. 0, 1, 2, ...)
    """
    try:
        # Speichere die Datei temporär
        temp_file = f"/tmp/diagnostic_{datetime.now().strftime('%Y%m%d%H%M%S')}.pst"
        with open(temp_file, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Öffne die PST-Datei
        pst = pypff.file()
        pst.open(temp_file)
        root_folder = pst.get_root_folder()
        
        # Finde den angegebenen Ordner
        target_folder = root_folder
        if folder_path:
            target_folder = find_folder_by_path(root_folder, folder_path)
            if not target_folder:
                return {"error": f"Ordner nicht gefunden: {folder_path}"}
        
        # Prüfe, ob der Index gültig ist
        if index < 0 or index >= target_folder.number_of_sub_messages:
            return {"error": f"Ungültiger Index: {index}. Der Ordner hat {target_folder.number_of_sub_messages} Nachrichten."}
        
        # Hole die Nachricht
        msg = target_folder.get_sub_message(index)
        
        # Sammle Diagnose-Informationen
        diagnostics = inspect_message_diagnostics(msg)
        
        # Versuche aggressiv, alle Properties zu extrahieren
        properties = extract_all_properties_enhanced(msg)
        
        # Füge auch die rohen Bytes der ersten 200 Byte der Nachricht hinzu
        try:
            if hasattr(msg, "get_data"):
                data = msg.get_data()
                if data:
                    diagnostics["raw_data_preview"] = data[:200].hex()
        except Exception as e:
            diagnostics["raw_data_error"] = str(e)
        
        return {
            "success": True,
            "message": f"Diagnose für Nachricht {index} in {folder_path}",
            "diagnostics": diagnostics,
            "properties": properties
        }
    
    except Exception as e:
        return {"success": False, "message": f"Fehler: {str(e)}"}
    
    finally:
        if 'pst' in locals():
            pst.close()
        if os.path.exists(temp_file):
            os.remove(temp_file)