import os
import subprocess
import tempfile
import shutil
from typing import Optional, Dict, Any
from fastapi import UploadFile, HTTPException
from pydantic import BaseModel

from app.models.request_models import CalendarExtractionParams
from app.utils.file_utils import cleanup_temp_dir

class ExtractionResult(BaseModel):
    zip_path: str
    message: str

async def extract_calendar_data(
    file: UploadFile, 
    params: CalendarExtractionParams
) -> ExtractionResult:
    """
    Extrahiert Kalenderdaten aus einer PST/OST-Datei.
    
    Args:
        file: Die hochgeladene PST/OST-Datei
        params: Parameter für die Extraktion
        
    Returns:
        ExtractionResult: Ergebnis mit Pfad zur ZIP-Datei
        
    Raises:
        HTTPException: Bei Fehlern während der Extraktion
    """
    # Temporäres Verzeichnis für die Verarbeitung erstellen
    temp_dir = tempfile.mkdtemp()
    result_dir = os.path.join(temp_dir, "result")
    os.makedirs(result_dir, exist_ok=True)
    
    # Upload-Datei speichern
    file_path = os.path.join(temp_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        # XstPortableExport aufrufen
        export_option = "-e" if params.format == "native" else "-p"
        cmd = [
            "dotnet", 
            "/app/XstPortableExport.dll", 
            export_option,
            "-f=Calendar", 
            "-t=" + result_dir,
            file_path
        ]
        
        process = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True
        )
        
        if process.returncode != 0:
            raise HTTPException(
                status_code=500, 
                detail=f"Extraction failed: {process.stderr}"
            )
        
        # Ergebnisse als ZIP verpacken für den Download
        output_zip = os.path.join(temp_dir, "calendar_export.zip")
        shutil.make_archive(
            os.path.splitext(output_zip)[0],  # Basis-Dateiname ohne Erweiterung
            'zip',
            result_dir
        )
        
        return ExtractionResult(
            zip_path=output_zip,
            message="Calendar data successfully extracted"
        )
    
    except Exception as e:
        # Bei Fehler das temporäre Verzeichnis aufräumen
        cleanup_temp_dir(temp_dir)
        # Fehler weiterwerfen
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))