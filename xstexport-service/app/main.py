from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional
import os

from app.services.calendar_extractor import extract_calendar_data

app = FastAPI(title="PST/OST Calendar Extractor API")

@app.post("/extract-calendar/")
async def extract_calendar(
    file: UploadFile = File(...),
    format: str = Form("csv"),
    target_folder: Optional[str] = Form(None),
    return_file: bool = Form(False)  # Neuer Parameter, ob die Datei zurückgegeben werden soll
):
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
    result = await extract_calendar_data(file, format, target_folder)
    
    if return_file:
        return FileResponse(
            result.zip_path, 
            media_type="application/zip",
            filename=os.path.basename(result.zip_path)
        )
    else:
        return JSONResponse(
            content={
                "status": "success",
                "message": result.message,
                "output_file": result.zip_path
            }
        )

@app.get("/health")
def health_check():
    """
    Endpoint zum Überprüfen der Anwendungsverfügbarkeit.
    """
    return {"status": "healthy", "version": "1.0.0"}