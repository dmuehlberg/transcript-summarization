import os
import subprocess
import tempfile
import shutil
from typing import Optional, Dict, Any
from fastapi import UploadFile, HTTPException
from pydantic import BaseModel
import logging
import psutil
import hashlib

from app.utils.file_utils import cleanup_temp_dir

logger = logging.getLogger(__name__)

def validate_and_repair_ost_file(file_path: str) -> bool:
    """
    Versucht eine OST-Datei zu validieren und zu reparieren.
    
    Args:
        file_path: Pfad zur OST-Datei
        
    Returns:
        bool: True wenn die Datei gültig ist oder repariert werden konnte
    """
    try:
        # Prüfe Dateigröße
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            logger.error("OST-Datei ist leer")
            return False
        
        # Prüfe Datei-Header (OST-Dateien haben einen spezifischen Header)
        with open(file_path, 'rb') as f:
            header = f.read(8)
            
        # OST-Dateien beginnen normalerweise mit einem spezifischen Header
        # Hier prüfen wir auf gängige OST-Header-Signaturen
        if header.startswith(b'\x21\x42\x44\x4E'):  # !BDN
            logger.info("OST-Datei hat gültigen Header")
            return True
        elif header.startswith(b'\x4D\x53\x47'):  # MSG
            logger.info("OST-Datei hat MSG-Header")
            return True
        else:
            logger.warning(f"Unbekannter OST-Header: {header.hex()}")
            # Trotzdem versuchen, da einige OST-Dateien andere Header haben können
        
        # Prüfe auf Dateikorruption durch MD5-Checksumme
        logger.info("Berechne MD5-Checksumme für Dateivalidierung...")
        md5_hash = hashlib.md5()
        
        with open(file_path, 'rb') as f:
            # Lese in Chunks, um große Dateien zu handhaben
            chunk_size = 8192
            for chunk in iter(lambda: f.read(chunk_size), b""):
                md5_hash.update(chunk)
        
        checksum = md5_hash.hexdigest()
        logger.info(f"MD5-Checksumme: {checksum}")
        
        return True
        
    except Exception as e:
        logger.error(f"Fehler bei der Dateivalidierung: {str(e)}")
        return False

def create_file_backup(file_path: str) -> str:
    """
    Erstellt eine Sicherungskopie der Datei.
    
    Args:
        file_path: Pfad zur ursprünglichen Datei
        
    Returns:
        str: Pfad zur Sicherungskopie
    """
    try:
        backup_path = file_path + ".backup"
        shutil.copy2(file_path, backup_path)
        logger.info(f"Sicherungskopie erstellt: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Fehler beim Erstellen der Sicherungskopie: {str(e)}")
        return file_path

async def extract_with_file_validation(
    file_path: str,
    dll_path: str,
    result_dir: str,
    format: str = "csv",
    pst_folder: str = "Calendar"
) -> bool:
    """
    Versucht Extraktion mit Dateivalidierung und -reparatur.
    
    Args:
        file_path: Pfad zur PST/OST-Datei
        dll_path: Pfad zur .NET DLL
        result_dir: Zielverzeichnis für die Extraktion
        format: Export-Format ('csv' oder 'native')
        pst_folder: Name des zu extrahierenden Ordners
        
    Returns:
        bool: True wenn erfolgreich, False wenn fehlgeschlagen
    """
    logger.info(f"Starte Extraktion mit Dateivalidierung: {file_path}")
    
    # Validiere die Datei
    if not validate_and_repair_ost_file(file_path):
        logger.warning("Dateivalidierung fehlgeschlagen, versuche trotzdem Extraktion")
    
    # Erstelle Sicherungskopie
    backup_path = create_file_backup(file_path)
    
    # Versuche verschiedene Ansätze
    approaches = [
        {
            "name": "Minimale Extraktion mit Dateivalidierung",
            "env": {
                "DOTNET_SYSTEM_GLOBALIZATION_INVARIANT": "1",
                "DOTNET_CLI_UI_LANGUAGE": "en",
                "DOTNET_GCHeapHardLimit": "0x1000000",  # 256MB
                "DOTNET_GCAllowVeryLargeObjects": "0",
                "DOTNET_GCHeapHardLimitPercent": "15"
            },
            "cmd": ["dotnet", dll_path, "-p", f"-f={pst_folder}", "-t=" + result_dir, file_path]
        },
        {
            "name": "Extraktion ohne Ordner-Spezifikation",
            "env": {
                "DOTNET_SYSTEM_GLOBALIZATION_INVARIANT": "1",
                "DOTNET_CLI_UI_LANGUAGE": "en",
                "DOTNET_GCHeapHardLimit": "0x800000",  # 128MB
                "DOTNET_GCAllowVeryLargeObjects": "0",
                "DOTNET_GCHeapHardLimitPercent": "10"
            },
            "cmd": ["dotnet", dll_path, "-p", "-t=" + result_dir, file_path]
        },
        {
            "name": "Native Extraktion",
            "env": {
                "DOTNET_SYSTEM_GLOBALIZATION_INVARIANT": "1",
                "DOTNET_CLI_UI_LANGUAGE": "en",
                "DOTNET_GCHeapHardLimit": "0x1000000",  # 256MB
                "DOTNET_GCAllowVeryLargeObjects": "0",
                "DOTNET_GCHeapHardLimitPercent": "15"
            },
            "cmd": ["dotnet", dll_path, "-e", f"-f={pst_folder}", "-t=" + result_dir, file_path]
        }
    ]
    
    for approach in approaches:
        logger.info(f"Versuche Ansatz: {approach['name']}")
        
        # Umgebungsvariablen setzen
        dotnet_env = os.environ.copy()
        dotnet_env.update(approach["env"])
        
        try:
            process = subprocess.run(
                approach["cmd"],
                capture_output=True,
                text=False,
                env=dotnet_env,
                timeout=3600  # 1 Stunde
            )
            
            if process.returncode == 0:
                logger.info(f"Ansatz '{approach['name']}' erfolgreich")
                return True
            else:
                stderr_text = process.stderr.decode('utf-8', errors='replace')
                logger.warning(f"Ansatz '{approach['name']}' fehlgeschlagen: {stderr_text}")
                
                # Wenn es ein Array-Index-Fehler ist, versuche mit Backup-Datei
                if "Index was outside the bounds of the array" in stderr_text:
                    logger.info("Array-Index-Fehler erkannt, versuche mit Backup-Datei")
                    
                    if backup_path != file_path:
                        backup_env = dotnet_env.copy()
                        backup_env["DOTNET_GCHeapHardLimit"] = "0x800000"  # Reduziere Heap-Limit auf 128MB
                        backup_env["DOTNET_GCHeapHardLimitPercent"] = "10"
                        
                        backup_cmd = approach["cmd"].copy()
                        backup_cmd[-1] = backup_path  # Ersetze Dateipfad mit Backup
                        
                        process_backup = subprocess.run(
                            backup_cmd,
                            capture_output=True,
                            text=False,
                            env=backup_env,
                            timeout=3600
                        )
                        
                        if process_backup.returncode == 0:
                            logger.info(f"Backup-Extraktion mit '{approach['name']}' erfolgreich")
                            return True
                        else:
                            stderr_backup = process_backup.stderr.decode('utf-8', errors='replace')
                            logger.warning(f"Backup-Extraktion fehlgeschlagen: {stderr_backup}")
                
                continue
                
        except subprocess.TimeoutExpired:
            logger.warning(f"Ansatz '{approach['name']}' nach 1 Stunde abgelaufen")
            continue
        except Exception as e:
            logger.warning(f"Fehler bei Ansatz '{approach['name']}': {str(e)}")
            continue
    
    logger.error("Alle Ansätze mit Dateivalidierung fehlgeschlagen")
    return False

def check_system_resources():
    """
    Überprüft die verfügbaren Systemressourcen und gibt Warnungen aus.
    """
    try:
        # Verfügbarer Speicher
        memory = psutil.virtual_memory()
        available_gb = memory.available / (1024**3)
        total_gb = memory.total / (1024**3)
        
        logger.info(f"Verfügbarer Speicher: {available_gb:.2f} GB von {total_gb:.2f} GB")
        
        if available_gb < 1.0:
            logger.warning(f"Wenig verfügbarer Speicher: {available_gb:.2f} GB")
            return False
        
        # Verfügbarer Speicherplatz
        disk = psutil.disk_usage('/')
        available_disk_gb = disk.free / (1024**3)
        
        logger.info(f"Verfügbarer Speicherplatz: {available_disk_gb:.2f} GB")
        
        if available_disk_gb < 5.0:
            logger.warning(f"Wenig verfügbarer Speicherplatz: {available_disk_gb:.2f} GB")
            return False
        
        return True
        
    except Exception as e:
        logger.warning(f"Konnte Systemressourcen nicht überprüfen: {str(e)}")
        return True  # Im Zweifelsfall fortfahren

def check_available_dotnet_runtimes():
    """
    Überprüft die verfügbaren .NET-Runtimes und gibt sie aus.
    """
    try:
        # Prüfe verfügbare Runtimes
        process = subprocess.run(
            ["dotnet", "--list-runtimes"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if process.returncode == 0:
            runtimes = process.stdout.strip()
            logger.info(f"Verfügbare .NET-Runtimes:\n{runtimes}")
            
            # Extrahiere auch die spezifischen Versionen
            available_versions = get_available_dotnet_runtimes()
            logger.info(f"Verfügbare .NET-Versionen: {available_versions}")
            
            return runtimes
        else:
            logger.warning("Konnte .NET-Runtimes nicht auflisten")
            return None
            
    except Exception as e:
        logger.warning(f"Fehler beim Überprüfen der .NET-Runtimes: {str(e)}")
        return None

def get_available_dotnet_runtimes():
    """
    Ermittelt die verfügbaren .NET-Runtimes dynamisch.
    
    Returns:
        list: Liste der verfügbaren Runtime-Versionen
    """
    try:
        process = subprocess.run(
            ["dotnet", "--list-runtimes"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if process.returncode == 0:
            runtimes = []
            for line in process.stdout.strip().split('\n'):
                if 'Microsoft.NETCore.App' in line:
                    # Extrahiere Version aus Zeile wie "Microsoft.NETCore.App 6.0.25 [/root/.dotnet/shared/Microsoft.NETCore.App]"
                    parts = line.split()
                    if len(parts) >= 2:
                        version = parts[1]
                        runtimes.append(version)
            
            logger.info(f"Verfügbare .NET-Runtimes: {runtimes}")
            return runtimes
        else:
            logger.warning("Konnte .NET-Runtimes nicht auflisten")
            return []
            
    except Exception as e:
        logger.warning(f"Fehler beim Ermitteln der .NET-Runtimes: {str(e)}")
        return []

async def extract_with_dynamic_runtime_selection(
    file_path: str,
    dll_path: str,
    result_dir: str,
    format: str = "csv",
    pst_folder: str = "Calendar"
) -> bool:
    """
    Versucht Extraktion mit verschiedenen .NET-Konfigurationen.
    
    Args:
        file_path: Pfad zur PST/OST-Datei
        dll_path: Pfad zur .NET DLL
        result_dir: Zielverzeichnis für die Extraktion
        format: Export-Format ('csv' oder 'native')
        pst_folder: Name des zu extrahierenden Ordners
        
    Returns:
        bool: True wenn erfolgreich, False wenn fehlgeschlagen
    """
    logger.info(f"Versuche Extraktion mit verschiedenen .NET-Konfigurationen: {file_path}")
    
    # Export-Option
    export_option = "-e" if format == "native" else "-p"
    
    # Verschiedene Konfigurationen testen
    configurations = [
        {
            "name": "Standard-Konfiguration",
            "env": {
                "DOTNET_SYSTEM_GLOBALIZATION_INVARIANT": "1",
                "DOTNET_CLI_UI_LANGUAGE": "en"
            }
        },
        {
            "name": "Konservative Konfiguration",
            "env": {
                "DOTNET_SYSTEM_GLOBALIZATION_INVARIANT": "1",
                "DOTNET_CLI_UI_LANGUAGE": "en",
                "DOTNET_GCHeapHardLimit": "0x800000",  # 128MB
                "DOTNET_GCAllowVeryLargeObjects": "0",
                "DOTNET_GCHeapHardLimitPercent": "20"
            }
        },
        {
            "name": "Minimale Konfiguration",
            "env": {
                "DOTNET_SYSTEM_GLOBALIZATION_INVARIANT": "1",
                "DOTNET_CLI_UI_LANGUAGE": "en",
                "DOTNET_GCHeapHardLimit": "0x400000",  # 64MB
                "DOTNET_GCAllowVeryLargeObjects": "0",
                "DOTNET_GCHeapHardLimitPercent": "10"
            }
        },
        {
            "name": "Erweiterte Konfiguration",
            "env": {
                "DOTNET_SYSTEM_GLOBALIZATION_INVARIANT": "1",
                "DOTNET_CLI_UI_LANGUAGE": "en",
                "DOTNET_GCHeapHardLimit": "0x1000000",  # 256MB
                "DOTNET_GCAllowVeryLargeObjects": "1",
                "DOTNET_GCHeapHardLimitPercent": "30"
            }
        }
    ]
    
    # Verschiedene Ordner-Namen testen
    folder_names = [pst_folder, "Kalender", "Calendar", "Inbox", "Posteingang"]
    
    for config in configurations:
        for folder in folder_names:
            logger.info(f"Versuche Konfiguration '{config['name']}' mit Ordner '{folder}'")
            
            # Umgebungsvariablen setzen
            dotnet_env = os.environ.copy()
            dotnet_env.update(config["env"])
            
            # Befehl erstellen
            cmd = ["dotnet", dll_path, export_option, f"-f={folder}", "-t=" + result_dir, file_path]
            
            try:
                process = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=False,
                    env=dotnet_env,
                    timeout=1800  # 30 Minuten
                )
                
                if process.returncode == 0:
                    logger.info(f"Konfiguration '{config['name']}' mit Ordner '{folder}' erfolgreich")
                    return True
                else:
                    stderr_text = process.stderr.decode('utf-8', errors='replace')
                    stdout_text = process.stdout.decode('utf-8', errors='replace')
                    
                    # Prüfe auf spezifische Fehler
                    if "Cannot find folder" in stderr_text:
                        logger.info(f"Ordner '{folder}' nicht gefunden, versuche nächsten")
                        continue
                    elif "Index was outside the bounds of the array" in stderr_text:
                        logger.warning(f"Array-Index-Fehler mit Konfiguration '{config['name']}', versuche nächste")
                        continue
                    elif "Failed to create CoreCLR" in stderr_text:
                        logger.warning(f"CoreCLR-Fehler mit Konfiguration '{config['name']}', versuche nächste")
                        continue
                    else:
                        logger.warning(f"Konfiguration '{config['name']}' mit Ordner '{folder}' fehlgeschlagen: {stderr_text}")
                        
            except subprocess.TimeoutExpired:
                logger.warning(f"Timeout mit Konfiguration '{config['name']}' und Ordner '{folder}'")
                continue
            except Exception as e:
                logger.warning(f"Fehler mit Konfiguration '{config['name']}' und Ordner '{folder}': {str(e)}")
                continue
    
    # Wenn alle Konfigurationen fehlgeschlagen sind, versuche ohne Ordner-Spezifikation
    logger.info("Alle Konfigurationen fehlgeschlagen, versuche Extraktion ohne Ordner-Spezifikation")
    
    for config in configurations:
        logger.info(f"Versuche Konfiguration '{config['name']}' ohne Ordner-Spezifikation")
        
        # Umgebungsvariablen setzen
        dotnet_env = os.environ.copy()
        dotnet_env.update(config["env"])
        
        # Befehl ohne Ordner-Spezifikation
        cmd = ["dotnet", dll_path, export_option, "-t=" + result_dir, file_path]
        
        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=False,
                env=dotnet_env,
                timeout=1800  # 30 Minuten
            )
            
            if process.returncode == 0:
                logger.info(f"Konfiguration '{config['name']}' ohne Ordner-Spezifikation erfolgreich")
                return True
            else:
                stderr_text = process.stderr.decode('utf-8', errors='replace')
                logger.warning(f"Konfiguration '{config['name']}' ohne Ordner-Spezifikation fehlgeschlagen: {stderr_text}")
                
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout mit Konfiguration '{config['name']}' ohne Ordner-Spezifikation")
            continue
        except Exception as e:
            logger.warning(f"Fehler mit Konfiguration '{config['name']}' ohne Ordner-Spezifikation: {str(e)}")
            continue
    
    logger.error("Alle dynamischen Runtime-Strategien fehlgeschlagen")
    return False

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
    extract_all: bool = False,  # Neue Option zum Extrahieren aller Elemente
    retry_count: int = 0  # Zähler für Rekursionsvermeidung
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
    # Verhindere Endlosschleife
    if retry_count > 5:
        raise HTTPException(
            status_code=500,
            detail="Maximale Anzahl von Wiederholungsversuchen erreicht. Die Datei ist möglicherweise zu groß oder beschädigt."
        )
    
    # Überprüfe Systemressourcen
    if not check_system_resources():
        logger.warning("Systemressourcen sind knapp, aber versuche Extraktion trotzdem")
    
    # Überprüfe verfügbare .NET-Runtimes
    check_available_dotnet_runtimes()
    
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
        
        # Für Speicherprobleme immer mit spezifischem Ordner extrahieren
        # extract_all wird ignoriert, um Speicherverbrauch zu reduzieren
        cmd.extend([
            f"-f={pst_folder}",
            "-t=" + result_dir,
            file_path
        ])
        extraction_type = pst_folder
        logger.info(f"Extrahiere spezifischen Ordner: {pst_folder} (extract_all wird ignoriert)")
        
        # Füge Umgebungsvariable für .NET-Debug-Ausgabe hinzu
        dotnet_env = os.environ.copy()
        dotnet_env["DOTNET_CLI_UI_LANGUAGE"] = "en"  # Erzwinge englische Fehlermeldungen
        dotnet_env["DOTNET_SYSTEM_GLOBALIZATION_INVARIANT"] = "1"  # Setze unveränderliche Globalisierung
        
        # Führe den dotnet-Befehl mit den Umgebungsvariablen aus
        logger.info(f"Führe Befehl aus: {' '.join(cmd)}")
        
        # Prüfe Dateigröße für spezielle Behandlung großer Dateien
        file_size_gb = os.path.getsize(file_path) / (1024**3)
        logger.info(f"Dateigröße: {file_size_gb:.2f} GB")
        
        # Für sehr große Dateien (>2GB) verwende längere Timeouts und spezielle Umgebungsvariablen
        if file_size_gb > 2.0:
            logger.info("Große Datei erkannt (>2GB), verwende erweiterte Konfiguration")
            # Erhöhe Timeout für große Dateien
            timeout_seconds = 1800  # 30 Minuten
            # Füge spezielle .NET-Umgebungsvariablen für große Dateien hinzu
            dotnet_env["DOTNET_GCHeapHardLimit"] = "0x8000000"  # 2GB Heap-Limit
            dotnet_env["DOTNET_GCAllowVeryLargeObjects"] = "1"
            dotnet_env["DOTNET_GCHeapHardLimitPercent"] = "80"
        elif file_size_gb > 1.0:
            logger.info("Mittlere Datei erkannt (1-2GB), verwende konservative Konfiguration")
            timeout_seconds = 900  # 15 Minuten
            # Konservative Speicherlimits für mittlere Dateien
            dotnet_env["DOTNET_GCHeapHardLimit"] = "0x2000000"  # 512MB Heap-Limit
            dotnet_env["DOTNET_GCAllowVeryLargeObjects"] = "0"
            dotnet_env["DOTNET_GCHeapHardLimitPercent"] = "25"
        else:
            logger.info("Kleine Datei erkannt (<1GB), verwende Standard-Konfiguration")
            timeout_seconds = 300  # 5 Minuten für normale Dateien
            # Konservative Speicherlimits für kleine Dateien
            dotnet_env["DOTNET_GCHeapHardLimit"] = "0x1000000"  # 256MB Heap-Limit
            dotnet_env["DOTNET_GCAllowVeryLargeObjects"] = "0"
            dotnet_env["DOTNET_GCHeapHardLimitPercent"] = "15"
        
        try:
            process = subprocess.run(
                cmd, 
                capture_output=True,
                text=False,  # Binärmodus
                env=dotnet_env,
                timeout=timeout_seconds
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
                
                # Spezielle Behandlung für Array-Index-Fehler bei großen Dateien
                if "Index was outside the bounds of the array" in stderr_text:
                    logger.warning("Array-Index-Fehler erkannt, versuche alternative Strategie")
                    
                    # Verhindere Endlosschleife durch Rekursionszähler
                    if retry_count >= 3:
                        logger.error("Maximale Anzahl von Wiederholungsversuchen erreicht, versuche alternative Lösung")
                        
                        # Verwende die neue Dateivalidierung und -reparatur
                        success = await extract_with_file_validation(
                            file_path=file_path,
                            dll_path=dll_path,
                            result_dir=result_dir,
                            format=format,
                            pst_folder=pst_folder
                        )
                        
                        if success:
                            logger.info("Extraktion mit Dateivalidierung erfolgreich")
                            # Weiter mit der normalen Verarbeitung
                        else:
                            # Als letzte Option versuche die dynamische Runtime-Auswahl
                            logger.info("Dateivalidierung fehlgeschlagen, versuche dynamische Runtime-Auswahl")
                            success = await extract_with_dynamic_runtime_selection(
                                file_path=file_path,
                                dll_path=dll_path,
                                result_dir=result_dir,
                                format=format,
                                pst_folder=pst_folder
                            )
                            
                            if success:
                                logger.info("Dynamische Runtime-Auswahl erfolgreich")
                                # Weiter mit der normalen Verarbeitung
                            else:
                                error_msg = f"Datei zu groß für die Verarbeitung. Alle Versuche fehlgeschlagen. Letzter Fehler: {stderr_text}"
                                logger.error(error_msg)
                                raise HTTPException(status_code=500, detail=error_msg)
                    
                    # Strategie 1: Versuche mit spezifischem Ordner statt extract_all
                    if extract_all:
                        logger.info("Versuche Extraktion mit spezifischem Ordner 'Calendar'")
                        return await extract_calendar_data(
                            file=file,
                            format=format,
                            target_folder=target_folder,
                            pst_folder="Calendar",
                            extract_all=False,
                            retry_count=retry_count + 1
                        )
                    else:
                        # Strategie 2: Versuche mit anderen Ordnernamen
                        alternative_folders = ["Kalender", "Inbox", "Posteingang"]
                        for alt_folder in alternative_folders:
                            logger.info(f"Versuche Extraktion mit alternativem Ordner '{alt_folder}'")
                            try:
                                return await extract_calendar_data(
                                    file=file,
                                    format=format,
                                    target_folder=target_folder,
                                    pst_folder=alt_folder,
                                    extract_all=False,
                                    retry_count=retry_count + 1
                                )
                            except HTTPException as e:
                                if "Index was outside the bounds of the array" in str(e.detail):
                                    logger.warning(f"Array-Index-Fehler auch mit Ordner '{alt_folder}'")
                                    continue
                                else:
                                    # Anderer Fehler, weiterwerfen
                                    raise e
                        
                        # Strategie 3: Versuche mit reduzierter Speichernutzung
                        logger.info("Versuche Extraktion mit reduzierter Speichernutzung")
                        dotnet_env["DOTNET_GCHeapHardLimit"] = "0x2000000"  # 512MB Heap-Limit
                        dotnet_env["DOTNET_GCAllowVeryLargeObjects"] = "0"
                        dotnet_env["DOTNET_GCHeapHardLimitPercent"] = "20"
                        
                        # Erneut versuchen mit extract_all=False
                        cmd_reduced = ["dotnet", dll_path, export_option, f"-f=Calendar", "-t=" + result_dir, file_path]
                        logger.info(f"Führe reduzierten Befehl aus: {' '.join(cmd_reduced)}")
                        
                        process_reduced = subprocess.run(
                            cmd_reduced,
                            capture_output=True,
                            text=False,
                            env=dotnet_env,
                            timeout=timeout_seconds
                        )
                        
                        if process_reduced.returncode == 0:
                            logger.info("Reduzierte Extraktion erfolgreich")
                            # Weiter mit der normalen Verarbeitung
                        else:
                            stderr_reduced = process_reduced.stderr.decode('utf-8', errors='replace')
                            logger.error(f"Reduzierte Extraktion fehlgeschlagen: {stderr_reduced}")
                            
                            # Wenn alle Strategien fehlgeschlagen sind, verwende die neue Dateivalidierung
                            logger.info("Alle Standard-Strategien fehlgeschlagen, versuche Dateivalidierung")
                            success = await extract_with_file_validation(
                                file_path=file_path,
                                dll_path=dll_path,
                                result_dir=result_dir,
                                format=format,
                                pst_folder="Calendar"
                            )
                            
                            if success:
                                logger.info("Dateivalidierung erfolgreich")
                                # Weiter mit der normalen Verarbeitung
                            else:
                                # Als letzte Option versuche die dynamische Runtime-Auswahl
                                logger.info("Dateivalidierung fehlgeschlagen, versuche dynamische Runtime-Auswahl")
                                success = await extract_with_dynamic_runtime_selection(
                                    file_path=file_path,
                                    dll_path=dll_path,
                                    result_dir=result_dir,
                                    format=format,
                                    pst_folder="Calendar"
                                )
                                
                                if success:
                                    logger.info("Dynamische Runtime-Auswahl erfolgreich")
                                    # Weiter mit der normalen Verarbeitung
                                else:
                                    error_msg = f"Datei zu groß für die Verarbeitung. Alle Versuche fehlgeschlagen. Letzter Fehler: {stderr_reduced}"
                                    logger.error(error_msg)
                                    raise HTTPException(status_code=500, detail=error_msg)

                
                # Wenn der Fehler "Cannot find folder" ist und wir nicht extract_all verwenden,
                # versuchen wir es erneut mit extract_all=True
                elif not extract_all and "Cannot find folder" in stderr_text:
                    logger.info(f"Ordner '{pst_folder}' nicht gefunden, versuche alle Elemente zu extrahieren")
                    return await extract_calendar_data(
                        file=file,
                        format=format,
                        target_folder=target_folder,
                        extract_all=True,
                        retry_count=retry_count + 1
                    )
                else:
                    raise HTTPException(
                        status_code=500, 
                        detail=error_msg
                    )
        except subprocess.TimeoutExpired:
            error_msg = f"Extraktionsprozess nach {timeout_seconds} Sekunden abgelaufen"
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

def cleanup_temp_dir(temp_dir: str):
    """Bereinigt ein temporäres Verzeichnis."""
    try:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logger.debug(f"Temporäres Verzeichnis bereinigt: {temp_dir}")
    except Exception as e:
        logger.warning(f"Fehler beim Bereinigen des temporären Verzeichnisses {temp_dir}: {e}")

async def extract_large_file_with_chunking(
    file_path: str,
    dll_path: str,
    result_dir: str,
    format: str = "csv",
    pst_folder: str = "Calendar"
) -> bool:
    """
    Spezielle Funktion für die Extraktion sehr großer PST/OST-Dateien.
    Verwendet optimierte .NET-Umgebungsvariablen und längere Timeouts.
    
    Args:
        file_path: Pfad zur PST/OST-Datei
        dll_path: Pfad zur .NET DLL
        result_dir: Zielverzeichnis für die Extraktion
        format: Export-Format ('csv' oder 'native')
        pst_folder: Name des zu extrahierenden Ordners
        
    Returns:
        bool: True wenn erfolgreich, False wenn fehlgeschlagen
    """
    logger.info(f"Starte optimierte Extraktion für große Datei: {file_path}")
    
    # Optimierte .NET-Umgebungsvariablen für große Dateien
    dotnet_env = os.environ.copy()
    dotnet_env["DOTNET_CLI_UI_LANGUAGE"] = "en"
    dotnet_env["DOTNET_SYSTEM_GLOBALIZATION_INVARIANT"] = "1"  # Setze unveränderliche Globalisierung
    
    # Spezielle Konfiguration für große Dateien
    dotnet_env["DOTNET_GCHeapHardLimit"] = "0x8000000"  # 2GB Heap-Limit
    dotnet_env["DOTNET_GCAllowVeryLargeObjects"] = "1"
    dotnet_env["DOTNET_GCHeapHardLimitPercent"] = "80"
    dotnet_env["DOTNET_GCHeapHardLimitSOH"] = "0x4000000"  # 1GB für Small Object Heap
    dotnet_env["DOTNET_GCHeapHardLimitLOH"] = "0x4000000"  # 1GB für Large Object Heap
    
    # Erhöhte Timeouts für große Dateien
    timeout_seconds = 3600  # 1 Stunde
    
    # Export-Option
    export_option = "-e" if format == "native" else "-p"
    
    # Befehl mit spezifischem Ordner (weniger Speicherverbrauch als extract_all)
    cmd = [
        "dotnet", 
        dll_path, 
        export_option,
        f"-f={pst_folder}",
        "-t=" + result_dir,
        file_path
    ]
    
    logger.info(f"Führe optimierten Befehl aus: {' '.join(cmd)}")
    
    try:
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=False,
            env=dotnet_env,
            timeout=timeout_seconds
        )
        
        if process.returncode == 0:
            logger.info("Optimierte Extraktion erfolgreich")
            return True
        else:
            stderr_text = process.stderr.decode('utf-8', errors='replace')
            logger.error(f"Optimierte Extraktion fehlgeschlagen: {stderr_text}")
            
            # Wenn es ein CoreCLR-Fehler ist, versuche alternative Strategien
            if "Failed to create CoreCLR" in stderr_text:
                logger.info("CoreCLR-Fehler erkannt, versuche alternative .NET-Konfiguration")
                
                # Versuche mit expliziter Runtime-Konfiguration
                runtime_config_path = os.path.join(os.path.dirname(dll_path), "runtimeconfig.json")
                if os.path.exists(runtime_config_path):
                    logger.info(f"Runtime-Konfiguration gefunden: {runtime_config_path}")
                    
                    # Alternative Umgebungsvariablen für CoreCLR-Probleme
                    dotnet_env_alt = os.environ.copy()
                    dotnet_env_alt["DOTNET_SYSTEM_GLOBALIZATION_INVARIANT"] = "1"
                    dotnet_env_alt["DOTNET_CLI_UI_LANGUAGE"] = "en"
                    dotnet_env_alt["DOTNET_GCHeapHardLimit"] = "0x4000000"  # 1GB Heap-Limit
                    dotnet_env_alt["DOTNET_GCAllowVeryLargeObjects"] = "0"
                    dotnet_env_alt["DOTNET_GCHeapHardLimitPercent"] = "60"
                    
                    # Versuche mit expliziter Runtime-Konfiguration
                    cmd_runtime = [
                        "dotnet", 
                        "--runtime-config", runtime_config_path,
                        dll_path, 
                        export_option,
                        f"-f={pst_folder}",
                        "-t=" + result_dir,
                        file_path
                    ]
                    
                    logger.info(f"Führe Runtime-Konfigurationsbefehl aus: {' '.join(cmd_runtime)}")
                    
                    process_runtime = subprocess.run(
                        cmd_runtime,
                        capture_output=True,
                        text=False,
                        env=dotnet_env_alt,
                        timeout=timeout_seconds
                    )
                    
                    if process_runtime.returncode == 0:
                        logger.info("Runtime-Konfigurations-Extraktion erfolgreich")
                        return True
                    else:
                        stderr_runtime = process_runtime.stderr.decode('utf-8', errors='replace')
                        logger.error(f"Runtime-Konfigurations-Extraktion fehlgeschlagen: {stderr_runtime}")
            
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"Optimierte Extraktion nach {timeout_seconds} Sekunden abgelaufen")
        return False
    except Exception as e:
        logger.error(f"Unerwarteter Fehler bei optimierter Extraktion: {str(e)}")
        return False

async def extract_very_large_file(
    file_path: str,
    dll_path: str,
    result_dir: str,
    format: str = "csv"
) -> bool:
    """
    Spezielle Funktion für die Extraktion sehr großer PST/OST-Dateien (>3GB).
    Verwendet minimale .NET-Konfiguration und versucht verschiedene Strategien.
    
    Args:
        file_path: Pfad zur PST/OST-Datei
        dll_path: Pfad zur .NET DLL
        result_dir: Zielverzeichnis für die Extraktion
        format: Export-Format ('csv' oder 'native')
        
    Returns:
        bool: True wenn erfolgreich, False wenn fehlgeschlagen
    """
    logger.info(f"Starte Extraktion für sehr große Datei: {file_path}")
    
    # Minimale .NET-Umgebungsvariablen für sehr große Dateien
    dotnet_env = os.environ.copy()
    dotnet_env["DOTNET_SYSTEM_GLOBALIZATION_INVARIANT"] = "1"
    dotnet_env["DOTNET_CLI_UI_LANGUAGE"] = "en"
    
    # Sehr konservative Speicherkonfiguration
    dotnet_env["DOTNET_GCHeapHardLimit"] = "0x2000000"  # 512MB Heap-Limit
    dotnet_env["DOTNET_GCAllowVeryLargeObjects"] = "0"
    dotnet_env["DOTNET_GCHeapHardLimitPercent"] = "40"
    dotnet_env["DOTNET_GCHeapHardLimitSOH"] = "0x1000000"  # 256MB für Small Object Heap
    dotnet_env["DOTNET_GCHeapHardLimitLOH"] = "0x1000000"  # 256MB für Large Object Heap
    
    # Erhöhte Timeouts für sehr große Dateien
    timeout_seconds = 7200  # 2 Stunden
    
    # Export-Option
    export_option = "-e" if format == "native" else "-p"
    
    # Versuche verschiedene Strategien
    strategies = [
        # Strategie 1: Nur Calendar-Ordner mit minimaler Konfiguration
        {
            "name": "Calendar-Ordner mit minimaler Konfiguration",
            "cmd": ["dotnet", dll_path, export_option, "-f=Calendar", "-t=" + result_dir, file_path]
        },
        # Strategie 2: Nur Inbox-Ordner
        {
            "name": "Inbox-Ordner",
            "cmd": ["dotnet", dll_path, export_option, "-f=Inbox", "-t=" + result_dir, file_path]
        },
        # Strategie 3: Alle Elemente mit minimaler Konfiguration
        {
            "name": "Alle Elemente mit minimaler Konfiguration",
            "cmd": ["dotnet", dll_path, export_option, "-t=" + result_dir, file_path]
        }
    ]
    
    for strategy in strategies:
        logger.info(f"Versuche Strategie: {strategy['name']}")
        
        try:
            process = subprocess.run(
                strategy['cmd'],
                capture_output=True,
                text=False,
                env=dotnet_env,
                timeout=timeout_seconds
            )
            
            if process.returncode == 0:
                logger.info(f"Strategie '{strategy['name']}' erfolgreich")
                return True
            else:
                stderr_text = process.stderr.decode('utf-8', errors='replace')
                logger.warning(f"Strategie '{strategy['name']}' fehlgeschlagen: {stderr_text}")
                
                # Wenn es ein CoreCLR-Fehler ist, versuche mit Runtime-Konfiguration
                if "Failed to create CoreCLR" in stderr_text:
                    runtime_config_path = os.path.join(os.path.dirname(dll_path), "runtimeconfig.json")
                    if os.path.exists(runtime_config_path):
                        logger.info("Versuche mit expliziter Runtime-Konfiguration")
                        
                        cmd_runtime = [
                            "dotnet",
                            "--runtime-config", runtime_config_path
                        ] + strategy['cmd'][1:]  # Entferne 'dotnet' und füge Runtime-Konfiguration hinzu
                        
                        process_runtime = subprocess.run(
                            cmd_runtime,
                            capture_output=True,
                            text=False,
                            env=dotnet_env,
                            timeout=timeout_seconds
                        )
                        
                        if process_runtime.returncode == 0:
                            logger.info(f"Runtime-Konfigurations-Strategie '{strategy['name']}' erfolgreich")
                            return True
                        else:
                            stderr_runtime = process_runtime.stderr.decode('utf-8', errors='replace')
                            logger.warning(f"Runtime-Konfigurations-Strategie '{strategy['name']}' fehlgeschlagen: {stderr_runtime}")
                
                continue
                
        except subprocess.TimeoutExpired:
            logger.warning(f"Strategie '{strategy['name']}' nach {timeout_seconds} Sekunden abgelaufen")
            continue
        except Exception as e:
            logger.warning(f"Unerwarteter Fehler bei Strategie '{strategy['name']}': {str(e)}")
            continue
    
    logger.error("Alle Strategien für sehr große Datei fehlgeschlagen")
    return False

async def extract_with_alternative_runtime(
    file_path: str,
    dll_path: str,
    result_dir: str,
    format: str = "csv",
    pst_folder: str = "Calendar"
) -> bool:
    """
    Versucht Extraktion mit alternativen .NET-Runtimes und Konfigurationen.
    
    Args:
        file_path: Pfad zur PST/OST-Datei
        dll_path: Pfad zur .NET DLL
        result_dir: Zielverzeichnis für die Extraktion
        format: Export-Format ('csv' oder 'native')
        pst_folder: Name des zu extrahierenden Ordners
        
    Returns:
        bool: True wenn erfolgreich, False wenn fehlgeschlagen
    """
    logger.info(f"Versuche Extraktion mit alternativer Runtime: {file_path}")
    
    # Export-Option
    export_option = "-e" if format == "native" else "-p"
    
    # Verschiedene .NET-Runtime-Strategien
    strategies = [
        # Strategie 1: Explizite .NET 6.0 Runtime
        {
            "name": ".NET 6.0 Runtime",
            "cmd": ["dotnet", "--runtime", "6.0.0", dll_path, export_option, f"-f={pst_folder}", "-t=" + result_dir, file_path],
            "env": {
                "DOTNET_SYSTEM_GLOBALIZATION_INVARIANT": "1",
                "DOTNET_CLI_UI_LANGUAGE": "en",
                "DOTNET_GCHeapHardLimit": "0x4000000",  # 1GB
                "DOTNET_GCAllowVeryLargeObjects": "0"
            }
        },
        # Strategie 2: Explizite .NET Core 3.1 Runtime
        {
            "name": ".NET Core 3.1 Runtime",
            "cmd": ["dotnet", "--runtime", "3.1.0", dll_path, export_option, f"-f={pst_folder}", "-t=" + result_dir, file_path],
            "env": {
                "DOTNET_SYSTEM_GLOBALIZATION_INVARIANT": "1",
                "DOTNET_CLI_UI_LANGUAGE": "en",
                "DOTNET_GCHeapHardLimit": "0x1000000",  # 256MB
                "DOTNET_GCAllowVeryLargeObjects": "0"
            }
        },
        # Strategie 3: Ohne spezifische Runtime, aber mit minimaler Konfiguration
        {
            "name": "Minimale Konfiguration",
            "cmd": ["dotnet", dll_path, export_option, f"-f={pst_folder}", "-t=" + result_dir, file_path],
            "env": {
                "DOTNET_SYSTEM_GLOBALIZATION_INVARIANT": "1",
                "DOTNET_CLI_UI_LANGUAGE": "en",
                "DOTNET_GCHeapHardLimit": "0x1000000",  # 256MB
                "DOTNET_GCAllowVeryLargeObjects": "0",
                "DOTNET_GCHeapHardLimitPercent": "30"
            }
        }
    ]
    
    for strategy in strategies:
        logger.info(f"Versuche Strategie: {strategy['name']}")
        
        # Umgebungsvariablen setzen
        dotnet_env = os.environ.copy()
        dotnet_env.update(strategy["env"])
        
        try:
            process = subprocess.run(
                strategy['cmd'],
                capture_output=True,
                text=False,
                env=dotnet_env,
                timeout=1800  # 30 Minuten
            )
            
            if process.returncode == 0:
                logger.info(f"Strategie '{strategy['name']}' erfolgreich")
                return True
            else:
                stderr_text = process.stderr.decode('utf-8', errors='replace')
                logger.warning(f"Strategie '{strategy['name']}' fehlgeschlagen: {stderr_text}")
                
                # Wenn es ein CoreCLR-Fehler ist, versuche Runtime-Konfiguration
                if "Failed to create CoreCLR" in stderr_text:
                    runtime_config_path = os.path.join(os.path.dirname(dll_path), "runtimeconfig.json")
                    if os.path.exists(runtime_config_path):
                        logger.info("Versuche mit expliziter Runtime-Konfiguration")
                        
                        cmd_runtime = [
                            "dotnet",
                            "--runtime-config", runtime_config_path
                        ] + strategy['cmd'][1:]  # Entferne 'dotnet' und füge Runtime-Konfiguration hinzu
                        
                        process_runtime = subprocess.run(
                            cmd_runtime,
                            capture_output=True,
                            text=False,
                            env=dotnet_env,
                            timeout=1800
                        )
                        
                        if process_runtime.returncode == 0:
                            logger.info(f"Runtime-Konfigurations-Strategie '{strategy['name']}' erfolgreich")
                            return True
                        else:
                            stderr_runtime = process_runtime.stderr.decode('utf-8', errors='replace')
                            logger.warning(f"Runtime-Konfigurations-Strategie '{strategy['name']}' fehlgeschlagen: {stderr_runtime}")
                
                continue
                
        except subprocess.TimeoutExpired:
            logger.warning(f"Strategie '{strategy['name']}' nach 30 Minuten abgelaufen")
            continue
        except Exception as e:
            logger.warning(f"Unerwarteter Fehler bei Strategie '{strategy['name']}': {str(e)}")
            continue
    
    logger.error("Alle alternativen Runtime-Strategien fehlgeschlagen")
    return False

async def extract_with_file_chunking(
    file_path: str,
    dll_path: str,
    result_dir: str,
    format: str = "csv",
    pst_folder: str = "Calendar"
) -> bool:
    """
    Versucht Extraktion mit Datei-Chunking für sehr große Dateien.
    
    Args:
        file_path: Pfad zur PST/OST-Datei
        dll_path: Pfad zur .NET DLL
        result_dir: Zielverzeichnis für die Extraktion
        format: Export-Format ('csv' oder 'native')
        pst_folder: Name des zu extrahierenden Ordners
        
    Returns:
        bool: True wenn erfolgreich, False wenn fehlgeschlagen
    """
    logger.info(f"Versuche Extraktion mit Datei-Chunking: {file_path}")
    
    # Prüfe, ob die Datei zu groß ist für normale Verarbeitung
    file_size_gb = os.path.getsize(file_path) / (1024**3)
    
    if file_size_gb < 3.0:
        logger.info("Datei ist nicht groß genug für Chunking")
        return False
    
    # Versuche verschiedene Chunking-Strategien
    strategies = [
        # Strategie 1: Sehr konservative .NET-Konfiguration
        {
            "name": "Sehr konservative Konfiguration",
            "env": {
                "DOTNET_SYSTEM_GLOBALIZATION_INVARIANT": "1",
                "DOTNET_CLI_UI_LANGUAGE": "en",
                "DOTNET_GCHeapHardLimit": "0x800000",  # 128MB
                "DOTNET_GCAllowVeryLargeObjects": "0",
                "DOTNET_GCHeapHardLimitPercent": "20",
                "DOTNET_GCHeapHardLimitSOH": "0x400000",  # 64MB
                "DOTNET_GCHeapHardLimitLOH": "0x400000"   # 64MB
            }
        },
        # Strategie 2: Minimale Konfiguration mit expliziter Runtime
        {
            "name": "Minimale Konfiguration mit Runtime",
            "env": {
                "DOTNET_SYSTEM_GLOBALIZATION_INVARIANT": "1",
                "DOTNET_CLI_UI_LANGUAGE": "en",
                "DOTNET_GCHeapHardLimit": "0x400000",  # 64MB
                "DOTNET_GCAllowVeryLargeObjects": "0",
                "DOTNET_GCHeapHardLimitPercent": "10"
            }
        }
    ]
    
    export_option = "-e" if format == "native" else "-p"
    
    for strategy in strategies:
        logger.info(f"Versuche Chunking-Strategie: {strategy['name']}")
        
        # Umgebungsvariablen setzen
        dotnet_env = os.environ.copy()
        dotnet_env.update(strategy["env"])
        
        # Versuche verschiedene Befehle
        commands = [
            # Befehl 1: Nur Calendar-Ordner
            ["dotnet", dll_path, export_option, "-f=Calendar", "-t=" + result_dir, file_path],
            # Befehl 2: Nur Inbox-Ordner
            ["dotnet", dll_path, export_option, "-f=Inbox", "-t=" + result_dir, file_path],
            # Befehl 3: Alle Elemente
            ["dotnet", dll_path, export_option, "-t=" + result_dir, file_path]
        ]
        
        for i, cmd in enumerate(commands):
            logger.info(f"Versuche Befehl {i+1}: {' '.join(cmd)}")
            
            try:
                process = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=False,
                    env=dotnet_env,
                    timeout=3600  # 1 Stunde
                )
                
                if process.returncode == 0:
                    logger.info(f"Chunking-Strategie '{strategy['name']}' mit Befehl {i+1} erfolgreich")
                    return True
                else:
                    stderr_text = process.stderr.decode('utf-8', errors='replace')
                    logger.warning(f"Chunking-Strategie '{strategy['name']}' mit Befehl {i+1} fehlgeschlagen: {stderr_text}")
                    
                    # Wenn es ein CoreCLR-Fehler ist, versuche Runtime-Konfiguration
                    if "Failed to create CoreCLR" in stderr_text:
                        runtime_config_path = os.path.join(os.path.dirname(dll_path), "runtimeconfig.json")
                        if os.path.exists(runtime_config_path):
                            logger.info("Versuche mit expliziter Runtime-Konfiguration")
                            
                            cmd_runtime = [
                                "dotnet",
                                "--runtime-config", runtime_config_path
                            ] + cmd[1:]  # Entferne 'dotnet' und füge Runtime-Konfiguration hinzu
                            
                            process_runtime = subprocess.run(
                                cmd_runtime,
                                capture_output=True,
                                text=False,
                                env=dotnet_env,
                                timeout=3600
                            )
                            
                            if process_runtime.returncode == 0:
                                logger.info(f"Runtime-Konfigurations-Chunking '{strategy['name']}' mit Befehl {i+1} erfolgreich")
                                return True
                            else:
                                stderr_runtime = process_runtime.stderr.decode('utf-8', errors='replace')
                                logger.warning(f"Runtime-Konfigurations-Chunking '{strategy['name']}' mit Befehl {i+1} fehlgeschlagen: {stderr_runtime}")
                    
                    continue
                    
            except subprocess.TimeoutExpired:
                logger.warning(f"Chunking-Strategie '{strategy['name']}' mit Befehl {i+1} nach 1 Stunde abgelaufen")
                continue
            except Exception as e:
                logger.warning(f"Unerwarteter Fehler bei Chunking-Strategie '{strategy['name']}' mit Befehl {i+1}: {str(e)}")
                continue
    
    logger.error("Alle Chunking-Strategien fehlgeschlagen")
    return False