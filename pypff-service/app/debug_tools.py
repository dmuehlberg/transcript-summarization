# debug_tools.py
import os
import subprocess
import json
import pypff
from fastapi import UploadFile, File, Form
from property_utils import extract_all_properties_enhanced
from datetime import datetime
from folder_utils import find_folder_by_path, find_calendar_folders


async def pffexport_help():
    """
    Zeigt die Hilfe-Ausgabe des pffexport-Tools an, um die korrekten Optionen zu ermitteln.
    """
    try:
        result = subprocess.run(
            ["pffexport", "--help"], 
            check=True,
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        
        help_text = result.stdout.decode(errors="ignore")
        if not help_text:
            help_text = result.stderr.decode(errors="ignore")
            
        # Alle verfügbaren Optionen als strukturierte Daten zurückgeben
        options = []
        for line in help_text.split('\n'):
            if line.strip().startswith('-'):
                options.append(line.strip())
                
        return {
            "tool": "pffexport",
            "full_help": help_text,
            "available_options": options
        }
        
    except subprocess.CalledProcessError as e:
        return {
            "error": "Fehler beim Abrufen der Hilfe",
            "detail": e.stderr.decode(errors="ignore")
        }
    except FileNotFoundError:
        return {
            "error": "pffexport-Tool nicht gefunden",
            "suggestion": "Stellen Sie sicher, dass pffexport installiert ist"
        }
    pass

async def check_system_tools():
    """
    Überprüft, welche relevanten Tools im System installiert sind.
    """
    tools_to_check = ["pffexport", "pffinfo", "python3", "pip3"]
    results = {}
    
    for tool in tools_to_check:
        try:
            # Prüfen, ob das Tool im Pfad ist
            result = subprocess.run(
                ["which", tool], 
                check=True,
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
            path = result.stdout.decode(errors="ignore").strip()
            
            # Versionsinformationen abrufen, falls möglich
            version = "Unbekannt"
            try:
                if tool not in ["which", "pip3"]:
                    version_result = subprocess.run(
                        [tool, "--version"], 
                        check=True,
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE
                    )
                    version = version_result.stdout.decode(errors="ignore").strip()
                    if not version:
                        version = version_result.stderr.decode(errors="ignore").strip()
            except Exception:
                pass
                
            results[tool] = {
                "available": True,
                "path": path,
                "version": version
            }
        except subprocess.CalledProcessError:
            results[tool] = {
                "available": False
            }
    
    # Libpff Python-Bindings-Informationen
    results["pypff"] = {
        "available": True,
        "version": getattr(pypff, "__version__", "Unbekannt")
    }
            
    return {
        "system_tools": results,
        "container_info": {
            "hostname": subprocess.getoutput("hostname"),
            "python_version": subprocess.getoutput("python3 --version"),
            "debian_version": subprocess.getoutput("cat /etc/debian_version")
        }
    }
    pass

async def pffexport_options():
    """
    Versucht auf verschiedene Weisen, die verfügbaren Optionen des pffexport-Tools zu ermitteln.
    """
    results = {
        "tool_found": False,
        "tool_path": None,
        "help_options": {},
        "direct_run": None,
        "error_messages": []
    }
    
    # 1. Überprüfen, ob das Tool im Pfad ist
    try:
        which_result = subprocess.run(
            ["which", "pffexport"], 
            check=True,
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        tool_path = which_result.stdout.decode(errors="ignore").strip()
        if tool_path:
            results["tool_found"] = True
            results["tool_path"] = tool_path
    except subprocess.CalledProcessError as e:
        results["error_messages"].append(f"Tool nicht im Pfad: {e.stderr.decode(errors='ignore')}")
        return results
    
    # 2. Verschiedene Hilfeparameter ausprobieren
    help_options = ["--help", "-h", "-?", "/?", "/help", "help"]
    for option in help_options:
        try:
            help_result = subprocess.run(
                ["pffexport", option], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                timeout=2  # Timeout nach 2 Sekunden
            )
            stdout = help_result.stdout.decode(errors="ignore")
            stderr = help_result.stderr.decode(errors="ignore")
            
            # Prüfen, ob es Informationen in stdout oder stderr gibt
            output = stdout if stdout else stderr
            
            # Suchen nach Hinweisen auf Optionen
            if output and ("-" in output or "Usage:" in output or "usage:" in output):
                results["help_options"][option] = {
                    "success": True,
                    "output": output[:1000]  # Begrenzen, um große Ausgaben zu vermeiden
                }
            else:
                results["help_options"][option] = {
                    "success": False,
                    "output": output[:200] if output else "Keine Ausgabe"
                }
        except Exception as e:
            results["help_options"][option] = {
                "success": False,
                "error": str(e)
            }
    
    # 3. Tool ohne Parameter ausführen
    try:
        direct_result = subprocess.run(
            ["pffexport"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            timeout=2  # Timeout nach 2 Sekunden
        )
        
        stdout = direct_result.stdout.decode(errors="ignore")
        stderr = direct_result.stderr.decode(errors="ignore")
        
        # Oft gibt die direkte Ausführung ohne Parameter eine Nutzungsanleitung
        output = stdout if stdout else stderr
        
        results["direct_run"] = {
            "exit_code": direct_result.returncode,
            "output": output[:1000]  # Begrenzen, um große Ausgaben zu vermeiden
        }
    except Exception as e:
        results["direct_run"] = {
            "error": str(e)
        }
    
    # 4. Tool-Datei untersuchen (falls es eine Textdatei sein könnte)
    if results["tool_path"]:
        try:
            with open(results["tool_path"], "r", errors="ignore") as f:
                content = f.read(500)  # Die ersten 500 Zeichen lesen
                
                if "usage" in content.lower() or "help" in content.lower():
                    results["file_content"] = {
                        "success": True,
                        "preview": content
                    }
        except Exception as e:
            results["error_messages"].append(f"Konnte Tool-Datei nicht lesen: {str(e)}")
    
    return results
    pass

async def raw_pst_inspector(
    file: UploadFile = File(...),
    folder_path: str = Form("/")  # Optionaler Pfad zu einem bestimmten Ordner
):
    """
    Analysiert eine PST-Datei auf niedrigster Ebene, um alle zugänglichen Informationen zu extrahieren.
    
    Parameters:
    - file: PST/OST-Datei
    - folder_path: Optionaler Pfad zu einem bestimmten Ordner (z.B. "/Top of Personal Folders/Kalender")
    """
    # Original-Dateinamen speichern und säubern
    original_filename = file.filename
    safe_filename = ''.join(c for c in original_filename if c.isalnum() or c in '._-')
    
    # Aktuelles Datum/Uhrzeit für eindeutige Dateinamen
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Permanentes Datenverzeichnis
    data_dir = "/data/ost"
    
    # Arbeitsverzeichnis
    work_dir = os.path.join(data_dir, f"raw_pst_{timestamp}_{safe_filename}")
    os.makedirs(work_dir, exist_ok=True)
    
    # Pfade definieren
    in_path = os.path.join(work_dir, "input.pst")
    out_dir = os.path.join(work_dir, "output")
    os.makedirs(out_dir, exist_ok=True)
    
    # Zielpfad für das ZIP-File
    zip_filename = f"raw_pst_{timestamp}_{safe_filename}.zip"
    zip_path = os.path.join(data_dir, zip_filename)
    
    # Ergebnisse sammeln
    results = {
        "folder_count": 0,
        "message_count": 0,
        "folder_structure": [],
        "errors": [],
        "properties_found": set(),
    }
    
    try:
        # PST/OST-Datei speichern
        with open(in_path, "wb") as f:
            chunk_size = 1024 * 1024
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
        
        print(f"Datei {original_filename} erfolgreich gespeichert")
        
        # PST öffnen
        pst = pypff.file()
        pst.open(in_path)
        root_folder = pst.get_root_folder()
        
        # Objekt-Struktur analysieren und introspizieren
        def inspect_object(obj, prefix=""):
            """Analysiert ein pypff-Objekt mit Introspection"""
            attributes = {}
            
            # Schritt 1: Alle Attribute des Objekts erfassen
            for attr in dir(obj):
                if attr.startswith("_"):
                    continue  # Interne Attribute überspringen
                
                try:
                    value = getattr(obj, attr)
                    
                    # Methoden ignorieren
                    if callable(value):
                        continue
                        
                    # Wert in einen String konvertieren oder repr verwenden
                    if isinstance(value, (str, int, float, bool, type(None))):
                        attributes[attr] = value
                    else:
                        attributes[attr] = repr(value)
                except Exception as e:
                    attributes[f"{attr}_error"] = f"Fehler: {str(e)}"
            
            # Schritt 2: Methoden aufrufen, die keine Parameter erfordern
            methods = {}
            for attr in dir(obj):
                if attr.startswith("_") or not callable(getattr(obj, attr)):
                    continue
                
                try:
                    # Nur parameterlose Methoden aufrufen
                    method_obj = getattr(obj, attr)
                    if "get_" in attr or "is_" in attr or "has_" in attr:
                        result = method_obj()
                        if isinstance(result, (str, int, float, bool, type(None))):
                            methods[attr] = result
                        else:
                            methods[attr] = repr(result)
                except Exception:
                    # Methoden, die Parameter benötigen, ignorieren
                    pass
            
            # Schritt 3: Auf Property-Werte zugreifen, wenn verfügbar
            properties = {}
            
            # Direkte property_values-Zugriff prüfen
            if hasattr(obj, "property_values"):
                try:
                    prop_values = obj.property_values
                    for prop_id, value in prop_values.items():
                        # Hexadezimale Darstellung des Property IDs
                        prop_name = f"0x{prop_id:04X}"
                        
                        # Wert konvertieren
                        if isinstance(value, bytes):
                            try:
                                str_value = value.decode('utf-8', errors='ignore').strip('\x00')
                                properties[prop_name] = str_value
                                # Für die Gesamtstatistik
                                results["properties_found"].add(prop_name)
                            except Exception:
                                properties[prop_name] = value.hex()
                        else:
                            properties[prop_name] = value
                except Exception as e:
                    properties["property_values_error"] = f"Fehler: {str(e)}"
            
            # Ältere API: get_number_of_properties und get_property_*
            if hasattr(obj, "get_number_of_properties"):
                try:
                    num_props = obj.get_number_of_properties()
                    properties["count"] = num_props
                    
                    for i in range(num_props):
                        try:
                            prop_type = obj.get_property_type(i)
                            prop_tag = obj.get_property_tag(i)
                            prop_value = obj.get_property_data(prop_tag)
                            
                            # Hexadezimale Darstellung des Property-Tags
                            prop_name = f"0x{prop_tag:04X}"
                            
                            # Wert konvertieren
                            if isinstance(prop_value, bytes):
                                try:
                                    str_value = prop_value.decode('utf-8', errors='ignore').strip('\x00')
                                    properties[prop_name] = str_value
                                    # Für die Gesamtstatistik
                                    results["properties_found"].add(prop_name)
                                except Exception:
                                    properties[prop_name] = prop_value.hex()
                            else:
                                properties[prop_name] = prop_value
                        except Exception as e:
                            properties[f"property_{i}_error"] = f"Fehler: {str(e)}"
                except Exception as e:
                    properties["get_properties_error"] = f"Fehler: {str(e)}"
            
            return {
                "attributes": attributes,
                "methods": methods,
                "properties": properties,
                "type": type(obj).__name__
            }
        
        # Hilfsfunktion um einen Ordnerpfad zu extrahieren
        def get_folder_path(folder):
            path_parts = []
            current = folder
            while current:
                name = current.name or "Unnamed"
                path_parts.append(name)
                # Zugriff auf parent-Attribut oder parent-Methode
                if hasattr(current, "parent") and not callable(current.parent):
                    current = current.parent
                elif hasattr(current, "get_parent"):
                    try:
                        current = current.get_parent()
                    except Exception:
                        current = None
                else:
                    current = None
            return "/" + "/".join(reversed(path_parts))
        
        # Hilfsfunktion, um einen Ordner nach Pfad zu finden
        def find_folder_by_path(root, target_path):
            if target_path == "/" or not target_path:
                return root
                
            path_parts = [p for p in target_path.split("/") if p]
            current = root
            
            for part in path_parts:
                found = False
                for i in range(current.number_of_sub_folders):
                    sub_folder = current.get_sub_folder(i)
                    if sub_folder.name and sub_folder.name.lower() == part.lower():
                        current = sub_folder
                        found = True
                        break
                
                if not found:
                    return None
            
            return current
        
        # Folder für die Analyse finden
        target_folder = root_folder
        if folder_path and folder_path != "/":
            target_folder = find_folder_by_path(root_folder, folder_path)
            if not target_folder:
                raise ValueError(f"Ordner '{folder_path}' nicht gefunden")
        
        # Rekursive Analyse der Ordnerstruktur
        def analyze_folder(folder, path=""):
            results["folder_count"] += 1
            folder_info = {
                "name": folder.name or "Unnamed",
                "path": path + "/" + (folder.name or "Unnamed"),
                "sub_folders": folder.number_of_sub_folders,
                "messages": folder.number_of_sub_messages,
                "inspection": inspect_object(folder)
            }
            
            # Nachrichten im Ordner analysieren
            message_infos = []
            for i in range(folder.number_of_sub_messages):
                try:
                    results["message_count"] += 1
                    msg = folder.get_sub_message(i)
                    
                    # Nachrichten analysieren
                    message_info = {
                        "index": i,
                        "inspection": inspect_object(msg)
                    }
                    
                    # Betreff extrahieren (wenn vorhanden)
                    subject = None
                    if "properties" in message_info["inspection"]:
                        # Bekannte Property-ID für Betreff: 0x0037
                        subject = message_info["inspection"]["properties"].get("0x0037", f"Message {i}")
                    
                    message_info["subject"] = subject
                    message_infos.append(message_info)
                    
                    # Erste 10 Nachrichten als einzelne Dateien speichern (für detaillierte Analyse)
                    if len(message_infos) <= 10:
                        msg_path = os.path.join(out_dir, f"message_{results['message_count']}_{i}.json")
                        with open(msg_path, "w") as f:
                            import json
                            json.dump(message_info, f, indent=2, default=str)
                except Exception as e:
                    results["errors"].append(f"Fehler bei Nachricht {i} in {folder_info['path']}: {str(e)}")
            
            folder_info["messages_info"] = message_infos
            
            # Unterordner rekursiv analysieren
            sub_folders = []
            for i in range(folder.number_of_sub_folders):
                try:
                    sub_folder = folder.get_sub_folder(i)
                    sub_info = analyze_folder(sub_folder, folder_info["path"])
                    sub_folders.append(sub_info)
                except Exception as e:
                    results["errors"].append(f"Fehler bei Unterordner {i} in {folder_info['path']}: {str(e)}")
            
            folder_info["sub_folders_info"] = sub_folders
            return folder_info
        
        # Analyse starten
        folder_info = analyze_folder(target_folder)
        results["folder_structure"] = folder_info
        
        # Property-Liste in eine sortierte Liste umwandeln
        sorted_properties = sorted(list(results["properties_found"]))
        results["properties_found"] = sorted_properties
        
        # Ergebnisse speichern
        summary_path = os.path.join(out_dir, "summary.json")
        with open(summary_path, "w") as f:
            import json
            json.dump({
                "file": original_filename,
                "timestamp": timestamp,
                "folder_count": results["folder_count"],
                "message_count": results["message_count"],
                "properties_found": results["properties_found"],
                "errors": results["errors"]
            }, f, indent=2, default=str)
        
        # Ordnerstruktur speichern (ohne die detaillierten Nachrichteninspektionen)
        structure_path = os.path.join(out_dir, "folder_structure.json")
        with open(structure_path, "w") as f:
            import json
            # Hilfsfunktion zum Bereinigen der Struktur (nur wichtige Infos behalten)
            def clean_structure(folder):
                return {
                    "name": folder["name"],
                    "path": folder["path"],
                    "sub_folders": folder["sub_folders"],
                    "messages": folder["messages"],
                    "message_subjects": [m.get("subject", f"Message {i}") for i, m in enumerate(folder.get("messages_info", []))],
                    "sub_folders_info": [clean_structure(sub) for sub in folder.get("sub_folders_info", [])]
                }
            
            json.dump(clean_structure(folder_info), f, indent=2, default=str)
        
        # Menschenlesbare Properties-Tabelle erstellen
        properties_path = os.path.join(out_dir, "properties_table.txt")
        with open(properties_path, "w") as f:
            f.write("GEFUNDENE MAPI-PROPERTIES\n")
            f.write("=" * 50 + "\n\n")
            f.write("| Property ID | Bekannte Bedeutung |\n")
            f.write("|-------------|-------------------|\n")
            
            # Bekannte MAPI-Properties
            known_props = {
                "0x001A": "PR_MESSAGE_CLASS",
                "0x0037": "PR_SUBJECT",
                "0x003D": "PR_CREATION_TIME",
                "0x1000": "PR_BODY",
                "0x0C1A": "PR_SENDER_NAME",
                "0x8004": "PidLidAppointmentStartWhole",
                "0x8005": "PidLidAppointmentEndWhole",
                "0x0063": "PidLidResponseStatus",
                "0x0024": "PidLidLocation",
                "0x0065": "PidLidReminderMinutesBeforeStart",
                "0x0E1D": "PR_NORMALIZED_SUBJECT",
                "0x0070": "PR_CONVERSATION_TOPIC",
                "0x0023": "PR_LAST_MODIFICATION_TIME",
                "0x0E04": "PR_DISPLAY_TO",
                "0x0E03": "PR_DISPLAY_CC",
                "0x0062": "PR_IMPORTANCE",
                "0x0017": "PR_IMPORTANCE (alternate)",
                "0x0036": "PR_SENSITIVITY",
                "0x000F": "PR_REPLY_RECIPIENT_NAMES",
                "0x0FFF": "PR_HTML",
                "0x0C1F": "PR_SENDER_ADDRTYPE",
                "0x0075": "PR_RECEIVED_BY_NAME",
                "0x0E1F": "PR_MSG_STATUS",
                "0x8201": "PidLidAppointmentRecur",
                "0x8216": "PidLidAppointmentAllDayEvent",
                "0x0E2D": "PR_HASATTACH",
                "0x8580": "PidLidRecurrenceType",
                "0x8582": "PidLidRecurrencePattern",
                "0x8501": "PidLidReminderSet",
                "0x001F": "PidTagSenderName"
            }
            
            for prop_id in sorted_properties:
                known_name = known_props.get(prop_id.upper(), "Unbekannt")
                f.write(f"| {prop_id} | {known_name} |\n")
        
        # ZIP-Datei erstellen
        import zipfile
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(out_dir):
                for file_name in files:
                    file_path = os.path.join(root, file_name)
                    rel_path = os.path.relpath(file_path, out_dir)
                    zipf.write(file_path, rel_path)
        
        # Erfolgsmeldung zurückgeben
        return {
            "success": True,
            "message": f"PST Raw-Analyse erfolgreich. {results['folder_count']} Ordner und {results['message_count']} Nachrichten gefunden.",
            "file_path": f"/data/ost/{zip_filename}",
            "folder_count": results["folder_count"],
            "message_count": results["message_count"],
            "properties_count": len(results["properties_found"]),
            "errors_count": len(results["errors"]),
            "download_url": f"/download/{zip_filename}"
        }
    
    except Exception as e:
        # Allgemeiner Fehler
        error_msg = str(e)
        print(f"Unerwarteter Fehler: {error_msg}")
        return {
            "success": False,
            "message": f"Fehler bei der PST-Analyse: {error_msg}"
        }
    
    finally:
        # PST-Datei schließen
        if 'pst' in locals():
            try:
                pst.close()
            except Exception:
                pass
    pass

async def inspect_calendar_properties(
    file: UploadFile = File(...),
    folder_path: str = Form(""),  # Optionaler Pfad zum Kalenderordner
    max_items: int = Form(5)      # Maximale Anzahl zu inspizierender Kalendereinträge
):
    """
    Inspiziert detailliert die Kalendereigenschaften in einer PST-Datei.
    
    Besonders nützlich, um alle verfügbaren Eigenschaften und ihre Werte anzuzeigen,
    damit die korrekten Property-IDs für die Kalenderextraktion bestimmt werden können.
    
    Parameters:
    - file: PST/OST-Datei
    - folder_path: Optionaler Pfad zum spezifischen Kalenderordner
    - max_items: Maximale Anzahl zu inspizierender Kalendereinträge
    """
    # Funktionen, Variablen und Import-Statements wie im erweiterten Kalendererport-Endpunkt
    
    # Original-Dateinamen speichern und säubern
    original_filename = file.filename
    safe_filename = ''.join(c for c in original_filename if c.isalnum() or c in '._-')
    
    # Aktuelles Datum/Uhrzeit für eindeutige Dateinamen
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Temporäres Verzeichnis für die Verarbeitung
    work_dir = os.path.join("/tmp", f"cal_inspect_{timestamp}")
    os.makedirs(work_dir, exist_ok=True)
    
    # Pfade definieren
    in_path = os.path.join(work_dir, "input.pst")
    
    try:
        # PST/OST-Datei in Chunks speichern
        with open(in_path, "wb") as f:
            chunk_size = 1024 * 1024  # 1MB pro Chunk
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
        
        # PST öffnen
        pst = None
        inspection_results = {
            "file_info": {
                "filename": original_filename,
                "inspect_time": datetime.now().isoformat()
            },
            "calendar_folders": [],
            "inspected_items": [],
            "property_stats": {}  # Statistiken über gefundene Eigenschaften
        }
        
        try:
            pst = pypff.file()
            pst.open(in_path)
            root_folder = pst.get_root_folder()
            
            # Kalenderordner finden
            calendar_folders = []
            
            if folder_path:
                # Wenn ein bestimmter Pfad angegeben wurde, diesen verwenden
                target_folder = find_folder_by_path(root_folder, folder_path)
                if target_folder:
                    calendar_folders = [{
                        "name": target_folder.name or "Spezifizierter Ordner",
                        "path": folder_path,
                        "folder": target_folder,
                        "message_count": target_folder.number_of_sub_messages
                    }]
                else:
                    return {
                        "success": False,
                        "message": f"Ordner nicht gefunden: {folder_path}"
                    }
            else:
                # Automatische Suche nach Kalenderordnern
                calendar_folders = find_calendar_folders(root_folder)
            
            # Kalenderordner speichern
            inspection_results["calendar_folders"] = [
                {
                    "name": f["name"],
                    "path": f["path"],
                    "message_count": f["message_count"]
                } for f in calendar_folders
            ]
            
            # Kalendereinträge inspizieren
            items_inspected = 0
            property_counts = {}  # Zählt das Vorkommen jeder Property
            
            for folder_info in calendar_folders:
                folder = folder_info["folder"]
                folder_path = folder_info["path"]
                
                # Maximal max_items Nachrichten pro Ordner durchgehen
                message_count = min(folder.number_of_sub_messages, max_items)
                
                for i in range(message_count):
                    try:
                        # Nachricht abrufen
                        msg = folder.get_sub_message(i)
                        
                        # Alle Eigenschaften extrahieren
                        all_props = extract_all_properties_enhanced(msg)
                        
                        # Nachrichtenklasse bestimmen
                        msg_class = None
                        for prop_id in ["0x001A", "0x001A001F"]:
                            if prop_id in all_props:
                                msg_class = all_props[prop_id]
                                break
                        
                        if not msg_class:
                            msg_class = "Unknown"
                        
                        # Ist es ein Kalendereintrag?
                        is_calendar = (
                            "IPM.Appointment" in str(msg_class) or
                            "IPM.Schedule.Meeting" in str(msg_class) or
                            "calendar" in str(msg_class).lower() or
                            "appointment" in str(msg_class).lower() or
                            "{00061055-0000-0000-C000-000000000046}" in str(msg_class)
                        )
                        
                        # Relevanz berechnen
                        relevance = 0
                        
                        # Erhöhung der Relevanz bei bestimmten Eigenschaften
                        for prop_id in ["0x8004", "0x8005", "0x0024", "0x8216", "0x8501"]:
                            if prop_id in all_props:
                                relevance += 1
                        
                        # Erhöhung für Kalenderklasse
                        if is_calendar:
                            relevance += 3
                        
                        # Statistiken über Eigenschaften aktualisieren
                        for prop_id, value in all_props.items():
                            if prop_id.startswith("0x"):  # Nur echte Eigenschaften zählen
                                if prop_id not in property_counts:
                                    property_counts[prop_id] = {
                                        "count": 0,
                                        "calendar_count": 0,
                                        "example_value": None
                                    }
                                
                                property_counts[prop_id]["count"] += 1
                                
                                if is_calendar:
                                    property_counts[prop_id]["calendar_count"] += 1
                                
                                # Beispielwert speichern (falls noch nicht vorhanden)
                                if property_counts[prop_id]["example_value"] is None:
                                    # Für lange Werte nur die ersten 100 Zeichen speichern
                                    if isinstance(value, str) and len(value) > 100:
                                        property_counts[prop_id]["example_value"] = value[:100] + "..."
                                    else:
                                        property_counts[prop_id]["example_value"] = value
                        
                        # Betreff für die Anzeige extrahieren
                        subject = "Ohne Betreff"
                        for prop_id in ["0x0037", "0x0037001F", "0x0E1D", "0x0070"]:
                            if prop_id in all_props and all_props[prop_id]:
                                subject = all_props[prop_id]
                                break
                        
                        # Eintrag zur Liste hinzufügen
                        item_info = {
                            "folder": folder_path,
                            "index": i,
                            "message_class": msg_class,
                            "subject": subject,
                            "is_calendar_item": is_calendar,
                            "relevance": relevance,
                            "property_count": len([p for p in all_props.keys() if p.startswith("0x")]),
                            "all_properties": {k: v for k, v in all_props.items() if k.startswith("0x")}
                        }
                        
                        inspection_results["inspected_items"].append(item_info)
                        items_inspected += 1
                        
                    except Exception as e:
                        print(f"Fehler bei Nachricht {i} in {folder_path}: {str(e)}")
            
            # Property-Statistiken sortieren und formatieren
            property_stats = []
            for prop_id, stats in property_counts.items():
                property_stats.append({
                    "property_id": prop_id,
                    "total_count": stats["count"],
                    "calendar_count": stats["calendar_count"],
                    "calendar_percentage": int(stats["calendar_count"] / max(1, stats["count"]) * 100),
                    "example_value": stats["example_value"]
                })
            
            # Nach Relevanz für Kalendereinträge sortieren
            property_stats.sort(key=lambda x: x["calendar_percentage"], reverse=True)
            inspection_results["property_stats"] = property_stats
            
            # Ergebnisse sortieren - Kalendereinträge zuerst, dann nach Relevanz
            inspection_results["inspected_items"].sort(
                key=lambda x: (not x["is_calendar_item"], -x["relevance"])
            )
            
            return {
                "success": True,
                "message": f"Eigenschaften inspiziert: {items_inspected} Elemente in {len(calendar_folders)} Kalenderordnern",
                "inspection_results": inspection_results
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Fehler beim Inspizieren der PST-Datei: {str(e)}"
            }
        
        finally:
            # PST-Datei schließen
            if pst:
                try:
                    pst.close()
                except Exception:
                    pass
    
    except Exception as e:
        return {
            "success": False,
            "message": f"Unerwarteter Fehler: {str(e)}"
        }
    
    finally:
        # Arbeitsverzeichnis aufräumen
        try:
            if os.path.exists(work_dir):
                shutil.rmtree(work_dir)
        except Exception as e:
            print(f"Fehler beim Aufräumen: {str(e)}")
    pass


def inspect_message_diagnostics(msg):
    """Zeigt detaillierte diagnostische Informationen über eine Nachricht"""
    diagnostics = {
        "object_type": type(msg).__name__,
        "available_attributes": dir(msg),
        "has_property_values": hasattr(msg, "property_values"),
        "property_values_size": len(msg.property_values) if hasattr(msg, "property_values") else 0,
        "has_get_property_data": hasattr(msg, "get_property_data"),
        "has_get_message_class": hasattr(msg, "get_message_class"),
        "message_class": None
    }
    
    # Versuche, die Nachrichtenklasse zu extrahieren
    try:
        if hasattr(msg, "get_message_class"):
            diagnostics["message_class"] = msg.get_message_class()
        elif hasattr(msg, "property_values") and 0x001A in msg.property_values:
            diagnostics["message_class"] = msg.property_values[0x001A]
    except Exception as e:
        diagnostics["message_class_error"] = str(e)
    
    return diagnostics

async def message_diagnostics(
    file: UploadFile = File(...),
    folder_path: str = Form(""),
    index: int = Form(0)
):
    """
    Zeigt detaillierte Diagnose-Informationen für eine bestimmte Nachricht.
    
    Parameters:
    - file: PST/OST-Datei
    - folder_path: Pfad zum Ordner (z.B. "/Unnamed/Top of Personal Folders/mail@david-muehlberg.de/Kalender")
    - index: Index der Nachricht im Ordner (z.B. 0, 1, 2, ...)
    """
    # Initialisiere temp_file Variable, bevor sie verwendet wird
    temp_file = f"/tmp/diagnostic_{datetime.now().strftime('%Y%m%d%H%M%S')}.pst"
    
    try:
        # Speichere die Datei temporär
        with open(temp_file, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Öffne die PST-Datei
        pst = None
        try:
            pst = pypff.file()
            pst.open(temp_file)
            root_folder = pst.get_root_folder()
            
            # Finde den angegebenen Ordner
            target_folder = root_folder
            if folder_path:
                target_folder = find_folder_by_path(root_folder, folder_path)
                if not target_folder:
                    return {"error": f"Ordner nicht gefunden: {folder_path}"}
            
            # Prüfe, ob der Index gültig ist
            if index < 0 or index >= target_folder.number_of_sub_messages:
                return {"error": f"Ungültiger Index: {index}. Der Ordner hat {target_folder.number_of_sub_messages} Nachrichten."}
            
            # Hole die Nachricht
            msg = target_folder.get_sub_message(index)
            
            # Sammle Diagnose-Informationen
            diagnostics = inspect_message_diagnostics(msg)
            
            # Versuche aggressiv, alle Properties zu extrahieren
            properties = extract_all_properties_enhanced(msg)
            
            # Füge auch die rohen Bytes der ersten 200 Byte der Nachricht hinzu
            try:
                if hasattr(msg, "get_data"):
                    data = msg.get_data()
                    if data:
                        diagnostics["raw_data_preview"] = data[:200].hex()
            except Exception as e:
                diagnostics["raw_data_error"] = str(e)
            
            return {
                "success": True,
                "message": f"Diagnose für Nachricht {index} in {folder_path}",
                "diagnostics": diagnostics,
                "properties": properties
            }
        finally:
            # PST-Datei schließen
            if pst:
                try:
                    pst.close()
                except Exception:
                    pass
    
    except Exception as e:
        return {"success": False, "message": f"Fehler: {str(e)}"}
    
    finally:
        # Temporäre Datei aufräumen
        if os.path.exists(temp_file):
            os.remove(temp_file)
