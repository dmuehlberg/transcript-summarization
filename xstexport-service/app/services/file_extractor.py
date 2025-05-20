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
        # Content-Type prüfen und ausgeben
        content_type = request.headers.get("content-type", "")
        logger.info(f"Request Content-Type: {content_type}")
        
        # JSON-Daten aus der Anfrage lesen mit verbesserter Fehlerbehandlung
        body_bytes = await request.body()
        logger.debug(f"Received request body (first 100 bytes): {body_bytes[:100]}")
        
        if not body_bytes:
            logger.error("Leerer Request-Body")
            raise HTTPException(
                status_code=400,
                detail="Der Request-Body ist leer"
            )
        
        # Versuche, den Request-Body zu parsen
        try:
            # Standard-Parsing mit UTF-8
            body_data = json.loads(body_bytes.decode('utf-8'))
        except UnicodeDecodeError as ude:
            logger.warning(f"UTF-8 Dekodierungsfehler: {str(ude)}, versuche mit errors=replace")
            # Versuche mit einer permissiveren Dekodierung, wenn UTF-8 fehlschlägt
            body_data = json.loads(body_bytes.decode('utf-8', errors='replace'))
        except json.JSONDecodeError as jde:
            logger.error(f"JSON-Dekodierungsfehler: {str(jde)}")
            
            # Prüfe, ob der Inhalt Form-Daten sein könnte statt JSON
            if content_type.startswith('multipart/form-data') or content_type.startswith('application/x-www-form-urlencoded'):
                raise HTTPException(
                    status_code=400,
                    detail="Es wurden Formulardaten gesendet, aber JSON wird erwartet. Stelle sicher, dass der Content-Type 'application/json' ist."
                )
            
            # Versuchen, den Body als String auszugeben, um zu sehen, was gesendet wurde
            body_str = body_bytes.decode('utf-8', errors='replace')
            sample = body_str[:100] + "..." if len(body_str) > 100 else body_str
            raise HTTPException(
                status_code=400,
                detail=f"Ungültiges JSON-Format: {str(jde)}. Empfangener Inhalt: {sample}"
            )
        
        logger.info(f"Received request data: {body_data}")
        
        # Prüfe auf erforderliche Felder
        filename = body_data.get("filename")
        if not filename:
            raise HTTPException(
                status_code=400,
                detail="Ein Dateiname muss angegeben werden"
            )
            
        format = body_data.get("format", "csv")
        target_folder = body_data.get("target_folder", None)
        return_file = body_data.get("return_file", False)
        
        # NEU: Ordnername aus der Anfrage lesen, mit Standardwert "Calendar"
        pst_folder = body_data.get("pst_folder", "Calendar")
        
        # Prüfen, ob die Datei existiert
        source_path = os.path.join("/data/ost", filename)
        if not os.path.exists(source_path):
            raise HTTPException(
                status_code=404,
                detail=f"Datei {filename} nicht im /data/ost-Verzeichnis gefunden"
            )
        
        # Mock-UploadFile mit dem Dateinamen erstellen
        mock_file = MockUploadFile(filename)
        
        logger.info(f"Extraktion mit Format {format} für Datei {filename} aus Ordner {pst_folder} gestartet")
        
        # Kalenderdaten extrahieren mit angepasstem Ordner
        result = await extract_calendar_data(
            mock_file,
            format,
            target_folder,
            pst_folder  # Übergebe den benutzerdefinierten Ordnernamen
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
    except json.JSONDecodeError as e:
        logger.error(f"Fehler beim Parsen der JSON-Anfrage: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Ungültiges JSON-Format in der Anfrage: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Fehler bei der Extraktion: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Fehler bei der Extraktion: {str(e)}"
        )