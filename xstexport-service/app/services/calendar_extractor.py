import os
import subprocess
import tempfile
import shutil
from typing import Optional, Dict, Any
from fastapi import UploadFile, HTTPException
from pydantic import BaseModel
import logging

from app.utils.file_utils import cleanup_temp_dir

logger = logging.getLogger(__name__)

class ExtractionResult(BaseModel):
    zip_path: str
    message: str

def find_dll(name: str) -> str:
    """
    Sucht nach einer DLL im Anwendungsverzeichnis.
    
    Args:
        name: Name der DLL
        
    Returns:
        Vollständiger Pfad zur DLL
    """
    for root, dirs, files in os.walk("/app"):
        for file in files:
            if file.lower() == name.lower():
                return os.path.join(root, file)
    
    return f"/app/{name}"  # Fallback zum Standardpfad

async def extract_calendar_data(
    file: UploadFile, 
    format: str = "csv",
    target_folder: Optional[str] = None
) -> ExtractionResult:
    """
    Extrahiert Kalenderdaten aus einer PST/OST-Datei.
    
    Args:
        file: Die hochgeladene PST/OST-Datei
        format: Format der Extraktion ('csv' oder 'native')
        target_folder: Optionaler Zielordner
        
    Returns:
        ExtractionResult: Ergebnis mit Pfad zur ZIP-Datei
        
    Raises:
        HTTPException: Bei Fehlern während der Extraktion
    """
    # Bestimmen des Quellverzeichnisses, falls target_folder nicht angegeben ist
    source_dir = "/data/ost"  # Standard-Verzeichnis im Container
    
    # Temporäres Verzeichnis für die Verarbeitung erstellen
    temp_dir = tempfile.mkdtemp()
    result_dir = os.path.join(temp_dir, "result")
    os.makedirs(result_dir, exist_ok=True)
    
    # Upload-Datei speichern
    source_filename = file.filename
    source_path = os.path.join(source_dir, source_filename)
    
    # Bestimmen des Ausgabe-Verzeichnisses
    output_dir = target_folder if target_folder else source_dir
    
    # PST/OST-Datei aus source_dir verwenden, falls verfügbar, sonst Upload-Datei verwenden
    file_path = ""
    if os.path.exists(source_path):
        logger.info(f"Verwende vorhandene Datei aus {source_path}")
        file_path = source_path
    else:
        logger.info(f"Datei nicht in {source_dir} gefunden, verwende Upload-Datei")
        file_path = os.path.join(temp_dir, source_filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    
    try:
        # Finde den korrekten Pfad zur DLL
        dll_path = find_dll("XstPortableExport.dll")
        logger.info(f"Gefundener Pfad zu XstPortableExport.dll: {dll_path}")
        
        # XstPortableExport aufrufen
        export_option = "-e" if format == "native" else "-p"
        cmd = [
            "dotnet", 
            dll_path, 
            export_option,
            "-f=Calendar", 
            "-t=" + result_dir,
            file_path
        ]
        
        logger.info(f"Führe Befehl aus: {' '.join(cmd)}")
        process = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True
        )
        
        if process.returncode != 0:
            error_msg = f"Extraction failed: {process.stderr}"
            logger.error(error_msg)
            raise HTTPException(
                status_code=500, 
                detail=error_msg
            )
        
        # Erstelle Basis-Dateiname für die ZIP-Datei (ohne Erweiterung)
        base_filename = os.path.splitext(source_filename)[0]
        
        # Ergebnisse als ZIP verpacken und in das Ausgangsverzeichnis schreiben
        output_zip_name = f"{base_filename}_calendar_export.zip"
        output_zip_path = os.path.join(output_dir, output_zip_name)
        
        # Stellen sicher, dass das Ausgabeverzeichnis existiert
        os.makedirs(output_dir, exist_ok=True)
        
        # Erstelle das ZIP-Archiv
        logger.info(f"Erstelle ZIP-Archiv unter {output_zip_path}")
        shutil.make_archive(
            os.path.splitext(output_zip_path)[0],  # Basis-Dateiname ohne Erweiterung
            'zip',
            result_dir
        )
        
        return ExtractionResult(
            zip_path=output_zip_path,
            message=f"Calendar data successfully extracted to {output_zip_path}"
        )
    
    except Exception as e:
        # Bei Fehler das temporäre Verzeichnis aufräumen
        cleanup_temp_dir(temp_dir)
        # Fehler protokollieren und weiterwerfen
        error_msg = f"Error during extraction: {str(e)}"
        logger.error(error_msg)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=error_msg)
    finally:
        # Temporäres Verzeichnis aufräumen, aber nur wenn wir nicht die Quelldatei verwenden
        if file_path != source_path:
            cleanup_temp_dir(temp_dir)