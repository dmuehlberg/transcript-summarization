from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import os
import logging

from app.services.calendar_extractor import extract_calendar_data
from app.services.file_extractor import extract_calendar_from_existing_file
from app.services.file_service import list_app_files, list_data_directory_files

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
    return_file: bool = Form(False)
):
    return {
        "file": file,
        "format": format,
        "target_folder": target_folder,
        "return_file": return_file
    }

@app.post("/extract-calendar/")
async def extract_calendar(form_data: dict = Depends(get_form_data)):
    """
    Extrahiert Kalenderdaten aus PST/OST-Dateien.
    
    Args:
        file: Die PST/OST-Datei
        format: Format der Extraktion ('csv' oder 'native')
        target_folder: Optionaler Zielordner (Standard: gleiches Verzeichnis wie Quelldatei)
        return_file: Ob die ZIP-Datei als Download zurückgegeben werden soll
    
    Returns:
        Bei return_file=True: Die ZIP-Datei als Download
        Bei return_file=False: JSON-Antwort mit Pfad zur generierten ZIP-Datei
    """
    try:
        logger.info(f"Extraktion mit Format {form_data['format']} gestartet")
        
        result = await extract_calendar_data(
            form_data["file"], 
            form_data["format"], 
            form_data["target_folder"]
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
    Extrahiert Kalenderdaten aus einer vorhandenen PST/OST-Datei im Container.
    
    Body-Parameter:
        filename: Name der Datei im /data/ost-Verzeichnis
        format: Format der Extraktion ('csv' oder 'native')
        target_folder: Optionaler Zielordner (Standard: gleiches Verzeichnis wie Quelldatei)
        return_file: Ob die ZIP-Datei als Download zurückgegeben werden soll
    
    Returns:
        Bei return_file=True: Die ZIP-Datei als Download
        Bei return_file=False: JSON-Antwort mit Pfad zur generierten ZIP-Datei
    """
    return await extract_calendar_from_existing_file(request)

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