from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import os
import logging
import subprocess
import json
import shutil
import tempfile
import zipfile
import platform
import pandas as pd

from app.services.calendar_extractor import extract_calendar_data, find_dll
from app.services.file_extractor import extract_calendar_from_existing_file, extract_calendar_from_zip
from app.services.file_service import list_app_files, list_data_directory_files
from app.services.pst_folder_service import list_pst_folders
from app.services.db_service import DatabaseService
from app.config.database import get_db_config
from app.services.mac_calendar_service import run_applescript, parse_calendar_xml

# Logger konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PST/OST Calendar Extractor API")

# Datenbank-Service initialisieren
db_config = get_db_config()
logger.info(f"Datenbankkonfiguration: {db_config}")
db_service = DatabaseService(db_config)

# CORS-Middleware für Cross-Origin-Anfragen hinzufügen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Im Produktivbetrieb einschränken
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Datenbank beim Start initialisieren
@app.on_event("startup")
async def startup_event():
    try:
        logger.info("Anwendung gestartet")
        # Tabelle erstellen, falls sie noch nicht existiert
        db_service.create_table_if_not_exists()
    except Exception as e:
        logger.error(f"Fehler beim Start: {str(e)}")
        raise

# Abhängigkeit für Form-Daten
async def get_form_data(
    file: UploadFile = File(...),
    format: str = Form("csv"),
    target_folder: Optional[str] = Form(None),
    return_file: bool = Form(False),
    pst_folder: str = Form("Calendar"),  # Parameter für Ordnernamen
    extract_all: bool = Form(False)  # Neuer Parameter für "alle Elemente extrahieren"
):
    return {
        "file": file,
        "format": format,
        "target_folder": target_folder,
        "return_file": return_file,
        "pst_folder": pst_folder,
        "extract_all": extract_all
    }

@app.post("/extract-calendar/")
async def extract_calendar(form_data: dict = Depends(get_form_data)):
    """
    Extrahiert Kalenderdaten oder alle Daten aus PST/OST-Dateien.
    
    Args:
        file: Die PST/OST-Datei
        format: Format der Extraktion ('csv' oder 'native')
        target_folder: Optionaler Zielordner (Standard: gleiches Verzeichnis wie Quelldatei)
        return_file: Ob die ZIP-Datei als Download zurückgegeben werden soll
        pst_folder: Name des Ordners in der PST-Datei, aus dem Kalender extrahiert werden sollen (Standard: "Calendar")
        extract_all: Ob alle Elemente aus der PST-Datei extrahiert werden sollen (Standard: False)
    
    Returns:
        Bei return_file=True: Die ZIP-Datei als Download
        Bei return_file=False: JSON-Antwort mit Pfad zur generierten ZIP-Datei
    """
    try:
        if form_data["extract_all"]:
            logger.info(f"Extraktion mit Format {form_data['format']} - Alle Elemente extrahieren")
        else:
            logger.info(f"Extraktion mit Format {form_data['format']} aus Ordner {form_data['pst_folder']} gestartet")
        
        result = await extract_calendar_data(
            form_data["file"], 
            form_data["format"], 
            form_data["target_folder"],
            form_data["pst_folder"],
            form_data["extract_all"]
        )
        
        if form_data["return_file"]:
            logger.info(f"Datei wird zurückgegeben: {result.zip_path}")
            return FileResponse(
                result.zip_path, 
                media_type="application/zip",
                filename=os.path.basename(result.zip_path)
            )
        else:
            logger.info(f"JSON-Antwort wird zurückgegeben: {result.zip_path}")
            return JSONResponse(
                content={
                    "status": "success",
                    "message": result.message,
                    "output_file": result.zip_path
                }
            )
    except Exception as e:
        logger.error(f"Fehler bei der Extraktion: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Fehler bei der Extraktion: {str(e)}"
        )

@app.post("/extract-calendar-from-file")
async def extract_calendar(
    file: UploadFile = File(..., description="Die zu verarbeitende Datei (ZIP, PST oder OST)"),
    format: str = Form("csv", description="Format der Extraktion ('csv' oder 'native')"),
    extract_all: bool = Form(False, description="Ob alle Elemente extrahiert werden sollen"),
    return_file: bool = Form(False, description="Ob die ZIP-Datei als Download zurückgegeben werden soll"),
    import_to_db: bool = Form(False, description="Ob die Daten in die Datenbank importiert werden sollen")
):
    """
    Extrahiert Kalenderdaten aus einer hochgeladenen Datei.
    Unterstützt .zip, .pst und .ost Dateien.
    """
    if not file:
        raise HTTPException(status_code=400, detail="Keine Datei hochgeladen")
        
    if not file.filename:
        raise HTTPException(status_code=400, detail="Kein Dateiname angegeben")
    
    temp_dir = None
    try:
        # Temporäres Verzeichnis erstellen
        temp_dir = tempfile.mkdtemp()
        logger.info(f"Temporäres Verzeichnis erstellt: {temp_dir}")
        
        # Datei speichern
        file_path = os.path.join(temp_dir, file.filename)
        logger.info(f"Speichere Datei: {file_path}")
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Datei verarbeiten
        if file.filename.endswith('.zip'):
            logger.info("Verarbeite ZIP-Datei")
            result = extract_calendar_from_zip(file_path)
            if result and 'calendar_path' in result:
                logger.info(f"Found Calendar.csv at: {result['calendar_path']}")
                
                # Daten in die Datenbank importieren, wenn gewünscht
                if import_to_db and format == 'csv':
                    try:
                        db_service.import_csv_to_db(result['calendar_path'])
                        logger.info("Daten erfolgreich in die Datenbank importiert")
                    except Exception as e:
                        logger.error(f"Fehler beim Importieren in die Datenbank: {str(e)}")
                        raise HTTPException(
                            status_code=500,
                            detail=f"Fehler beim Importieren in die Datenbank: {str(e)}"
                        )
                
                if 'temp_dir' in result:
                    shutil.rmtree(result['temp_dir'])
                return JSONResponse(
                    content={
                        "message": "Kalenderdaten erfolgreich extrahiert",
                        "status": "success"
                    }
                )
            else:
                raise HTTPException(status_code=400, detail="Keine Kalenderdaten in der ZIP-Datei gefunden")
                
        elif file.filename.endswith(('.pst', '.ost')):
            logger.info(f"Verarbeite {file.filename}")
            # PST/OST-Datei verarbeiten
            result = await extract_calendar_from_existing_file(
                file_path=file_path,
                format=format,
                extract_all=extract_all,
                return_file=return_file
            )
            
            if result and 'calendar_path' in result:
                logger.info(f"Found Calendar.csv at: {result['calendar_path']}")
                
                # Daten in die Datenbank importieren, wenn gewünscht
                if import_to_db and format == 'csv':
                    try:
                        db_service.import_csv_to_db(result['calendar_path'])
                        logger.info("Daten erfolgreich in die Datenbank importiert")
                    except Exception as e:
                        logger.error(f"Fehler beim Importieren in die Datenbank: {str(e)}")
                        raise HTTPException(
                            status_code=500,
                            detail=f"Fehler beim Importieren in die Datenbank: {str(e)}"
                        )
                
                if 'temp_dir' in result:
                    shutil.rmtree(result['temp_dir'])
                return JSONResponse(
                    content={
                        "message": "Kalenderdaten erfolgreich extrahiert",
                        "status": "success"
                    }
                )
            else:
                raise HTTPException(status_code=400, detail="Keine Kalenderdaten in der Datei gefunden")
        else:
            raise HTTPException(status_code=400, detail="Nicht unterstütztes Dateiformat. Nur ZIP, PST und OST Dateien werden unterstützt")
            
    except Exception as e:
        logger.error(f"Fehler bei der Extraktion: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if file.file:
            file.file.close()
        # Sicherstellen, dass alle temporären Verzeichnisse bereinigt werden
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logger.info(f"Temporäres Verzeichnis bereinigt: {temp_dir}")

@app.post("/list-pst-folders")
async def list_folders_endpoint(request: Request):
    """
    Listet alle Ordner in einer PST/OST-Datei auf.
    
    Body-Parameter:
        filename: Name der Datei im /data/ost-Verzeichnis
    
    Returns:
        JSON-Antwort mit einer Liste der Ordner in der PST-Datei
    """
    try:
        # JSON-Daten aus der Anfrage lesen
        body_bytes = await request.body()
        try:
            body_data = json.loads(body_bytes.decode('utf-8'))
        except Exception as e:
            logger.error(f"Fehler beim Parsen der JSON-Anfrage: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Ungültiges JSON-Format: {str(e)}"
            )
        
        # Prüfe auf erforderliche Felder
        filename = body_data.get("filename")
        if not filename:
            raise HTTPException(
                status_code=400,
                detail="Ein Dateiname muss angegeben werden"
            )
        
        # Pfad zur PST-Datei
        file_path = os.path.join("/data/ost", filename)
        
        # Ordner auflisten
        folders = await list_pst_folders(file_path)
        
        return JSONResponse(
            content={
                "status": "success",
                "filename": filename,
                "folders": folders
            }
        )
    except Exception as e:
        logger.error(f"Fehler beim Auflisten der Ordner: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=500,
            detail=f"Fehler beim Auflisten der Ordner: {str(e)}"
        )

@app.get("/health")
def health_check():
    """
    Endpoint zum Überprüfen der Anwendungsverfügbarkeit.
    """
    return {"status": "healthy", "version": "1.0.0"}

@app.get("/debug/files")
def list_files():
    """
    Zeigt den Inhalt des Anwendungsverzeichnisses für Debugging-Zwecke an.
    """
    return list_app_files()

@app.get("/data/files")
def list_data_files():
    """
    Zeigt den Inhalt des Datenverzeichnisses für Debugging-Zwecke an.
    """
    return list_data_directory_files()

@app.get("/debug/dotnet")
def debug_dotnet():
    """
    Testet die .NET-Laufzeit und gibt Debug-Informationen zurück.
    """
    try:
        process = subprocess.run(
            ["dotnet", "--info"],
            capture_output=True,
            text=False
        )
        
        dotnet_info = process.stdout.decode('utf-8', errors='replace')
        dotnet_error = process.stderr.decode('utf-8', errors='replace') if process.stderr else None
        
        # Prüfe DLL-Existenz
        dll_path = find_dll("XstExporter.Portable.dll")
        dll_exists = os.path.exists(dll_path)
        
        return {
            "dotnet_info": dotnet_info,
            "dotnet_error": dotnet_error,
            "exit_code": process.returncode,
            "dll_path": dll_path,
            "dll_exists": dll_exists,
            "dotnet_environment": {
                "DOTNET_SYSTEM_GLOBALIZATION_INVARIANT": os.environ.get("DOTNET_SYSTEM_GLOBALIZATION_INVARIANT", "Nicht gesetzt")
            }
        }
    except Exception as e:
        return {
            "error": str(e)
        }

@app.post("/mac/export-calendar")
async def export_mac_calendar(import_to_db: bool = False):
    """
    Exportiert Kalenderdaten von macOS über ein AppleScript, parst die XML und fügt sie optional in die Datenbank ein.
    """
    logger.info(f"[mac/export-calendar] platform.system() = {platform.system()}")
    logger.info(f"[mac/export-calendar] SSH_USER={os.getenv('SSH_USER')}, SSH_HOST={os.getenv('SSH_HOST')}")
    # Plattform-Check entfernt, da SSH-Workflow genutzt wird
    try:
        xml_path = run_applescript()
        events = parse_calendar_xml(xml_path)
        num_events = len(events)
        if import_to_db and num_events > 0:
            db_service.insert_calendar_events(events, truncate=True)
        return {
            "status": "success",
            "num_events": num_events,
            "xml_path": str(xml_path),
            "imported": bool(import_to_db and num_events > 0)
        }
    except Exception as e:
        logger.error(f"Fehler beim Exportieren des macOS-Kalenders: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/debug/analyze-csv-timestamps")
async def analyze_csv_timestamps(file: UploadFile = File(...)):
    """Debug-Endpoint zur Analyse von Timestamp-Formaten in CSV-Dateien."""
    try:
        # Temporäre Datei erstellen
        temp_file = f"/tmp/debug_{file.filename}"
        with open(temp_file, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Verschiedene Encodings versuchen
        encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'iso-8859-1', 'windows-1252', 'cp1252']
        df = None
        
        for encoding in encodings:
            try:
                logger.info(f"Debug: Versuche CSV mit Encoding '{encoding}' zu lesen")
                
                # Versuche zuerst mit Semikolon
                try:
                    df = pd.read_csv(temp_file, sep=';', encoding=encoding, low_memory=False)
                    logger.info(f"Debug: CSV erfolgreich mit Semikolon und Encoding '{encoding}' gelesen")
                    break
                except Exception as e:
                    logger.warning(f"Debug: Fehler beim Lesen mit Semikolon und Encoding '{encoding}': {str(e)}, versuche mit Komma")
                    try:
                        df = pd.read_csv(temp_file, sep=',', encoding=encoding, low_memory=False)
                        logger.info(f"Debug: CSV erfolgreich mit Komma und Encoding '{encoding}' gelesen")
                        break
                    except Exception as e2:
                        logger.warning(f"Debug: Fehler beim Lesen mit Komma und Encoding '{encoding}': {str(e2)}")
                        continue
                        
            except Exception as e:
                logger.warning(f"Debug: Fehler beim Lesen mit Encoding '{encoding}': {str(e)}")
                continue
        
        if df is None:
            raise ValueError(f"Konnte CSV-Datei mit keinem der Encodings {encodings} lesen")
        
        # Bereinige Spaltennamen
        df.columns = df.columns.str.replace('"', '').str.strip()
        
        # Überprüfe, ob die Spaltennamen als einzelner String gelesen wurden
        if len(df.columns) == 1 and ';' in df.columns[0]:
            # Teile die Spaltennamen
            column_names = df.columns[0].split(';')
            # Erstelle ein neues DataFrame mit den korrekten Spaltennamen
            df = pd.read_csv(temp_file, sep=';', encoding=encoding, names=column_names, skiprows=1, low_memory=False)
            logger.info("Debug: Spaltennamen wurden korrekt aufgeteilt")
        
        # Rest der Analyse bleibt gleich
        analysis = {
            "filename": file.filename,
            "total_rows": len(df),
            "columns": list(df.columns),
            "timestamp_columns": [],
            "sample_data": {}
        }
        
        # Suche nach Timestamp-Spalten
        timestamp_patterns = ['date', 'time', 'start', 'end', 'datum', 'zeit', 'beginn', 'ende']
        for col in df.columns:
            col_lower = col.lower()
            if any(pattern in col_lower for pattern in timestamp_patterns):
                analysis["timestamp_columns"].append(col)
                
                # Analysiere die ersten 5 nicht-leeren Werte
                non_null_values = df[col].dropna().head(5)
                analysis["sample_data"][col] = {
                    "data_types": [str(type(val).__name__) for val in non_null_values],
                    "values": [str(val) for val in non_null_values],
                    "null_count": df[col].isnull().sum()
                }
        
        # Entferne temporäre Datei
        os.remove(temp_file)
        
        return analysis
        
    except Exception as e:
        logger.error(f"Fehler bei CSV-Analyse: {str(e)}")
        # Entferne temporäre Datei falls vorhanden
        try:
            if 'temp_file' in locals():
                os.remove(temp_file)
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Fehler bei CSV-Analyse: {str(e)}")