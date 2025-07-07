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
    target_folder: Optional[str] = None,
    pst_folder: str = "Calendar",  # Standardwert für Kompatibilität
    extract_all: bool = False  # Neue Option zum Extrahieren aller Elemente
) -> ExtractionResult:
    """
    Extrahiert Kalenderdaten oder alle Daten aus einer PST/OST-Datei.
    
    Args:
        file: Die hochgeladene PST/OST-Datei
        format: Format der Extraktion ('csv' oder 'native')
        target_folder: Optionaler Zielordner
        pst_folder: Name des Ordners in der PST-Datei (wird ignoriert, wenn extract_all=True)
        extract_all: Ob alle Elemente extrahiert werden sollen
        
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
    try:
        source_filename = file.filename
        if source_filename is None:
            source_filename = "upload.pst"  # Fallback-Name, falls kein Dateiname angegeben ist
        
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
                content = await file.read()
                logger.info(f"Datei gelesen, Länge: {len(content)} Bytes")
                buffer.write(content)
            
            # Datei-Berechtigungen setzen
            try:
                os.chmod(file_path, 0o644)
            except Exception as e:
                logger.warning(f"Konnte Berechtigungen für {file_path} nicht setzen: {e}")
        
        # Prüfen, ob die Datei existiert und Größe > 0
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            raise HTTPException(
                status_code=400,
                detail=f"Datei wurde nicht korrekt hochgeladen oder konnte nicht gespeichert werden: {file_path}"
            )
        
        logger.info(f"Datei gespeichert unter: {file_path}, Größe: {os.path.getsize(file_path)} Bytes")
        
        # Finde den korrekten Pfad zur DLL (erst XstExporter.Portable.dll versuchen, dann XstPortableExport.dll als Fallback)
        dll_path = find_dll("XstExporter.Portable.dll")
        if "XstExporter.Portable.dll" not in dll_path:
            # Fallback zur alten DLL-Benennung
            dll_path = find_dll("XstPortableExport.dll")
        
        logger.info(f"Gefundener Pfad zur DLL: {dll_path}")
        
        # Vor der Ausführung des Befehls, prüfe ob die Datei lesbar ist
        try:
            # Prüfe Dateiberechtigungen
            if not os.access(file_path, os.R_OK):
                logger.warning(f"Datei {file_path} ist möglicherweise nicht lesbar, versuche Berechtigungen zu korrigieren")
                os.chmod(file_path, 0o644)
        except Exception as e:
            logger.warning(f"Berechtigungsprüfung fehlgeschlagen: {str(e)}")
        
        # XstExporter.Portable aufrufen
        export_option = "-e" if format == "native" else "-p"
        
        # CMD erzeugen je nach extract_all Option
        cmd = ["dotnet", dll_path, export_option]
        
        if extract_all:
            # Wenn alle Elemente extrahiert werden sollen, verwenden wir keinen -f Parameter
            cmd.extend([
                "-t=" + result_dir,
                file_path
            ])
            extraction_type = "all items"
        else:
            # Wenn nur ein bestimmter Ordner extrahiert werden soll
            cmd.extend([
                f"-f={pst_folder}",
                "-t=" + result_dir,
                file_path
            ])
            extraction_type = pst_folder
        
        # Füge Umgebungsvariable für .NET-Debug-Ausgabe hinzu
        dotnet_env = os.environ.copy()
        dotnet_env["DOTNET_CLI_UI_LANGUAGE"] = "en"  # Erzwinge englische Fehlermeldungen
        dotnet_env["DOTNET_SYSTEM_GLOBALIZATION_INVARIANT"] = "true"  # Setze unveränderliche Globalisierung
        
        # Führe den dotnet-Befehl mit den Umgebungsvariablen aus
        logger.info(f"Führe Befehl aus: {' '.join(cmd)}")
        try:
            process = subprocess.run(
                cmd, 
                capture_output=True,
                text=False,  # Binärmodus
                env=dotnet_env,
                timeout=300  # Füge ein Timeout von 5 Minuten hinzu
            )
            
            # Protokolliere detaillierte Debug-Informationen
            logger.debug(f"Command exit code: {process.returncode}")
            logger.debug(f"Command stdout length: {len(process.stdout)}")
            logger.debug(f"Command stderr length: {len(process.stderr)}")
            
            if process.returncode != 0:
                # Sichere Dekodierung von stderr, problematische Zeichen ignorieren
                stderr_text = process.stderr.decode('utf-8', errors='replace')
                error_msg = f"Extraktion fehlgeschlagen: {stderr_text}"
                logger.error(error_msg)
                
                # Wenn der Fehler "Cannot find folder" ist und wir nicht extract_all verwenden,
                # versuchen wir es erneut mit extract_all=True
                if not extract_all and "Cannot find folder" in stderr_text:
                    logger.info(f"Ordner '{pst_folder}' nicht gefunden, versuche alle Elemente zu extrahieren")
                    return await extract_calendar_data(
                        file=file,
                        format=format,
                        target_folder=target_folder,
                        extract_all=True
                    )
                
                raise HTTPException(
                    status_code=500, 
                    detail=error_msg
                )
        except subprocess.TimeoutExpired:
            error_msg = "Extraktionsprozess nach 5 Minuten abgelaufen"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
        
        # Erstelle Basis-Dateiname für die ZIP-Datei (ohne Erweiterung)
        base_filename = os.path.splitext(source_filename)[0]
        
        # Ergebnisse als ZIP verpacken und in das Ausgangsverzeichnis schreiben
        if extract_all:
            output_zip_name = f"{base_filename}_all_export.zip"
        else:
            output_zip_name = f"{base_filename}_{pst_folder.lower()}_export.zip"
            
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
            message=f"{extraction_type} data successfully extracted to {output_zip_path}"
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
        if 'file_path' in locals() and file_path != source_path:
            cleanup_temp_dir(temp_dir)