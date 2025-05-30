from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import os
import logging
import subprocess
import json

from app.services.calendar_extractor import extract_calendar_data, find_dll
from app.services.file_extractor import extract_calendar_from_existing_file
from app.services.file_service import list_app_files, list_data_directory_files
from app.services.pst_folder_service import list_pst_folders

# Logger konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PST/OST Calendar Extractor API")

# CORS-Middleware für Cross-Origin-Anfragen hinzufügen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Im Produktivbetrieb einschränken
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# Alternativer Endpunkt, der eine zuvor existierende Datei verwendet
@app.post("/extract-calendar-from-file")
async def extract_calendar_file_endpoint(request: Request):
    """
    Extrahiert Kalenderdaten oder alle Daten aus einer vorhandenen PST/OST-Datei im Container.
    
    Body-Parameter:
        filename: Name der Datei im /data/ost-Verzeichnis
        format: Format der Extraktion ('csv' oder 'native')
        target_folder: Optionaler Zielordner (Standard: gleiches Verzeichnis wie Quelldatei)
        return_file: Ob die ZIP-Datei als Download zurückgegeben werden soll
        pst_folder: Name des Ordners in der PST-Datei (Standard: "Calendar")
        extract_all: Ob alle Elemente extrahiert werden sollen (Standard: False)
    
    Returns:
        Bei return_file=True: Die ZIP-Datei als Download
        Bei return_file=False: JSON-Antwort mit Pfad zur generierten ZIP-Datei
    """
    return await extract_calendar_from_existing_file(request)

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