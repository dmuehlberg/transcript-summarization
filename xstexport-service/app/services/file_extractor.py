import os
import json
import logging
from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from app.services.calendar_extractor import extract_calendar_data

logger = logging.getLogger(__name__)

class MockUploadFile:
    """
    Mock-Klasse für UploadFile, um bestehende Dateien zu verwenden, ohne sie hochzuladen.
    """
    def __init__(self, filename):
        self.filename = filename
        
    async def read(self):
        # Diese Methode wird nicht verwendet, da wir die vorhandene Datei direkt verwenden
        return b""

async def extract_calendar_from_existing_file(request: Request):
    """
    Extrahiert Kalenderdaten aus einer vorhandenen PST/OST-Datei im Container.
    
    Args:
        request: FastAPI Request-Objekt mit JSON-Daten
    
    Returns:
        Bei return_file=True: Die ZIP-Datei als Download
        Bei return_file=False: JSON-Antwort mit Pfad zur generierten ZIP-Datei
        
    Raises:
        HTTPException: Bei Fehlern während der Verarbeitung
    """
    try:
        # JSON-Daten aus der Anfrage lesen mit verbesserter Fehlerbehandlung
        body_bytes = await request.body()
        try:
            body_data = json.loads(body_bytes.decode('utf-8'))
        except UnicodeDecodeError:
            # Versuche mit einer permissiveren Dekodierung, wenn UTF-8 fehlschlägt
            body_data = json.loads(body_bytes.decode('utf-8', errors='replace'))
        
        logger.info(f"Received request data: {body_data}")
        
        filename = body_data.get("filename")
        if not filename:
            raise HTTPException(
                status_code=400,
                detail="Ein Dateiname muss angegeben werden"
            )
            
        format = body_data.get("format", "csv")
        target_folder = body_data.get("target_folder", None)
        return_file = body_data.get("return_file", False)
        
        # Prüfen, ob die Datei existiert
        source_path = os.path.join("/data/ost", filename)
        if not os.path.exists(source_path):
            raise HTTPException(
                status_code=404,
                detail=f"Datei {filename} nicht im /data/ost-Verzeichnis gefunden"
            )
        
        # Mock-UploadFile mit dem Dateinamen erstellen
        mock_file = MockUploadFile(filename)
        
        logger.info(f"Extraktion mit Format {format} für Datei {filename} gestartet")
        
        # Kalenderdaten extrahieren
        result = await extract_calendar_data(
            mock_file,
            format,
            target_folder
        )
        
        if return_file:
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
    except json.JSONDecodeError:
        logger.error("Fehler beim Parsen der JSON-Anfrage")
        raise HTTPException(
            status_code=400,
            detail="Ungültiges JSON-Format in der Anfrage"
        )
    except Exception as e:
        logger.error(f"Fehler bei der Extraktion: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Fehler bei der Extraktion: {str(e)}"
        )