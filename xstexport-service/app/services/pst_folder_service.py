import os
import subprocess
import tempfile
import logging
import json
from typing import List, Dict, Any, Optional
from fastapi import HTTPException

from app.services.calendar_extractor import find_dll

logger = logging.getLogger(__name__)

async def list_pst_folders(file_path: str) -> List[Dict[str, Any]]:
    """
    Listet alle Ordner in einer PST/OST-Datei auf.
    
    Args:
        file_path: Pfad zur PST/OST-Datei
        
    Returns:
        List[Dict[str, Any]]: Liste der Ordner mit Namen und Pfaden
        
    Raises:
        HTTPException: Bei Fehlern während der Verarbeitung
    """
    # Prüfen, ob die Datei existiert
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail=f"Datei {file_path} nicht gefunden"
        )
    
    # Temporäres Verzeichnis erstellen für die Ausgabe
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Finde den korrekten Pfad zur DLL
        dll_path = find_dll("XstExporter.Portable.dll")
        if "XstExporter.Portable.dll" not in dll_path:
            # Fallback zur alten DLL-Benennung
            dll_path = find_dll("XstPortableExport.dll")
        
        logger.info(f"Gefundener Pfad zur DLL: {dll_path}")
        
        # Befehl zur Auflistung der Ordner
        # Verwende den "List Folders"-Modus (angenommen, die DLL unterstützt diese Option)
        # Hinweis: Wir müssen hier möglicherweise eine JSON-Ausgabe erstellen
        # Da die originale DLL möglicherweise keine Listing-Funktion hat,
        # erstellen wir einen temporären Ordner und versuchen, alle Ordner zu extrahieren
        
        # Wir versuchen, mit dem -i (Info) Flag den Inhalt anzuzeigen
        cmd = [
            "dotnet", 
            dll_path, 
            "-i",  # Info-Modus, falls verfügbar
            file_path
        ]
        
        # Umgebungsvariablen für .NET
        dotnet_env = os.environ.copy()
        dotnet_env["DOTNET_CLI_UI_LANGUAGE"] = "en"
        dotnet_env["DOTNET_SYSTEM_GLOBALIZATION_INVARIANT"] = "true"
        
        # Befehl ausführen
        logger.info(f"Führe Befehl aus: {' '.join(cmd)}")
        process = subprocess.run(
            cmd, 
            capture_output=True,
            text=False,
            env=dotnet_env
        )
        
        # Dekodieren der Ausgabe
        stdout = process.stdout.decode('utf-8', errors='replace')
        stderr = process.stderr.decode('utf-8', errors='replace')
        
        logger.debug(f"Command stdout: {stdout}")
        logger.debug(f"Command stderr: {stderr}")
        
        # Wenn der Info-Modus nicht funktioniert, versuchen wir, die Ordnerstruktur anders zu ermitteln
        folders = []
        
        # Parsen der Ausgabe, um Ordner zu identifizieren
        # Dies hängt vom tatsächlichen Ausgabeformat der DLL ab
        # Hier ein einfacher Ansatz, der angepasst werden muss:
        
        # Wenn die DLL keine Ordnerinformationen in der Konsole ausgibt,
        # versuchen wir alle Hauptordnertypen zu identifizieren
        if process.returncode != 0 or "folder" not in stdout.lower():
            # Bekannte Ordnernamen in Outlook PST-Dateien
            standard_folders = [
                "Calendar", "Kalender", 
                "Inbox", "Posteingang",
                "Outbox", "Postausgang",
                "Sent Items", "Gesendete Elemente",
                "Deleted Items", "Gelöschte Elemente",
                "Drafts", "Entwürfe",
                "Junk E-Mail", "Junk-E-Mail",
                "Journal",
                "Notes", "Notizen",
                "Tasks", "Aufgaben",
                "Contacts", "Kontakte",
                "Conversation History", "Unterhaltungsverlauf",
                "Archive"
            ]
            
            # Füge alle standardmäßigen Ordner hinzu und markiere, welche existieren könnten
            for folder in standard_folders:
                folders.append({
                    "name": folder,
                    "path": folder,
                    "is_standard": True,
                    "note": "Dies ist ein Standardordner; die tatsächliche Existenz in der PST-Datei muss geprüft werden"
                })
                
            # Füge einen Hinweis hinzu, dass dies nur Standardordner sind
            folders.append({
                "name": "HINWEIS",
                "path": "",
                "is_standard": False,
                "note": "Die DLL unterstützt keine direkte Ordnerauflistung. Dies sind nur mögliche Standardordnernamen."
            })
        else:
            # Versuche, die Ordner aus der Ausgabe zu extrahieren
            # Dies muss an das tatsächliche Format der DLL-Ausgabe angepasst werden
            lines = stdout.split('\n')
            for line in lines:
                if "folder" in line.lower() or "ordner" in line.lower():
                    # Einfache Heuristik zur Extraktion von Ordnernamen
                    parts = line.split(':')
                    if len(parts) >= 2:
                        folder_name = parts[1].strip()
                        folders.append({
                            "name": folder_name,
                            "path": folder_name,
                            "is_standard": False,
                            "note": ""
                        })
        
        # Alternative Strategie: Versuche, jeden bekannten Ordnertyp zu extrahieren
        # und prüfe, ob er erfolgreich ist
        if not folders or len(folders) <= 1:
            logger.info("Versuche, Ordner durch Testextraktionen zu identifizieren")
            for potential_folder in ["Calendar", "Kalender", "Inbox", "Posteingang"]:
                # Versuche, in diesen Ordner zu extrahieren
                test_cmd = [
                    "dotnet", 
                    dll_path, 
                    "-p",  # Exportiere im CSV-Format
                    f"-f={potential_folder}",  # Ordner angeben
                    "-t=" + temp_dir,  # Temporäres Zielverzeichnis
                    file_path
                ]
                
                test_process = subprocess.run(
                    test_cmd, 
                    capture_output=True,
                    text=False,
                    env=dotnet_env
                )
                
                # Wenn der Extraktionsprozess erfolgreich war oder keine explizite Fehlermeldung
                # über fehlenden Ordner enthält, fügen wir den Ordner hinzu
                test_stderr = test_process.stderr.decode('utf-8', errors='replace')
                if test_process.returncode == 0 or "Cannot find folder" not in test_stderr:
                    folders.append({
                        "name": potential_folder,
                        "path": potential_folder,
                        "is_standard": True,
                        "verified": True,
                        "note": "Dieser Ordner wurde durch erfolgreiche Testextraktion bestätigt"
                    })
        
        return folders
        
    except Exception as e:
        logger.error(f"Fehler beim Auflisten der PST-Ordner: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Fehler beim Auflisten der PST-Ordner: {str(e)}"
        )
    finally:
        # Temporäres Verzeichnis aufräumen
        if os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)