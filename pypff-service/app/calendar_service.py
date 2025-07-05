# calendar_service.py
import os
import shutil
import json
import re
import zipfile
from fastapi import UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from datetime import datetime
import pypff

from property_utils import extract_properties, extract_all_properties
from folder_utils import find_folder_by_path, find_calendar_folders
from constants import CALENDAR_PROPS, EXTENDED_PROPS, STANDARD_CAL_PROPS, EXTENDED_CAL_PROPS

async def export_calendar(
    file: UploadFile = File(...),
    extended: bool = Form(False)  # Erweiterte Eigenschaften für Kalendereinträge extrahieren
):
    """
    Exportiert speziell Kalendereinträge aus PST/OST-Dateien mit Fokus auf die relevanten Eigenschaften.
    
    Parameters:
    - file: PST/OST-Datei
    - extended: Falls true, werden zusätzliche MAPI-Eigenschaften extrahiert
    """
    # Original-Dateinamen speichern und säubern
    original_filename = file.filename
    safe_filename = ''.join(c for c in original_filename if c.isalnum() or c in '._-')
    
    # Aktuelles Datum/Uhrzeit für eindeutige Dateinamen
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Permanentes Datenverzeichnis (das gemounted ist)
    data_dir = "/data/ost"
    
    # Temporäres Verzeichnis für die Verarbeitung
    work_dir = os.path.join(data_dir, f"calendar_export_{timestamp}_{safe_filename}")
    os.makedirs(work_dir, exist_ok=True)
    
    # Pfade definieren
    in_path = os.path.join(work_dir, "input.pst")
    out_dir = os.path.join(work_dir, "output")
    os.makedirs(out_dir, exist_ok=True)
    cal_dir = os.path.join(out_dir, "calendar")
    os.makedirs(cal_dir, exist_ok=True)
    
    # Zielpfad für das ZIP-File im /data/ost Verzeichnis
    zip_filename = f"calendar_export_{timestamp}_{safe_filename}.zip"
    zip_path = os.path.join(data_dir, zip_filename)
    
   
    
    # Dictionary mit Properties kombinieren je nach extended Flag
    properties_to_check = CALENDAR_PROPS.copy()
    if extended:
        properties_to_check.update(EXTENDED_PROPS)
    
    try:
        # PST/OST-Datei in Chunks speichern
        with open(in_path, "wb") as f:
            chunk_size = 1024 * 1024  # 1MB pro Chunk
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
        
        print(f"Datei {original_filename} erfolgreich gespeichert als {in_path}")
        
        # Datei mit pypff öffnen
        pst = None
        try:
            pst = pypff.file()
            pst.open(in_path)
            root_folder = pst.get_root_folder()
            
            # Infotext erstellen
            with open(os.path.join(out_dir, "info.txt"), "w") as f:
                f.write(f"Kalenderexport aus PST-Datei: {original_filename}\n")
                f.write(f"Export-Datum: {datetime.now().isoformat()}\n")
                f.write(f"Anzahl Root-Ordner: {root_folder.number_of_sub_folders}\n")
                f.write(f"Nachrichten im Root: {root_folder.number_of_sub_messages}\n")
            
            # Kalendereinträge zählen
            calendar_count = 0
            total_msg_count = 0
            
            # Diese Funktion extrahiert die Eigenschaften einer Nachricht mit Fokus auf Kalendereigenschaften
            def extract_properties(msg):
                props = {}
                
                # Nachrichtenklasse zuerst ermitteln
                msg_class = None
                try:
                    if hasattr(msg, "get_message_class"):
                        msg_class = msg.get_message_class()
                    elif hasattr(msg, "property_values") and 0x001A in msg.property_values:
                        msg_class = msg.property_values[0x001A]
                    elif hasattr(msg, "get_property_data"):
                        msg_class = msg.get_property_data(0x001A)
                        
                    # String-Konvertierung
                    if isinstance(msg_class, bytes):
                        msg_class = msg_class.decode('utf-8', errors='ignore')
                    else:
                        msg_class = str(msg_class or "Unknown")
                except Exception as e:
                    msg_class = f"Error getting class: {str(e)}"
                
                props["Message Class"] = msg_class
                
                # Alle relevanten Eigenschaften durchgehen
                for prop_id, prop_name in properties_to_check.items():
                    try:
                        # Wert über verschiedene Methoden extrahieren
                        value = None
                        if hasattr(msg, "property_values") and prop_id in msg.property_values:
                            value = msg.property_values[prop_id]
                        elif hasattr(msg, "get_property_data"):
                            try:
                                value = msg.get_property_data(prop_id)
                            except:
                                pass
                        
                        # Bereinigen und konvertieren
                        if value is not None:
                            if isinstance(value, bytes):
                                try:
                                    # Für Datum/Zeitwerte
                                    if prop_id in [0x8004, 0x8005, 0x003D, 0x0023, 0x8502]:
                                        # Versuchen, als Datumsstring zu interpretieren
                                        if b":" in value and b"-" in value:  # Wahrscheinlich ein ISO-Datum
                                            value = value.decode('utf-8', errors='ignore').strip('\x00')
                                        else:
                                            # Möglicherweise ein binäres Datum - als HEX ausgeben
                                            value = value.hex()
                                    else:
                                        # Standardkonvertierung für Strings
                                        value = value.decode('utf-8', errors='ignore').strip('\x00')
                                except Exception:
                                    # Fallback auf Hex-Darstellung
                                    value = value.hex()
                            props[prop_name] = value
                    except Exception as e:
                        # Fehler protokollieren, aber fortfahren
                        print(f"Fehler beim Extrahieren von {prop_name}: {str(e)}")
                
                return props, msg_class
            
            # Diese Funktion exportiert rekursiv alle Kalendereinträge aus einem Ordner
            def export_calendar_items(folder, folder_path):
                nonlocal calendar_count, total_msg_count
                
                # Ordnernamen für den Pfad extrahieren und bereinigen
                folder_name = folder.name or "Unnamed"
                safe_name = ''.join(c for c in folder_name if c.isalnum() or c in ' ._-')
                current_path = os.path.join(folder_path, safe_name)
                
                # Speziellen Kalenderordner für mögliche Kalendereinträge erstellen
                if "Calendar" in folder_name or "Kalender" in folder_name:
                    calendar_folder_path = os.path.join(cal_dir, safe_name)
                    os.makedirs(calendar_folder_path, exist_ok=True)
                    
                    # Info über den Kalenderordner schreiben
                    with open(os.path.join(calendar_folder_path, "_calendar_info.txt"), "w") as f:
                        f.write(f"Kalenderordner: {folder_name}\n")
                        f.write(f"Anzahl Elemente: {folder.number_of_sub_messages}\n")
                        f.write(f"Pfad: {folder_path}/{safe_name}\n")
                else:
                    # Kein Kalenderordner, aber trotzdem nach Kalendereinträgen suchen
                    calendar_folder_path = None
                
                # Alle Nachrichten im Ordner durchgehen
                for i in range(folder.number_of_sub_messages):
                    total_msg_count += 1
                    try:
                        msg = folder.get_sub_message(i)
                        
                        # Eigenschaften extrahieren
                        props, msg_class = extract_properties(msg)
                        
                        # Ist es ein Kalendereintrag?
                        is_calendar_item = (
                            "IPM.Appointment" in msg_class or
                            "IPM.Schedule.Meeting" in msg_class or
                            "IPM.OLE.CLASS.{00061055-0000-0000-C000-000000000046}" in msg_class
                        )
                        
                        if is_calendar_item:
                            calendar_count += 1
                            
                            # Betreff und Datum für den Dateinamen extrahieren
                            subject = props.get("Subject", f"NoSubject_{i}")
                            safe_subject = ''.join(c for c in subject if c.isalnum() or c in ' ._-')
                            safe_subject = safe_subject[:50]  # Längenbegrenzung
                            
                            # Start- und Endzeit extrahieren für den Dateinamen
                            start_time = props.get("Start Time", "")
                            if start_time:
                                # Versuchen, ein Datum zu extrahieren und zu formatieren
                                try:
                                    if isinstance(start_time, str) and "T" in start_time:
                                        date_part = start_time.split("T")[0]
                                        safe_subject = f"{date_part}_{safe_subject}"
                                except Exception:
                                    pass
                            
                            # Speicherort festlegen - im speziellen Kalenderordner oder im aktuellen Ordner
                            save_path = calendar_folder_path if calendar_folder_path else current_path
                            os.makedirs(save_path, exist_ok=True)
                            
                            # Kalendereintrag als Text speichern
                            cal_file = os.path.join(save_path, f"calendar_{calendar_count}_{safe_subject}.txt")
                            with open(cal_file, "w", encoding="utf-8") as f:
                                # Wichtige Eigenschaften zuerst
                                f.write(f"KALENDEREINTRAG #{calendar_count}\n")
                                f.write(f"{'='*50}\n")
                                
                                # Wichtige Attribute in einer bestimmten Reihenfolge anzeigen
                                for key in ["Subject", "Start Time", "End Time", "Location", "Body", "Display To"]:
                                    if key in props:
                                        f.write(f"{key}: {props[key]}\n")
                                
                                f.write(f"\nALLE EIGENSCHAFTEN:\n")
                                f.write(f"{'-'*50}\n")
                                
                                # Alle anderen Eigenschaften sortiert ausgeben
                                for key, value in sorted(props.items()):
                                    f.write(f"{key}: {value}\n")
                    except Exception as msg_error:
                        # Fehler bei einzelnen Nachrichten protokollieren, aber weitermachen
                        print(f"Fehler beim Verarbeiten der Nachricht {i}: {str(msg_error)}")
                
                # Unterordner rekursiv durchsuchen
                for i in range(folder.number_of_sub_folders):
                    try:
                        sub_folder = folder.get_sub_folder(i)
                        export_calendar_items(sub_folder, current_path)
                    except Exception as folder_error:
                        print(f"Fehler beim Verarbeiten des Unterordners {i}: {str(folder_error)}")
            
            # Export starten
            export_calendar_items(root_folder, out_dir)
            
            # Zusammenfassung erstellen
            with open(os.path.join(out_dir, "calendar_summary.txt"), "w") as f:
                f.write(f"Kalenderexport abgeschlossen\n")
                f.write(f"Gefundene Kalendereinträge: {calendar_count}\n")
                f.write(f"Gesamtzahl der Nachrichten: {total_msg_count}\n")
                f.write(f"Erweiterte Eigenschaften: {'Ja' if extended else 'Nein'}\n")
                f.write(f"Export-Ende: {datetime.now().isoformat()}\n")
        
        except Exception as pff_error:
            # Fehler protokollieren, aber fortfahren
            error_msg = str(pff_error)
            print(f"Fehler beim Verarbeiten der PST-Datei: {error_msg}")
            with open(os.path.join(out_dir, "error.txt"), "w") as f:
                f.write(f"Fehler beim Verarbeiten der PST-Datei: {error_msg}\n")
                f.write(f"Datei: {original_filename}\n")
        
        finally:
            # PST-Datei schließen
            if pst:
                try:
                    pst.close()
                except Exception:
                    pass
        
        # ZIP-Datei erstellen
        import zipfile
        print(f"Erstelle ZIP-Datei: {zip_path}")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(out_dir):
                for file_name in files:
                    file_path = os.path.join(root, file_name)
                    rel_path = os.path.relpath(file_path, out_dir)
                    zipf.write(file_path, rel_path)
        
        # Ergebnis zurückgeben
        if os.path.exists(zip_path):
            zip_size = os.path.getsize(zip_path)
            return {
                "success": True,
                "message": f"Kalenderexport erfolgreich. {calendar_count} Kalendereinträge gefunden.",
                "file_path": f"/data/ost/{zip_filename}",
                "file_size": zip_size,
                "calendar_count": calendar_count,
                "total_messages": total_msg_count,
                "download_url": f"/download/{zip_filename}"
            }
        else:
            return {
                "success": False,
                "message": "Fehler beim Erstellen der ZIP-Datei"
            }
    
    except Exception as e:
        # Allgemeiner Fehler
        error_msg = str(e)
        print(f"Unerwarteter Fehler: {error_msg}")
        return {
            "success": False,
            "message": f"Fehler beim Export: {error_msg}"
        }
    
    finally:
        # Temporäres Verzeichnis aufräumen
        try:
            if os.path.exists(work_dir):
                shutil.rmtree(work_dir)
        except Exception as e:
            print(f"Fehler beim Aufräumen: {str(e)}")
    pass

async def export_calendar_debug(
    file: UploadFile = File(...),
    extended: bool = Form(False),
    debug_mode: bool = Form(True)  # Aktiviert das Debugging
):
    """
    Exportiert Kalendereinträge mit zusätzlichen Debugging-Informationen.
    
    Parameters:
    - file: PST/OST-Datei
    - extended: Falls true, werden zusätzliche MAPI-Eigenschaften extrahiert
    - debug_mode: Speichert zusätzliche Debugging-Informationen
    """
    # Original-Dateinamen speichern und säubern
    original_filename = file.filename
    safe_filename = ''.join(c for c in original_filename if c.isalnum() or c in '._-')
    
    # Aktuelles Datum/Uhrzeit für eindeutige Dateinamen
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Permanentes Datenverzeichnis (das gemounted ist)
    data_dir = "/data/ost"
    
    # Temporäres Verzeichnis für die Verarbeitung
    work_dir = os.path.join(data_dir, f"caldbg_{timestamp}_{safe_filename}")
    os.makedirs(work_dir, exist_ok=True)
    
    # Pfade definieren
    in_path = os.path.join(work_dir, "input.pst")
    out_dir = os.path.join(work_dir, "output")
    os.makedirs(out_dir, exist_ok=True)
    cal_dir = os.path.join(out_dir, "calendar")
    os.makedirs(cal_dir, exist_ok=True)
    debug_dir = os.path.join(out_dir, "debug")
    os.makedirs(debug_dir, exist_ok=True)
    
    # Zielpfad für das ZIP-File im /data/ost Verzeichnis
    zip_filename = f"caldbg_{timestamp}_{safe_filename}.zip"
    zip_path = os.path.join(data_dir, zip_filename)
    
    # Dictionary mit Properties kombinieren je nach extended Flag
    properties_to_check = CALENDAR_PROPS.copy()
    if extended:
        properties_to_check.update(EXTENDED_PROPS)
    
    # Debug-Sammler
    debug_info = {
        "message_classes": set(),
        "calendar_like_items": [],
        "item_stats": {},
        "errors": []
    }
    
    try:
        # PST/OST-Datei in Chunks speichern
        with open(in_path, "wb") as f:
            chunk_size = 1024 * 1024  # 1MB pro Chunk
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
        
        print(f"Datei {original_filename} erfolgreich gespeichert als {in_path}")
        
        # Datei mit pypff öffnen
        pst = None
        try:
            pst = pypff.file()
            pst.open(in_path)
            root_folder = pst.get_root_folder()
            
            # Infotext erstellen
            with open(os.path.join(out_dir, "info.txt"), "w") as f:
                f.write(f"Kalenderexport (Debug) aus PST-Datei: {original_filename}\n")
                f.write(f"Export-Datum: {datetime.now().isoformat()}\n")
                f.write(f"Anzahl Root-Ordner: {root_folder.number_of_sub_folders}\n")
                f.write(f"Nachrichten im Root: {root_folder.number_of_sub_messages}\n")
            
            # Kalendereinträge zählen
            calendar_count = 0
            total_msg_count = 0
            
            # Diese Funktion extrahiert die Eigenschaften einer Nachricht
            def extract_all_properties(msg):
                """Extrahiert alle verfügbaren Eigenschaften einer Nachricht"""
                props = {}
                
                # Versuchen, property_values zu bekommen (moderne API)
                if hasattr(msg, "property_values"):
                    # Alle Properties durchgehen
                    for prop_id, value in msg.property_values.items():
                        prop_name = f"0x{prop_id:04X}"  # Hex-Format für unbekannte IDs
                        
                        # Bereinigen und konvertieren
                        if value is not None:
                            if isinstance(value, bytes):
                                try:
                                    # Für Datumswerte
                                    if prop_id in [0x8004, 0x8005, 0x003D, 0x0023, 0x8502]:
                                        if b":" in value and b"-" in value:  # ISO-Datum
                                            value = value.decode('utf-8', errors='ignore').strip('\x00')
                                        else:
                                            value = value.hex()
                                    else:
                                        # Standardkonvertierung
                                        value = value.decode('utf-8', errors='ignore').strip('\x00')
                                except Exception:
                                    value = value.hex()
                            props[prop_name] = value
                
                # Ältere API-Methode
                elif hasattr(msg, "get_number_of_properties"):
                    try:
                        for i in range(msg.get_number_of_properties()):
                            try:
                                prop_id = msg.get_property_tag(i)
                                value = msg.get_property_data(prop_id)
                                
                                prop_name = f"0x{prop_id & 0xFFFF:04X}"  # Hex-Format
                                
                                # Bereinigen und konvertieren
                                if value is not None:
                                    if isinstance(value, bytes):
                                        try:
                                            value = value.decode('utf-8', errors='ignore').strip('\x00')
                                        except Exception:
                                            value = value.hex()
                                    props[prop_name] = value
                            except Exception as e:
                                print(f"Fehler bei Property {i}: {str(e)}")
                    except Exception as e:
                        print(f"Fehler beim Zugriff auf Properties: {str(e)}")
                
                return props
            
            # Diese Funktion extrahiert die Eigenschaften einer Nachricht mit Fokus auf Kalendereigenschaften
            def extract_properties(msg):
                props = {}
                
                # Nachrichtenklasse zuerst ermitteln
                msg_class = None
                try:
                    if hasattr(msg, "get_message_class"):
                        msg_class = msg.get_message_class()
                    elif hasattr(msg, "property_values") and 0x001A in msg.property_values:
                        msg_class = msg.property_values[0x001A]
                    elif hasattr(msg, "get_property_data"):
                        msg_class = msg.get_property_data(0x001A)
                        
                    # String-Konvertierung
                    if isinstance(msg_class, bytes):
                        msg_class = msg_class.decode('utf-8', errors='ignore')
                    else:
                        msg_class = str(msg_class or "Unknown")
                except Exception as e:
                    msg_class = f"Error getting class: {str(e)}"
                
                props["Message Class"] = msg_class
                
                # Für Debug-Zwecke die Nachrichtenklasse speichern
                debug_info["message_classes"].add(msg_class)
                
                # Alle relevanten Eigenschaften durchgehen
                for prop_id, prop_name in properties_to_check.items():
                    try:
                        # Wert über verschiedene Methoden extrahieren
                        value = None
                        if hasattr(msg, "property_values") and prop_id in msg.property_values:
                            value = msg.property_values[prop_id]
                        elif hasattr(msg, "get_property_data"):
                            try:
                                value = msg.get_property_data(prop_id)
                            except:
                                pass
                        
                        # Bereinigen und konvertieren
                        if value is not None:
                            if isinstance(value, bytes):
                                try:
                                    # Für Datum/Zeitwerte
                                    if prop_id in [0x8004, 0x8005, 0x003D, 0x0023, 0x8502]:
                                        # Versuchen, als Datumsstring zu interpretieren
                                        if b":" in value and b"-" in value:  # ISO-Datum
                                            value = value.decode('utf-8', errors='ignore').strip('\x00')
                                        else:
                                            # Binäres Datum - als HEX ausgeben
                                            value = value.hex()
                                    else:
                                        # Standardkonvertierung für Strings
                                        value = value.decode('utf-8', errors='ignore').strip('\x00')
                                except Exception:
                                    # Fallback auf Hex-Darstellung
                                    value = value.hex()
                            props[prop_name] = value
                    except Exception as e:
                        print(f"Fehler beim Extrahieren von {prop_name}: {str(e)}")
                
                return props, msg_class
            
            # Diese Funktion exportiert rekursiv alle Kalendereinträge aus einem Ordner
            def export_calendar_items(folder, folder_path):
                nonlocal calendar_count, total_msg_count
                
                # Ordnernamen für den Pfad extrahieren und bereinigen
                folder_name = folder.name or "Unnamed"
                safe_name = ''.join(c for c in folder_name if c.isalnum() or c in ' ._-')
                current_path = os.path.join(folder_path, safe_name)
                
                # Ist es ein Kalenderordner?
                is_calendar_folder = ("Calendar" in folder_name or "Kalender" in folder_name)
                
                # Speziellen Kalenderordner für mögliche Kalendereinträge erstellen
                if is_calendar_folder:
                    calendar_folder_path = os.path.join(cal_dir, safe_name)
                    os.makedirs(calendar_folder_path, exist_ok=True)
                    
                    # Info über den Kalenderordner schreiben
                    with open(os.path.join(calendar_folder_path, "_calendar_info.txt"), "w") as f:
                        f.write(f"Kalenderordner: {folder_name}\n")
                        f.write(f"Anzahl Elemente: {folder.number_of_sub_messages}\n")
                        f.write(f"Pfad: {folder_path}/{safe_name}\n")
                else:
                    # Kein Kalenderordner, aber trotzdem nach Kalendereinträgen suchen
                    calendar_folder_path = os.path.join(out_dir, "non_calendar_items")
                    os.makedirs(calendar_folder_path, exist_ok=True)
                
                # Alle Nachrichten im Ordner durchgehen
                for i in range(folder.number_of_sub_messages):
                    total_msg_count += 1
                    try:
                        msg = folder.get_sub_message(i)
                        
                        # Eigenschaften extrahieren
                        props, msg_class = extract_properties(msg)
                        
                        # Für Debug-Zwecke alle Eigenschaften extrahieren
                        if debug_mode:
                            all_props = extract_all_properties(msg)
                        
                        # Erweiterter Check auf Kalendereintrag
                        is_calendar_item = False
                        calendar_indicators = [
                            # Standard-Klassen
                            "IPM.Appointment" in msg_class,
                            "IPM.Schedule.Meeting" in msg_class,
                            "IPM.OLE.CLASS.{00061055-0000-0000-C000-000000000046}" in msg_class,
                            # Weitere Indikatoren
                            "Start Time" in props and "End Time" in props,  # Hat Start/End-Zeit
                            is_calendar_folder,  # Liegt in einem Kalenderordner
                            "Location" in props,  # Hat Ortsangabe
                            "All Day Event" in props,  # Hat All-Day-Flag
                            "Appointment" in msg_class  # "Appointment" im Klassennamen
                        ]
                        
                        # Wenn irgendein Indikator zutrifft, als Kalendereintrag behandeln
                        is_calendar_item = any(calendar_indicators)
                        
                        # Für Debug-Zwecke bei potenziellen Kalendereinträgen
                        if not is_calendar_item and is_calendar_folder:
                            # Wenn im Kalenderordner, aber nicht als Kalendereintrag erkannt
                            debug_info["calendar_like_items"].append({
                                "message_class": msg_class,
                                "path": f"{folder_path}/{safe_name}",
                                "index": i,
                                "properties": props,
                                "all_properties": all_props if debug_mode else None
                            })
                        
                        # Statistik für den Nachrichtentyp
                        if msg_class not in debug_info["item_stats"]:
                            debug_info["item_stats"][msg_class] = 0
                        debug_info["item_stats"][msg_class] += 1
                        
                        # Nachricht exportieren (für alle Nachrichten im Debug-Modus)
                        if debug_mode or is_calendar_item:
                            calendar_count += 1 if is_calendar_item else 0
                            
                            # Betreff und Datum für den Dateinamen extrahieren
                            subject = props.get("Subject", f"NoSubject_{i}")
                            safe_subject = ''.join(c for c in subject if c.isalnum() or c in ' ._-')
                            safe_subject = safe_subject[:50]  # Längenbegrenzung
                            
                            # Start-Zeit extrahieren für den Dateinamen
                            start_time = props.get("Start Time", "")
                            if start_time:
                                try:
                                    if isinstance(start_time, str) and "T" in start_time:
                                        date_part = start_time.split("T")[0]
                                        safe_subject = f"{date_part}_{safe_subject}"
                                except Exception:
                                    pass
                            
                            # Speicherort festlegen
                            if is_calendar_item:
                                # Kalendereinträge in den Kalenderordner
                                save_path = calendar_folder_path
                            else:
                                # Andere Nachrichten in den Debug-Ordner
                                save_path = os.path.join(debug_dir, safe_name)
                            
                            os.makedirs(save_path, exist_ok=True)
                            
                            # Datei-Präfix je nach Typ
                            file_prefix = "calendar" if is_calendar_item else "msg"
                            
                            # Nachricht als Text speichern
                            msg_file = os.path.join(save_path, f"{file_prefix}_{i}_{safe_subject}.txt")
                            with open(msg_file, "w", encoding="utf-8") as f:
                                # Header
                                f.write(f"{'KALENDEREINTRAG' if is_calendar_item else 'NACHRICHT'} #{i}\n")
                                f.write(f"{'='*50}\n")
                                
                                # Stammdaten
                                f.write(f"Message Class: {msg_class}\n")
                                f.write(f"Item Index: {i}\n")
                                f.write(f"Folder: {folder_name}\n")
                                f.write(f"Path: {folder_path}/{safe_name}\n")
                                f.write(f"Calendar Item: {'Ja' if is_calendar_item else 'Nein'}\n\n")
                                
                                # Wichtige Attribute in einer bestimmten Reihenfolge anzeigen
                                for key in ["Subject", "Start Time", "End Time", "Location", "Body", "Display To"]:
                                    if key in props:
                                        f.write(f"{key}: {props[key]}\n")
                                
                                f.write(f"\nALLE EXTRAHIERTEN EIGENSCHAFTEN:\n")
                                f.write(f"{'-'*50}\n")
                                
                                # Alle anderen Eigenschaften sortiert ausgeben
                                for key, value in sorted(props.items()):
                                    if key not in ["Subject", "Start Time", "End Time", "Location", "Body", "Display To"]:
                                        f.write(f"{key}: {value}\n")
                                
                                # Im Debug-Modus auch alle rohen Eigenschaften ausgeben
                                if debug_mode:
                                    f.write(f"\nROHE EIGENSCHAFTEN (ALLE IDs):\n")
                                    f.write(f"{'-'*50}\n")
                                    
                                    for key, value in sorted(all_props.items()):
                                        f.write(f"{key}: {value}\n")
                    except Exception as msg_error:
                        # Fehler bei einzelnen Nachrichten protokollieren
                        error_msg = str(msg_error)
                        print(f"Fehler bei Nachricht {i}: {error_msg}")
                        debug_info["errors"].append(f"Fehler bei Nachricht {i} in {folder_path}/{safe_name}: {error_msg}")
                
                # Unterordner rekursiv durchsuchen
                for i in range(folder.number_of_sub_folders):
                    try:
                        sub_folder = folder.get_sub_folder(i)
                        export_calendar_items(sub_folder, current_path)
                    except Exception as folder_error:
                        error_msg = str(folder_error)
                        print(f"Fehler bei Unterordner {i}: {error_msg}")
                        debug_info["errors"].append(f"Fehler bei Unterordner {i} in {folder_path}/{safe_name}: {error_msg}")
            
            # Export starten
            export_calendar_items(root_folder, out_dir)
            
            # Debug-Informationen speichern
            if debug_mode:
                # Nachrichtenklassen
                with open(os.path.join(debug_dir, "message_classes.txt"), "w") as f:
                    f.write("GEFUNDENE NACHRICHTENKLASSEN:\n")
                    f.write("=" * 50 + "\n")
                    for cls in sorted(debug_info["message_classes"]):
                        count = debug_info["item_stats"].get(cls, 0)
                        f.write(f"{cls}: {count} Vorkommen\n")
                
                # Nicht erkannte Kalenderelemente
                with open(os.path.join(debug_dir, "calendar_like_items.txt"), "w") as f:
                    f.write("POTENZIELLE KALENDEREINTRÄGE, DIE NICHT ERKANNT WURDEN:\n")
                    f.write("=" * 50 + "\n")
                    for item in debug_info["calendar_like_items"]:
                        f.write(f"Nachrichtenklasse: {item['message_class']}\n")
                        f.write(f"Pfad: {item['path']}\n")
                        f.write(f"Index: {item['index']}\n")
                        f.write(f"Eigenschaften:\n")
                        for k, v in item['properties'].items():
                            f.write(f"  {k}: {v}\n")
                        f.write("-" * 50 + "\n")
                
                # Fehler
                with open(os.path.join(debug_dir, "errors.txt"), "w") as f:
                    f.write("FEHLER WÄHREND DES EXPORTS:\n")
                    f.write("=" * 50 + "\n")
                    for error in debug_info["errors"]:
                        f.write(f"{error}\n")
            
            # Zusammenfassung erstellen
            with open(os.path.join(out_dir, "calendar_summary.txt"), "w") as f:
                f.write(f"Kalenderexport abgeschlossen\n")
                f.write(f"Gefundene Kalendereinträge: {calendar_count}\n")
                f.write(f"Gesamtzahl der Nachrichten: {total_msg_count}\n")
                f.write(f"Erweiterte Eigenschaften: {'Ja' if extended else 'Nein'}\n")
                f.write(f"Debug-Modus: {'Ja' if debug_mode else 'Nein'}\n")
                f.write(f"Export-Ende: {datetime.now().isoformat()}\n")
        
        except Exception as pff_error:
            # Fehler protokollieren
            error_msg = str(pff_error)
            print(f"Fehler beim Verarbeiten der PST-Datei: {error_msg}")
            with open(os.path.join(out_dir, "error.txt"), "w") as f:
                f.write(f"Fehler beim Verarbeiten der PST-Datei: {error_msg}\n")
                f.write(f"Datei: {original_filename}\n")
        
        finally:
            # PST-Datei schließen
            if pst:
                try:
                    pst.close()
                except Exception:
                    pass
        
        # ZIP-Datei erstellen
        import zipfile
        print(f"Erstelle ZIP-Datei: {zip_path}")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(out_dir):
                for file_name in files:
                    file_path = os.path.join(root, file_name)
                    rel_path = os.path.relpath(file_path, out_dir)
                    zipf.write(file_path, rel_path)
        
        # Ergebnis zurückgeben
        if os.path.exists(zip_path):
            zip_size = os.path.getsize(zip_path)
            return {
                "success": True,
                "message": f"Kalenderexport (Debug) erfolgreich. {calendar_count} Kalendereinträge gefunden.",
                "file_path": f"/data/ost/{zip_filename}",
                "file_size": zip_size,
                "calendar_count": calendar_count,
                "total_messages": total_msg_count,
                "message_classes_count": len(debug_info["message_classes"]),
                "download_url": f"/download/{zip_filename}"
            }
        else:
            return {
                "success": False,
                "message": "Fehler beim Erstellen der ZIP-Datei"
            }
    
    except Exception as e:
        # Allgemeiner Fehler
        error_msg = str(e)
        print(f"Unerwarteter Fehler: {error_msg}")
        return {
            "success": False,
            "message": f"Fehler beim Export: {error_msg}"
        }
    
    finally:
        # Temporäres Verzeichnis aufräumen
        try:
            if os.path.exists(work_dir):
                shutil.rmtree(work_dir)
        except Exception as e:
            print(f"Fehler beim Aufräumen: {str(e)}")
    pass

async def advanced_calendar_extraction(
    file: UploadFile = File(...),
    folder_path: str = Form(""),  # Optionaler spezifischer Kalenderpfad
    export_format: str = Form("json"),  # Format: json oder text
    use_extended_props: bool = Form(True)  # Erweiterte Eigenschaftssuche aktivieren
):
    """
    Erweiterter Kalenderexport mit verbesserten Methoden zur Eigenschaftsextraktion
    
    Parameters:
    - file: PST/OST-Datei
    - folder_path: Optionaler Pfad zum Kalenderordner (leer = automatische Suche)
    - export_format: Ausgabeformat (json oder text)
    - use_extended_props: Aktiviert die erweiterte Suche nach Kalendereigenschaften
    """
    # Original-Dateinamen speichern und säubern
    original_filename = file.filename
    safe_filename = ''.join(c for c in original_filename if c.isalnum() or c in '._-')
    
    # Aktuelles Datum/Uhrzeit für eindeutige Dateinamen
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Datenverzeichnis
    data_dir = "/data/ost"
    
    # Arbeitsverzeichnis
    work_dir = os.path.join(data_dir, f"adv_cal_{timestamp}_{safe_filename}")
    os.makedirs(work_dir, exist_ok=True)
    
    # Pfade definieren
    in_path = os.path.join(work_dir, "input.pst")
    out_dir = os.path.join(work_dir, "output")
    os.makedirs(out_dir, exist_ok=True)
    
    # ZIP-Dateiname
    zip_filename = f"advanced_calendar_{timestamp}_{safe_filename}.zip"
    zip_path = os.path.join(data_dir, zip_filename)
    
    # -------------------------------------------------------------------------
    # 1. ERWEITERTE EIGENSCHAFTSZUORDNUNGEN FÜR KALENDERELEMENTE
    # -------------------------------------------------------------------------
    
   
    
    # Kombinierte Eigenschaftsliste basierend auf use_extended_props
    property_map = STANDARD_CAL_PROPS.copy()
    if use_extended_props:
        property_map.update(EXTENDED_CAL_PROPS)
    
    # -------------------------------------------------------------------------
    # 2. HILFSFUNKTIONEN FÜR ERWEITERTE EIGENSCHAFTSABFRAGE
    # -------------------------------------------------------------------------
    
    def get_property_value(msg, prop_id, property_name=None):
        """
        Versucht, den Wert einer Eigenschaft mit mehreren Methoden zu erhalten.
        
        Args:
            msg: Die Nachricht (pypff-Objekt)
            prop_id: Property-ID (int oder hex-string)
            property_name: Optionaler Name für Debug-Ausgaben
            
        Returns:
            Der Wert der Eigenschaft oder None, wenn nicht gefunden
        """
        value = None
        debug_info = []
        
        try:
            # Property-ID konvertieren, falls nötig
            if isinstance(prop_id, str):
                if prop_id.startswith("0x"):
                    prop_id = int(prop_id, 16)
                else:
                    prop_id = int(prop_id)
            
            # Methode 1: Über property_values dict (moderne API)
            if hasattr(msg, "property_values") and prop_id in msg.property_values:
                value = msg.property_values[prop_id]
                debug_info.append(f"Gefunden über property_values[{prop_id}]")
            
            # Methode 2: Über get_property_value (falls vorhanden)
            elif hasattr(msg, "get_property_value"):
                try:
                    value = msg.get_property_value(prop_id)
                    if value is not None:
                        debug_info.append(f"Gefunden über get_property_value({prop_id})")
                except Exception as e:
                    debug_info.append(f"get_property_value Fehler: {str(e)}")
            
            # Methode 3: Über get_property_data (ältere API)
            elif hasattr(msg, "get_property_data"):
                try:
                    value = msg.get_property_data(prop_id)
                    if value is not None:
                        debug_info.append(f"Gefunden über get_property_data({prop_id})")
                except Exception as e:
                    debug_info.append(f"get_property_data Fehler: {str(e)}")
            
            # Bereinigen und Konvertieren des Wertes
            if value is not None:
                if isinstance(value, bytes):
                    # Verarbeitung für verschiedene Eigenschaftstypen
                    try:
                        # Für Datums-/Zeitwerte
                        if prop_id in [0x8004, 0x8005, 0x003D, 0x0023, 0x8502, 
                                    0x00430102, 0x00440102, 0x0002, 0x0003, 
                                    0x0060, 0x0061, 0x82000102, 0x82010102]:
                            # Versuchen als ISO-Datum zu dekodieren
                            if b":" in value and b"-" in value:
                                value = value.decode('utf-8', errors='ignore').strip('\x00')
                                debug_info.append("Als ISO-Datum dekodiert")
                            else:
                                # Falls binäres Format, umwandeln
                                # TODO: Korrekte Datumskonvertierung 
                                # von binärem FILETIME Format hinzufügen
                                value = f"Binäres Datum: {value.hex()}"
                                debug_info.append("Binäres Datum als Hex")
                        else:
                            # Standard-Stringkonvertierung für Text
                            value = value.decode('utf-8', errors='ignore').strip('\x00')
                            debug_info.append("Als UTF-8 String dekodiert")
                    except Exception as e:
                        value = f"Binäre Daten: {value.hex()}"
                        debug_info.append(f"Konvertierungsfehler: {str(e)}")
            
            # Debug-Informationen
            if property_name and debug_info:
                print(f"Property {property_name} (ID 0x{prop_id:X}): {', '.join(debug_info)}")
                
            return value
            
        except Exception as e:
            print(f"Fehler beim Zugriff auf Property 0x{prop_id:X}: {str(e)}")
            return None
    
    def extract_all_properties(msg):
        """
        Extrahiert alle verfügbaren Eigenschaften einer Nachricht.
        
        Args:
            msg: Die Nachricht (pypff-Objekt)
            
        Returns:
            Ein Dictionary mit allen gefundenen Eigenschaften
        """
        all_props = {}
        
        # Methode 1: Über property_values (moderne API)
        if hasattr(msg, "property_values"):
            for prop_id, value in msg.property_values.items():
                prop_name = f"0x{prop_id:04X}"
                
                # Wert konvertieren
                if isinstance(value, bytes):
                    try:
                        # Spezialbehandlung für bekannte Datumsfelder
                        if prop_id in [0x8004, 0x8005, 0x003D, 0x0023]:
                            if b":" in value and b"-" in value:
                                value = value.decode('utf-8', errors='ignore').strip('\x00')
                            else:
                                value = f"Binäres Datum: {value.hex()}"
                        else:
                            # Normale Textkonvertierung
                            value = value.decode('utf-8', errors='ignore').strip('\x00')
                    except Exception:
                        value = f"Binäre Daten ({len(value)} Bytes): {value.hex()[:60]}..."
                
                all_props[prop_name] = value
        
        # Methode 2: Über get_number_of_properties (ältere API)
        elif hasattr(msg, "get_number_of_properties"):
            try:
                num_props = msg.get_number_of_properties()
                
                for i in range(num_props):
                    try:
                        prop_type = msg.get_property_type(i)
                        prop_tag = msg.get_property_tag(i)
                        prop_name = f"0x{prop_tag:04X}"
                        
                        # Wert abrufen
                        try:
                            value = msg.get_property_data(prop_tag)
                            
                            # Wert konvertieren
                            if isinstance(value, bytes):
                                try:
                                    # Spezialbehandlung für bekannte Datumsfelder
                                    if prop_tag in [0x8004, 0x8005, 0x003D, 0x0023]:
                                        if b":" in value and b"-" in value:
                                            value = value.decode('utf-8', errors='ignore').strip('\x00')
                                        else:
                                            value = f"Binäres Datum: {value.hex()}"
                                    else:
                                        # Normale Textkonvertierung
                                        value = value.decode('utf-8', errors='ignore').strip('\x00')
                                except Exception:
                                    value = f"Binäre Daten ({len(value)} Bytes): {value.hex()[:60]}..."
                                
                            all_props[prop_name] = value
                        except Exception as e:
                            all_props[prop_name] = f"Fehler beim Abrufen des Werts: {str(e)}"
                    except Exception as e:
                        print(f"Fehler bei Property {i}: {str(e)}")
            except Exception as e:
                print(f"Fehler beim Zugriff auf Properties: {str(e)}")
        
        return all_props
    
    def get_calendar_properties(msg):
        """
        Extrahiert alle für Kalendereinträge relevanten Eigenschaften mit erweiterten Methoden.
        
        Args:
            msg: Die Nachricht (pypff-Objekt)
            
        Returns:
            Ein Dictionary mit den Eigenschaften des Kalendereintrags
        """
        calendar_data = {
            "raw_props": {},  # Alle rohen Eigenschaften
            "properties": {}  # Geordnete und bereinigte Eigenschaften
        }
        
        # Zuerst alle Eigenschaften extrahieren - für Debugging und Redundanz
        raw_props = extract_all_properties(msg)
        calendar_data["raw_props"] = raw_props
        
        # Nachrichtenklasse bestimmen
        msg_class = None
        for prop_id in [0x001A, 0x001A001F]:
            value = get_property_value(msg, prop_id)
            if value:
                msg_class = value
                break
        
        if not msg_class:
            msg_class = "Unknown"
        
        calendar_data["properties"]["MessageClass"] = msg_class
        
        # Kernfelder mit Fallback-Optionen extrahieren
        # 1. Betreff
        subject = None
        for prop_id in [0x0037, 0x0037001F, 0x0E1D, 0x0070]:
            value = get_property_value(msg, prop_id)
            if value:
                subject = value
                calendar_data["properties"]["Subject"] = value
                break
        
        # 2. Startzeit - mehrere mögliche Property-IDs probieren
        for prop_id in [0x8004, 0x00430102, 0x0002, 0x0060, 0x82000102, 0x82050102]:
            value = get_property_value(msg, prop_id)
            if value:
                calendar_data["properties"]["StartTime"] = value
                break
        
        # 3. Endzeit - mehrere mögliche Property-IDs probieren
        for prop_id in [0x8005, 0x00440102, 0x0003, 0x0061, 0x82010102, 0x82060102]:
            value = get_property_value(msg, prop_id)
            if value:
                calendar_data["properties"]["EndTime"] = value
                break
        
        # 4. Ort - mehrere mögliche Property-IDs probieren
        for prop_id in [0x0024, 0x0094, 0x8208]:
            value = get_property_value(msg, prop_id)
            if value:
                calendar_data["properties"]["Location"] = value
                break
        
        # 5. Textkörper - versuche mehrere Formate
        body = None
        
        # Plain Text
        for prop_id in [0x1000, 0x1000001F]:
            value = get_property_value(msg, prop_id)
            if value:
                body = value
                calendar_data["properties"]["Body"] = value
                break
        
        # HTML (falls kein Plain Text gefunden wurde oder zusätzlich)
        for prop_id in [0x0FFF, 0x1013, 0x1014]:
            value = get_property_value(msg, prop_id)
            if value:
                calendar_data["properties"]["HtmlBody"] = value
                # Falls noch kein Body gefunden wurde, HTML als Fallback verwenden
                if "Body" not in calendar_data["properties"]:
                    # HTML-Tags entfernen für eine einfache Textdarstellung
                    text_body = re.sub(r'<[^>]+>', ' ', value)
                    text_body = re.sub(r'\s+', ' ', text_body).strip()
                    calendar_data["properties"]["Body"] = text_body
                break
        
        # RTF Compressed (als letzter Versuch)
        rtf_value = get_property_value(msg, 0x1009)
        if rtf_value and "Body" not in calendar_data["properties"]:
            calendar_data["properties"]["RtfCompressed"] = "RTF data available (binary)"
        
        # 6. Teilnehmer 
        for prop_id in [0x0E04, 0x0E04001F]:
            value = get_property_value(msg, prop_id)
            if value:
                calendar_data["properties"]["DisplayTo"] = value
                break
        
        # 7. Organisator-Informationen
        for prop_id in [0x0042, 0x0081, 0x001F]:
            value = get_property_value(msg, prop_id)
            if value:
                calendar_data["properties"]["Organizer"] = value
                break
        
        # 8. Wichtige Flags
        # Ganztägiges Ereignis
        all_day = get_property_value(msg, 0x8216)
        if all_day is not None:
            calendar_data["properties"]["AllDayEvent"] = all_day
        
        # Erinnerung gesetzt
        reminder_set = get_property_value(msg, 0x8501)
        if reminder_set is not None:
            calendar_data["properties"]["ReminderSet"] = reminder_set
        
        # Erinnerungszeit
        reminder_minutes = get_property_value(msg, 0x0065)
        if reminder_minutes is not None:
            calendar_data["properties"]["ReminderMinutesBeforeStart"] = reminder_minutes
        
        # Wiederholung
        is_recurring = get_property_value(msg, 0x8201)
        if is_recurring is not None:
            calendar_data["properties"]["IsRecurring"] = is_recurring
        
        # Wiederholungsmuster
        recurrence_pattern = get_property_value(msg, 0x8582)
        if recurrence_pattern:
            calendar_data["properties"]["RecurrencePattern"] = recurrence_pattern
        
        # 9. Weitere wichtige Eigenschaften hinzufügen, wenn vorhanden
        for prop_name, prop_id in property_map.items():
            # Überspringen von bereits verarbeiteten Kernfeldern
            if (prop_name in calendar_data["properties"] or 
                prop_name.endswith("_Alt") or 
                prop_name.endswith("_Alt1") or 
                prop_name.endswith("_Alt2") or
                prop_name.endswith("_Alt3") or
                prop_name.endswith("_Named") or
                prop_name.endswith("Unicode")):
                continue
                
            value = get_property_value(msg, prop_id)
            if value is not None:
                calendar_data["properties"][prop_name] = value
        
        # Ist dies wirklich ein Kalendereintrag?
        is_calendar = (
            "IPM.Appointment" in msg_class or
            "IPM.Schedule.Meeting" in msg_class or
            "calendar" in msg_class.lower() or
            "appointment" in msg_class.lower() or
            "meeting" in msg_class.lower() or
            "{00061055-0000-0000-C000-000000000046}" in msg_class
        )
        
        # Alternative Erkennung über vorhandene Kalendereigenschaften
        if not is_calendar:
            calendar_indicators = [
                "StartTime" in calendar_data["properties"],
                "EndTime" in calendar_data["properties"],
                "AllDayEvent" in calendar_data["properties"],
                "Location" in calendar_data["properties"] and "Body" in calendar_data["properties"],
                "ReminderSet" in calendar_data["properties"],
                # Weitere spezifische Indikatoren können hier hinzugefügt werden
            ]
            
            is_calendar = any(calendar_indicators)
        
        calendar_data["is_calendar_item"] = is_calendar
        
        return calendar_data
    
    # -------------------------------------------------------------------------
    # 3. HILFSFUNKTION ZUM AUFFINDEN VON KALENDERORDNERN
    # -------------------------------------------------------------------------
    
    def find_calendar_folders(folder, path="", results=None):
        """
        Findet alle Kalenderordner in der PST-Datei.
        
        Args:
            folder: Der aktuelle Ordner
            path: Der Pfad zum aktuellen Ordner
            results: Liste der gefundenen Kalenderordner
            
        Returns:
            Liste der gefundenen Kalenderordner mit Pfaden
        """
        if results is None:
            results = []
            
        folder_name = folder.name or "Unnamed"
        current_path = f"{path}/{folder_name}" if path else f"/{folder_name}"
        
        # Prüfen, ob es ein Kalenderordner ist
        is_calendar_folder = (
            "Calendar" in folder_name or 
            "Kalender" in folder_name or
            "calendar" in folder_name.lower()
        )
        
        if is_calendar_folder:
            results.append({
                "name": folder_name,
                "path": current_path,
                "folder": folder,
                "message_count": folder.number_of_sub_messages
            })
        
        # Rekursiv Unterordner durchsuchen
        for i in range(folder.number_of_sub_folders):
            try:
                sub_folder = folder.get_sub_folder(i)
                find_calendar_folders(sub_folder, current_path, results)
            except Exception as e:
                print(f"Fehler beim Durchsuchen von Unterordner {i} in {current_path}: {str(e)}")
        
        return results
    
    # -------------------------------------------------------------------------
    # 4. FUNKTION ZUM FINDEN EINES ORDNERS ANHAND EINES PFADES
    # -------------------------------------------------------------------------
    
    def find_folder_by_path(root_folder, target_path):
        """
        Findet einen Ordner anhand seines Pfades.
        
        Args:
            root_folder: Der Root-Ordner
            target_path: Der Pfad zum gesuchten Ordner
            
        Returns:
            Der gefundene Ordner oder None
        """
        if not target_path or target_path == "/" or target_path == "":
            return root_folder
            
        # Pfadteile extrahieren
        parts = [p for p in target_path.split("/") if p]
        current = root_folder
        
        for part in parts:
            found = False
            # Unterordner durchsuchen
            for i in range(current.number_of_sub_folders):
                sub_folder = current.get_sub_folder(i)
                sub_name = sub_folder.name or "Unnamed"
                
                if sub_name.lower() == part.lower():
                    current = sub_folder
                    found = True
                    break
            
            if not found:
                return None
        
        return current
    
    # -------------------------------------------------------------------------
    # 5. HAUPTEXPORTFUNKTION
    # -------------------------------------------------------------------------
    
    try:
        # PST/OST-Datei in Chunks speichern
        with open(in_path, "wb") as f:
            chunk_size = 1024 * 1024  # 1MB pro Chunk
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
        
        print(f"Datei {original_filename} erfolgreich gespeichert als {in_path}")
        
        # PST öffnen
        pst = None
        calendar_entries = []
        calendar_folders = []
        total_messages = 0
        calendar_count = 0
        errors = []
        
        try:
            pst = pypff.file()
            pst.open(in_path)
            root_folder = pst.get_root_folder()
            
            # Info-Datei erstellen
            with open(os.path.join(out_dir, "info.txt"), "w") as f:
                f.write(f"Erweiterter Kalenderexport aus PST-Datei: {original_filename}\n")
                f.write(f"Export-Datum: {datetime.now().isoformat()}\n")
                f.write(f"Anzahl Root-Ordner: {root_folder.number_of_sub_folders}\n")
                f.write(f"Nachrichten im Root: {root_folder.number_of_sub_messages}\n")
            
            # Kalenderordner finden
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
                    raise ValueError(f"Ordner nicht gefunden: {folder_path}")
            else:
                # Automatische Suche nach Kalenderordnern
                calendar_folders = find_calendar_folders(root_folder)
            
            # Kalenderordner in Info-Datei dokumentieren
            with open(os.path.join(out_dir, "calendar_folders.txt"), "w") as f:
                f.write(f"Gefundene Kalenderordner: {len(calendar_folders)}\n")
                f.write("=" * 50 + "\n\n")
                
                for i, cal_folder in enumerate(calendar_folders):
                    f.write(f"Kalenderordner {i+1}:\n")
                    f.write(f"  Name: {cal_folder['name']}\n")
                    f.write(f"  Pfad: {cal_folder['path']}\n")
                    f.write(f"  Anzahl Nachrichten: {cal_folder['message_count']}\n\n")
            
            # Kalendereinträge extrahieren
            for folder_info in calendar_folders:
                folder = folder_info["folder"]
                folder_path = folder_info["path"]
                
                # Ordnerverzeichnis erstellen
                folder_dir = os.path.join(out_dir, f"folder_{folder_info['name']}")
                os.makedirs(folder_dir, exist_ok=True)
                
                print(f"Verarbeite Ordner: {folder_info['path']} mit {folder.number_of_sub_messages} Nachrichten")
                
                # Alle Nachrichten durchgehen
                for i in range(folder.number_of_sub_messages):
                    total_messages += 1
                    
                    try:
                        # Nachricht abrufen
                        msg = folder.get_sub_message(i)
                        
                        # Eigenschaften extrahieren mit erweiterter Methode
                        calendar_data = get_calendar_properties(msg)
                        
                        # Nur Kalendereinträge weiterverarbeiten
                        if calendar_data["is_calendar_item"]:
                            calendar_count += 1
                            
                            # Betreff für Dateinamen extrahieren
                            subject = calendar_data["properties"].get("Subject", f"Termin_{i}")
                            safe_subject = ''.join(c for c in subject if c.isalnum() or c in ' ._-')
                            safe_subject = safe_subject[:50]  # Längenbegrenzung
                            
                            # Startzeit für Dateinamen
                            start_time = calendar_data["properties"].get("StartTime", "")
                            if start_time:
                                try:
                                    # Versuchen, ein Datum aus ISO-Format zu extrahieren
                                    if isinstance(start_time, str) and "T" in start_time:
                                        date_part = start_time.split("T")[0]
                                        safe_subject = f"{date_part}_{safe_subject}"
                                except Exception:
                                    pass
                            
                            # Eintrag sowohl als JSON als auch als Text speichern
                            
                            # JSON-Format (für maschinelle Verarbeitung)
                            json_path = os.path.join(folder_dir, f"cal_{calendar_count}_{safe_subject}.json")
                            with open(json_path, "w", encoding="utf-8") as f:
                                import json
                                json.dump(calendar_data, f, indent=2, ensure_ascii=False)
                            
                            # Textformat (für menschliche Lesbarkeit)
                            text_path = os.path.join(folder_dir, f"cal_{calendar_count}_{safe_subject}.txt")
                            with open(text_path, "w", encoding="utf-8") as f:
                                # Header
                                f.write(f"KALENDEREINTRAG #{calendar_count}\n")
                                f.write("=" * 50 + "\n\n")
                                
                                # Kernfelder in bestimmter Reihenfolge
                                core_fields = ["Subject", "StartTime", "EndTime", "Location", "Organizer", 
                                              "DisplayTo", "Body", "IsRecurring", "RecurrencePattern"]
                                
                                for field in core_fields:
                                    if field in calendar_data["properties"]:
                                        value = calendar_data["properties"][field]
                                        if field == "Body" and value:
                                            f.write(f"{field}:\n{'-'*40}\n{value}\n{'-'*40}\n\n")
                                        else:
                                            f.write(f"{field}: {value}\n")
                                
                                # Weitere Felder
                                f.write("\nWEITERE EIGENSCHAFTEN:\n")
                                f.write("-" * 50 + "\n")
                                
                                for key, value in sorted(calendar_data["properties"].items()):
                                    if key not in core_fields:
                                        f.write(f"{key}: {value}\n")
                                
                                # Rohe Eigenschaften (für Debugging)
                                if use_extended_props:
                                    f.write("\nROHE EIGENSCHAFTEN:\n")
                                    f.write("-" * 50 + "\n")
                                    
                                    for key, value in sorted(calendar_data["raw_props"].items()):
                                        # Nur die ersten 100 Zeichen für lange Werte
                                        if isinstance(value, str) and len(value) > 100:
                                            value = value[:100] + "..."
                                        f.write(f"{key}: {value}\n")
                            
                            # Eintrag zur Liste hinzufügen
                            entry_summary = {
                                "id": calendar_count,
                                "subject": calendar_data["properties"].get("Subject", "Kein Betreff"),
                                "start_time": calendar_data["properties"].get("StartTime", "Keine Startzeit"),
                                "end_time": calendar_data["properties"].get("EndTime", "Keine Endzeit"),
                                "location": calendar_data["properties"].get("Location", "Kein Ort"),
                                "folder": folder_info["path"],
                                "index": i
                            }
                            
                            calendar_entries.append(entry_summary)
                            
                    except Exception as e:
                        error_msg = f"Fehler bei Nachricht {i} in {folder_info['path']}: {str(e)}"
                        print(error_msg)
                        errors.append(error_msg)
            
            # Erstelle eine Zusammenfassung aller Kalendereinträge
            summary_path = os.path.join(out_dir, "calendar_summary.json")
            with open(summary_path, "w", encoding="utf-8") as f:
                import json
                summary = {
                    "file": original_filename,
                    "export_date": datetime.now().isoformat(),
                    "total_messages": total_messages,
                    "calendar_count": calendar_count,
                    "calendar_folders": [{"name": f["name"], "path": f["path"], "message_count": f["message_count"]} 
                                        for f in calendar_folders],
                    "calendar_entries": calendar_entries,
                    "errors": errors
                }
                json.dump(summary, f, indent=2, ensure_ascii=False)
            
            # Erstelle eine menschenlesbare Übersicht
            overview_path = os.path.join(out_dir, "calendar_overview.txt")
            with open(overview_path, "w", encoding="utf-8") as f:
                f.write(f"KALENDEREXPORT ÜBERSICHT\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"Datei: {original_filename}\n")
                f.write(f"Exportdatum: {datetime.now().isoformat()}\n")
                f.write(f"Gesamtzahl der Nachrichten: {total_messages}\n")
                f.write(f"Gefundene Kalendereinträge: {calendar_count}\n")
                f.write(f"Anzahl Kalenderordner: {len(calendar_folders)}\n\n")
                
                f.write("KALENDERORDNER:\n")
                f.write("-" * 50 + "\n")
                for i, folder in enumerate(calendar_folders):
                    f.write(f"{i+1}. {folder['name']} ({folder['path']}): {folder['message_count']} Nachrichten\n")
                
                f.write("\nKALENDEREINTRÄGE:\n")
                f.write("-" * 50 + "\n")
                for i, entry in enumerate(calendar_entries):
                    f.write(f"{i+1}. {entry['subject']}\n")
                    f.write(f"   Start: {entry['start_time']}\n")
                    f.write(f"   Ende: {entry['end_time']}\n")
                    f.write(f"   Ort: {entry['location']}\n")
                    f.write(f"   Ordner: {entry['folder']}\n\n")
                
                if errors:
                    f.write("\nFEHLER WÄHREND DES EXPORTS:\n")
                    f.write("-" * 50 + "\n")
                    for i, error in enumerate(errors):
                        f.write(f"{i+1}. {error}\n")
            
        except Exception as e:
            error_msg = str(e)
            print(f"Fehler beim Verarbeiten der PST-Datei: {error_msg}")
            with open(os.path.join(out_dir, "error.txt"), "w") as f:
                f.write(f"Fehler beim Verarbeiten der PST-Datei: {error_msg}\n")
                f.write(f"Datei: {original_filename}\n")
        
        finally:
            # PST-Datei schließen
            if pst:
                try:
                    pst.close()
                except Exception:
                    pass
        
        # ZIP-Datei erstellen
        import zipfile
        print(f"Erstelle ZIP-Datei: {zip_path}")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(out_dir):
                for file_name in files:
                    file_path = os.path.join(root, file_name)
                    rel_path = os.path.relpath(file_path, out_dir)
                    zipf.write(file_path, rel_path)
        
        # Ergebnis zurückgeben
        if os.path.exists(zip_path):
            zip_size = os.path.getsize(zip_path)
            
            # Wenn das Format JSON ist, gib ein detailliertes JSON zurück
            if export_format.lower() == "json":
                return {
                    "success": True,
                    "message": f"Erweiterter Kalenderexport erfolgreich. {calendar_count} Kalendereinträge gefunden.",
                    "file_path": f"/data/ost/{zip_filename}",
                    "file_size": zip_size,
                    "calendar_count": calendar_count,
                    "total_messages": total_messages,
                    "calendar_folders": [{"name": f["name"], "path": f["path"]} for f in calendar_folders],
                    "calendar_entries": calendar_entries[:10],  # Erste 10 Einträge zurückgeben
                    "errors_count": len(errors),
                    "download_url": f"/download/{zip_filename}"
                }
            else:
                # Ansonsten ein einfacheres Format
                return {
                    "success": True,
                    "message": f"Erweiterter Kalenderexport erfolgreich. {calendar_count} Kalendereinträge gefunden.",
                    "file_path": f"/data/ost/{zip_filename}",
                    "file_size": zip_size,
                    "calendar_count": calendar_count,
                    "total_messages": total_messages,
                    "download_url": f"/download/{zip_filename}"
                }
        else:
            return {
                "success": False,
                "message": "Fehler beim Erstellen der ZIP-Datei"
            }
    
    except Exception as e:
        # Allgemeiner Fehler
        error_msg = str(e)
        print(f"Unerwarteter Fehler: {error_msg}")
        return {
            "success": False,
            "message": f"Fehler beim Export: {error_msg}"
        }
    
    finally:
        # Arbeitsverzeichnis aufräumen
        try:
            if os.path.exists(work_dir):
                shutil.rmtree(work_dir)
        except Exception as e:
            print(f"Fehler beim Aufräumen: {str(e)}")
    pass