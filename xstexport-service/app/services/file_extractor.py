import os
import json
import logging
import zipfile
import tempfile
import shutil
from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from app.services.calendar_extractor import extract_calendar_data

logger = logging.getLogger(__name__)

class MockUploadFile:
    """Mock-Klasse für UploadFile, die nur den Dateinamen benötigt."""
    def __init__(self, filename: str):
        self.filename = filename
        self.file = None
        
    async def read(self):
        return b""
        
    async def seek(self, offset: int):
        pass
        
    async def close(self):
        pass

async def extract_calendar_from_existing_file(
    file_path: str,
    format: str = "csv",
    extract_all: bool = False,
    return_file: bool = False
) -> dict:
    """
    Extrahiert Kalenderdaten aus einer vorhandenen PST/OST-Datei.
    
    Args:
        file_path: Pfad zur PST/OST-Datei
        format: Format der Extraktion ('csv' oder 'native')
        extract_all: Ob alle Elemente extrahiert werden sollen
        return_file: Ob die ZIP-Datei als Download zurückgegeben werden soll
        
    Returns:
        dict: Enthält den Pfad zur extrahierten Calendar.csv
    """
    try:
        logger.info(f"Starte Extraktion der PST/OST-Datei: {file_path}")
        
        # Temporäres Verzeichnis für die Extraktion erstellen
        temp_dir = tempfile.mkdtemp()
        logger.info(f"Temporäres Verzeichnis erstellt: {temp_dir}")
        
        # Mock-UploadFile mit dem Dateinamen erstellen
        mock_file = MockUploadFile(os.path.basename(file_path))
        
        # Kalenderdaten extrahieren
        logger.info(f"Extrahiere Kalenderdaten mit Format {format}")
        result = await extract_calendar_data(
            mock_file,
            format,
            None,  # target_folder
            "Calendar",  # pst_folder
            extract_all
        )
        
        if not result or not result.zip_path:
            logger.error("Keine ZIP-Datei wurde generiert")
            return None
            
        # ZIP-Datei entpacken
        output_dir = os.path.join(temp_dir, "extracted")
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Entpacke ZIP-Datei nach: {output_dir}")
        
        with zipfile.ZipFile(result.zip_path, 'r') as zip_ref:
            zip_ref.extractall(output_dir)
        
        # Calendar.csv suchen
        logger.info("Suche nach Calendar.csv")
        calendar_path = None
        for root, _, files in os.walk(output_dir):
            for file in files:
                if file.lower() == 'calendar.csv':
                    calendar_path = os.path.join(root, file)
                    logger.info(f"Calendar.csv gefunden: {calendar_path}")
                    break
            if calendar_path:
                break
        
        if calendar_path:
            logger.info(f"Calendar.csv gefunden: {calendar_path}")
            return {
                'calendar_path': calendar_path,
                'temp_dir': temp_dir  # Wichtig für spätere Bereinigung
            }
        else:
            logger.warning("Keine Calendar.csv in der extrahierten Datei gefunden")
            return None
            
    except Exception as e:
        logger.error(f"Fehler beim Extrahieren der PST/OST-Datei: {str(e)}")
        if 'temp_dir' in locals():
            shutil.rmtree(temp_dir)
            logger.info(f"Temporäres Verzeichnis bereinigt: {temp_dir}")
        raise

def extract_calendar_from_zip(zip_path: str) -> dict:
    """
    Extrahiert Kalenderdaten aus einer ZIP-Datei.
    
    Args:
        zip_path: Pfad zur ZIP-Datei
        
    Returns:
        dict: Enthält den Pfad zur extrahierten Calendar.csv
    """
    try:
        logger.info(f"Starte Extraktion der ZIP-Datei: {zip_path}")
        
        # Temporäres Verzeichnis für die Extraktion erstellen
        temp_dir = tempfile.mkdtemp()
        logger.info(f"Temporäres Verzeichnis erstellt: {temp_dir}")
        
        # ZIP-Datei extrahieren
        logger.info("Extrahiere ZIP-Datei")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Calendar.csv suchen
        logger.info("Suche nach Calendar.csv")
        calendar_path = None
        for root, _, files in os.walk(temp_dir):
            for file in files:
                if file.lower() == 'calendar.csv':
                    calendar_path = os.path.join(root, file)
                    logger.info(f"Calendar.csv gefunden: {calendar_path}")
                    break
            if calendar_path:
                break
        
        if calendar_path:
            logger.info(f"Calendar.csv gefunden: {calendar_path}")
            return {
                'calendar_path': calendar_path,
                'temp_dir': temp_dir  # Wichtig für spätere Bereinigung
            }
        else:
            logger.warning("Keine Calendar.csv in der ZIP-Datei gefunden")
            return None
            
    except Exception as e:
        logger.error(f"Fehler beim Extrahieren der ZIP-Datei: {str(e)}")
        if 'temp_dir' in locals():
            shutil.rmtree(temp_dir)
            logger.info(f"Temporäres Verzeichnis bereinigt: {temp_dir}")
        raise