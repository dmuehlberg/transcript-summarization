from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse
import os, subprocess, shutil, tempfile
import os
import re
import json
import struct
import shutil
import tempfile
import subprocess
from datetime import datetime, timedelta
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse
import pypff

# Bestehende pypff-Logik importieren
# from extractor import (
#     dump_message_classes,
#     list_calendar_entries,
#     extract_calendar_entries,
#     extract_all_calendar_entries,
#     dump_calendar_properties,
#     list_folders
# )

# from pst_analysis import analyze_pst

# Python-Bindings


app = FastAPI()

# ... bestehende Endpoints und Funktionen ...

@app.post("/export/pffexport")
async def export_pffexport(
    file: UploadFile = File(...),
    scope: str = Form("all")  # Optionen: all, debug, items, recovered
):
    """
    Exportiert Items (inkl. Kalender) via pffexport CLI.
    
    Parameter:
    - file: PST/OST-Datei zum Exportieren
    - scope: Export-Modus (all, debug, items, recovered)
    """
    # Verwenden eines Verzeichnisses, das nicht automatisch gelöscht wird
    # statt tempfile.mkdtemp(), um vorzeitiges Löschen zu vermeiden
    base_temp_dir = "/tmp/pypff_exports"
    os.makedirs(base_temp_dir, exist_ok=True)
    
    # Eindeutigen Unterordner für diesen Aufruf erstellen
    import uuid
    unique_id = str(uuid.uuid4())
    temp_dir = os.path.join(base_temp_dir, unique_id)
    os.makedirs(temp_dir, exist_ok=True)
    
    # Definiere alle Pfade
    in_path = os.path.join(temp_dir, "input.pst")  # Fester Name, um Probleme mit Sonderzeichen zu vermeiden
    out_dir = os.path.join(temp_dir, "output")
    os.makedirs(out_dir, exist_ok=True)
    zip_base = os.path.join(temp_dir, "export")
    zip_path = f"{zip_base}.zip"
    
    # Original-Dateinamen speichern, bevor wir ihn verlieren
    original_filename = file.filename
    
    try:
        # PST/OST-Datei speichern - Content in kleine Chunks aufteilen, um Speicherprobleme zu vermeiden
        with open(in_path, "wb") as f:
            # Lese in 1MB-Chunks
            chunk_size = 1024 * 1024  
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
            f.flush()
            os.fsync(f.fileno())  # Sicherstellen, dass die Datei physisch geschrieben wird
        
        print(f"Datei {original_filename} erfolgreich gespeichert als {in_path}")
        
        # Prüfen, ob die Datei tatsächlich existiert und eine Größe hat
        file_size = os.path.getsize(in_path)
        print(f"Dateigröße: {file_size} Bytes")
        if file_size == 0:
            raise HTTPException(status_code=400, detail="Hochgeladene Datei ist leer")
            
        # Gültige Scopes definieren
        valid_scopes = ["all", "debug", "items", "recovered"]
        export_mode = scope if scope in valid_scopes else "items"
        
        # pffexport ausführen
        # Alternativ zu mehreren Argumenten verwenden wir einen einzigen Befehlsstring
        # Dadurch können wir sicherstellen, dass der Befehl korrekt ausgeführt wird
        cmd_str = f"cd {temp_dir} && pffexport -m {export_mode} -f all '{in_path}' '{out_dir}'"
        print(f"Führe Befehl aus: {cmd_str}")
        
        # Shell=True verwenden, um mit dem Shell-Befehl zu arbeiten
        try:
            result = subprocess.run(
                cmd_str,
                shell=True,  # Befehl als Shell-Kommando ausführen
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            print(f"Stdout: {result.stdout.decode(errors='ignore')}")
            print(f"Stderr: {result.stderr.decode(errors='ignore')}")
        except subprocess.CalledProcessError as e:
            detail = e.stderr.decode(errors='ignore')
            print(f"pffexport fehlgeschlagen: {detail}")
            # Fehlermeldung speichern, aber Verarbeitung fortsetzen
            with open(os.path.join(out_dir, "pffexport_error.txt"), "w") as f:
                f.write(f"pffexport fehlgeschlagen: {detail}\n")
                f.write(f"Befehl: {cmd_str}\n")
        
        # Prüfen, ob Ausgabeverzeichnis Dateien enthält
        try:
            output_files = os.listdir(out_dir)
            print(f"Ausgabeverzeichnis enthält {len(output_files)} Dateien/Verzeichnisse")
            if not output_files:
                print("Ausgabeverzeichnis ist leer, erstelle Fallback-Dateien")
                # Fallback: Erstelle eine einfache Infodatei
                with open(os.path.join(out_dir, "info.txt"), "w") as f:
                    f.write(f"Export mit pffexport hat keine Dateien erzeugt.\n")
                    f.write(f"Befehl: {cmd_str}\n")
                    f.write(f"Datei: {original_filename}\n")
                    f.write(f"Dateigröße: {file_size} Bytes\n")
        except Exception as e:
            print(f"Fehler beim Überprüfen des Ausgabeverzeichnisses: {str(e)}")
            # Fallback: Erstelle eine einfache Infodatei
            with open(os.path.join(out_dir, "error.txt"), "w") as f:
                f.write(f"Fehler beim Überprüfen des Ausgabeverzeichnisses: {str(e)}\n")
        
        # ZIP-Datei erstellen
        print(f"Erstelle ZIP-Datei: {zip_path}")
        
        # Zunächst sicherstellen, dass es etwas zu zippen gibt
        if not os.path.exists(out_dir) or not os.listdir(out_dir):
            # Erstelle eine Dummy-Datei, um das Zippen zu ermöglichen
            os.makedirs(out_dir, exist_ok=True)
            with open(os.path.join(out_dir, "empty_export.txt"), "w") as f:
                f.write("Der Export hat keine Dateien erzeugt.")
        
        # ZIP erstellen mit explizitem Pfad
        try:
            # Alternative zu shutil.make_archive - direkter zipfile.ZipFile verwenden
            import zipfile
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Rekursiv alle Dateien im Ausgabeverzeichnis hinzufügen
                for root, dirs, files in os.walk(out_dir):
                    for file_name in files:
                        file_path = os.path.join(root, file_name)
                        # Relativen Pfad im ZIP-Archiv berechnen
                        rel_path = os.path.relpath(file_path, out_dir)
                        zipf.write(file_path, rel_path)
                        print(f"Datei {rel_path} zum ZIP hinzugefügt")
            
            print(f"ZIP-Datei erstellt: {zip_path}")
            
            # Prüfen, ob die ZIP-Datei existiert und eine Größe hat
            if os.path.exists(zip_path):
                zip_size = os.path.getsize(zip_path)
                print(f"ZIP-Größe: {zip_size} Bytes")
                if zip_size == 0:
                    raise ValueError("Erstellte ZIP-Datei ist leer")
            else:
                raise ValueError(f"ZIP-Datei wurde nicht erstellt: {zip_path}")
                
            # Die ZIP-Datei öffnen, um sicherzustellen, dass sie gültig ist
            with zipfile.ZipFile(zip_path, 'r') as test_zip:
                file_list = test_zip.namelist()
                print(f"ZIP-Datei enthält {len(file_list)} Einträge")
                if not file_list:
                    raise ValueError("ZIP-Datei enthält keine Einträge")
            
            # Schließlich die ZIP-Datei zurückgeben
            return FileResponse(
                path=zip_path,
                media_type="application/zip",
                filename=f"export_{original_filename}.zip"
            )
            
        except Exception as e:
            print(f"Fehler beim Erstellen der ZIP-Datei: {str(e)}")
            # Als letzten Ausweg eine einfache Textdatei zurückgeben
            error_file = os.path.join(temp_dir, "error.txt")
            with open(error_file, "w") as f:
                f.write(f"Fehler beim Erstellen der ZIP-Datei: {str(e)}\n")
                f.write(f"Datei: {original_filename}\n")
                f.write(f"Dateigröße: {file_size} Bytes\n")
                
            return FileResponse(
                path=error_file,
                media_type="text/plain",
                filename="export_error.txt"
            )
            
    except Exception as e:
        print(f"Unerwarteter Fehler: {str(e)}")
        # Selbst im Fehlerfall versuchen, eine Antwort zu senden
        try:
            error_file = os.path.join(temp_dir, "fatal_error.txt")
            with open(error_file, "w") as f:
                f.write(f"Fehler beim Export: {str(e)}\n")
            return FileResponse(
                path=error_file,
                media_type="text/plain",
                filename="export_fatal_error.txt"
            )
        except Exception as inner_e:
            # Wenn wirklich nichts funktioniert, HTTPException werfen
            print(f"Kritischer Fehler, kann keine Datei zurückgeben: {str(inner_e)}")
            raise HTTPException(status_code=500, detail=f"Export fehlgeschlagen: {str(e)} + {str(inner_e)}")



# ... weitere bestehende Endpoints ...

@app.get("/debug/pffexport-help")
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
    
@app.get("/debug/check-tools")
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


@app.get("/debug/pffexport-options")
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


@app.post("/export/simple")
async def export_simple(
    file: UploadFile = File(...),
    item_type: str = Form("all")  # Optionen: all, message, appointment, contact
):
    """
    Einfache Version des Exports, die das ZIP-File direkt ins /data/ost Verzeichnis schreibt,
    aus dem auch die PST-Dateien gelesen werden.
    """
    # Original-Dateinamen speichern und säubern
    original_filename = file.filename
    safe_filename = ''.join(c for c in original_filename if c.isalnum() or c in '._-')
    
    # Aktuelles Datum/Uhrzeit für eindeutige Dateinamen
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Permanentes Datenverzeichnis (das gemounted ist)
    data_dir = "/data/ost"
    
    # Temporäres Verzeichnis für die Verarbeitung
    work_dir = os.path.join(data_dir, f"export_{timestamp}_{safe_filename}")
    os.makedirs(work_dir, exist_ok=True)
    
    # Pfade definieren
    in_path = os.path.join(work_dir, "input.pst")
    out_dir = os.path.join(work_dir, "output")
    os.makedirs(out_dir, exist_ok=True)
    
    # Zielpfad für das ZIP-File im /data/ost Verzeichnis
    zip_filename = f"export_{timestamp}_{safe_filename}.zip"
    zip_path = os.path.join(data_dir, zip_filename)
    
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
            
            # Info-Datei erstellen
            with open(os.path.join(out_dir, "info.txt"), "w") as f:
                f.write(f"PST/OST-Datei: {original_filename}\n")
                f.write(f"Export-Datum: {datetime.now().isoformat()}\n")
                f.write(f"Anzahl Root-Ordner: {root_folder.number_of_sub_folders}\n")
                f.write(f"Nachrichten im Root: {root_folder.number_of_sub_messages}\n")
            
            # Zähler für exportierte Items
            item_count = 0
            
            # Funktion zum rekursiven Exportieren von Ordnern und Nachrichten
            def export_folder(folder, path):
                nonlocal item_count
                
                # Ordner erstellen
                folder_name = folder.name or "Unnamed"
                # Sonderzeichen entfernen
                safe_name = ''.join(c for c in folder_name if c.isalnum() or c in ' ._-')
                folder_path = os.path.join(path, safe_name)
                os.makedirs(folder_path, exist_ok=True)
                
                # Ordnerinfo schreiben
                with open(os.path.join(folder_path, "_folder_info.txt"), "w") as f:
                    f.write(f"Ordnername: {folder_name}\n")
                    f.write(f"Anzahl Nachrichten: {folder.number_of_sub_messages}\n")
                    f.write(f"Anzahl Unterordner: {folder.number_of_sub_folders}\n")
                
                # Nachrichten im Ordner exportieren
                for i in range(folder.number_of_sub_messages):
                    try:
                        msg = folder.get_sub_message(i)
                        
                        # Nachrichtenklasse ermitteln (für Filterung)
                        msg_class = "Unknown"
                        try:
                            if hasattr(msg, "get_message_class"):
                                msg_class = msg.get_message_class() or "Unknown"
                            elif hasattr(msg, "property_values") and 0x001A in msg.property_values:
                                msg_class = msg.property_values[0x001A] or "Unknown"
                            elif hasattr(msg, "get_property_data"):
                                msg_class = msg.get_property_data(0x001A) or "Unknown"
                            
                            # Wenn msg_class Bytes ist, in String umwandeln
                            if isinstance(msg_class, bytes):
                                msg_class = msg_class.decode('utf-8', errors='ignore')
                            else:
                                msg_class = str(msg_class)
                        except Exception as e:
                            print(f"Fehler beim Lesen der Nachrichtenklasse: {e}")
                        
                        # Nach Item-Typ filtern
                        if item_type != "all":
                            if item_type == "message" and "IPM.Note" not in msg_class:
                                continue
                            elif item_type == "appointment" and "IPM.Appointment" not in msg_class:
                                continue
                            elif item_type == "contact" and "IPM.Contact" not in msg_class:
                                continue
                        
                        # Betreff ermitteln
                        subject = "Unnamed"
                        try:
                            if hasattr(msg, "get_subject"):
                                subject = msg.get_subject() or "Unnamed"
                            elif hasattr(msg, "property_values") and 0x0037 in msg.property_values:
                                subject = msg.property_values[0x0037] or "Unnamed"
                            elif hasattr(msg, "get_property_data"):
                                subject = msg.get_property_data(0x0037) or "Unnamed"
                                
                            # Wenn subject Bytes ist, in String umwandeln
                            if isinstance(subject, bytes):
                                subject = subject.decode('utf-8', errors='ignore')
                        except Exception as e:
                            print(f"Fehler beim Lesen des Betreffs: {e}")
                        
                        # Dateinamen säubern
                        safe_subject = ''.join(c for c in subject if c.isalnum() or c in ' ._-')
                        safe_subject = safe_subject[:50]  # Maximale Länge beschränken
                        
                        # Nachricht als Textdatei speichern
                        msg_path = os.path.join(folder_path, f"{i}_{safe_subject}.txt")
                        with open(msg_path, "w", encoding="utf-8") as f:
                            f.write(f"Subject: {subject}\n")
                            f.write(f"Type: {msg_class}\n\n")
                            
                            # Text-Body extrahieren
                            body = "No body content available"
                            try:
                                if hasattr(msg, "get_plain_text_body"):
                                    body = msg.get_plain_text_body() or body
                                elif hasattr(msg, "property_values") and 0x1000 in msg.property_values:
                                    body = msg.property_values[0x1000] or body
                                elif hasattr(msg, "get_property_data"):
                                    body = msg.get_property_data(0x1000) or body
                                    
                                # Wenn body Bytes ist, in String umwandeln
                                if isinstance(body, bytes):
                                    body = body.decode('utf-8', errors='ignore')
                            except Exception as e:
                                body = f"Error extracting body: {e}"
                            
                            f.write(f"Body:\n{body}\n")
                        
                        item_count += 1
                    except Exception as msg_error:
                        # Bei Fehlern bei einzelnen Nachrichten fortfahren, aber Fehler protokollieren
                        error_path = os.path.join(folder_path, f"error_message_{i}.txt")
                        with open(error_path, "w") as f:
                            f.write(f"Fehler beim Verarbeiten der Nachricht {i}: {str(msg_error)}\n")
                
                # Unterordner rekursiv exportieren
                for i in range(folder.number_of_sub_folders):
                    try:
                        sub_folder = folder.get_sub_folder(i)
                        export_folder(sub_folder, folder_path)
                    except Exception as folder_error:
                        # Bei Fehlern bei einzelnen Ordnern fortfahren, aber Fehler protokollieren
                        error_path = os.path.join(folder_path, f"error_folder_{i}.txt")
                        with open(error_path, "w") as f:
                            f.write(f"Fehler beim Verarbeiten des Unterordners {i}: {str(folder_error)}\n")
            
            # Export starten
            try:
                export_folder(root_folder, out_dir)
                
                # Export-Zusammenfassung
                with open(os.path.join(out_dir, "summary.txt"), "w") as f:
                    f.write(f"Export abgeschlossen\n")
                    f.write(f"Exportierte Items: {item_count}\n")
                    f.write(f"Item-Typ: {item_type}\n")
                    f.write(f"Export-Ende: {datetime.now().isoformat()}\n")
            except Exception as export_error:
                # Fehlerinfo schreiben, ohne den Export abzubrechen
                with open(os.path.join(out_dir, "export_error.txt"), "w") as f:
                    f.write(f"Fehler während des Exports: {str(export_error)}\n")
                    f.write(f"Exportierte Items bis zum Fehler: {item_count}\n")
            
        except Exception as pff_error:
            # Fehlerinfos speichern
            with open(os.path.join(out_dir, "error.txt"), "w") as f:
                f.write(f"Fehler beim Öffnen oder Verarbeiten der PST-Datei: {str(pff_error)}\n")
                f.write(f"Datei: {original_filename}\n")
                f.write(f"Diese Fehler können auftreten, wenn die PST-Datei beschädigt ist oder ein nicht unterstütztes Format hat.\n")
        finally:
            # PST-Datei schließen
            if pst:
                try:
                    pst.close()
                except Exception:
                    pass
        
        # Prüfen, ob Ausgabeverzeichnis Dateien enthält
        try:
            output_files = os.listdir(out_dir)
            print(f"Ausgabeverzeichnis enthält {len(output_files)} Dateien/Verzeichnisse")
            if not output_files:
                # Falls keine Dateien erzeugt wurden, eine Nachricht schreiben
                with open(os.path.join(out_dir, "empty_export.txt"), "w") as f:
                    f.write("Es wurden keine Daten gefunden oder extrahiert.\n")
                    f.write(f"Dies kann passieren, wenn die Datei beschädigt ist oder kein gültiges PST/OST-Format hat.\n")
                    f.write(f"Datei: {original_filename}\n")
        except Exception as e:
            print(f"Fehler beim Überprüfen des Ausgabeverzeichnisses: {str(e)}")
        
        # ZIP-Datei erstellen direkt im /data/ost Verzeichnis
        import zipfile
        print(f"Erstelle ZIP-Datei im gemounteten Verzeichnis: {zip_path}")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(out_dir):
                for file_name in files:
                    file_path = os.path.join(root, file_name)
                    rel_path = os.path.relpath(file_path, out_dir)
                    zipf.write(file_path, rel_path)
        
        # Prüfen, ob die ZIP-Datei erstellt wurde
        if os.path.exists(zip_path):
            zip_size = os.path.getsize(zip_path)
            print(f"ZIP-Datei erfolgreich erstellt. Größe: {zip_size} Bytes")
            
            # Einfach die Erfolgsmeldung zurückgeben, anstatt die Datei direkt
            return {
                "success": True, 
                "message": f"Export erfolgreich. ZIP-Datei wurde im Verzeichnis /data/ost als '{zip_filename}' gespeichert.",
                "file_path": f"/data/ost/{zip_filename}",
                "file_size": zip_size,
                "exported_items": item_count
            }
        else:
            return {
                "success": False,
                "message": "Fehler beim Erstellen der ZIP-Datei"
            }
    
    except Exception as e:
        # Allgemeiner Fehler
        print(f"Unerwarteter Fehler: {str(e)}")
        error_file = os.path.join(data_dir, f"error_{timestamp}.txt")
        with open(error_file, "w") as f:
            f.write(f"Fehler beim Export: {str(e)}\n")
        
        return {
            "success": False,
            "message": f"Fehler beim Export: {str(e)}",
            "error_file": error_file
        }
    
    finally:
        # Aufräumen des temporären Arbeitsverzeichnisses
        try:
            if os.path.exists(work_dir):
                shutil.rmtree(work_dir)
        except Exception as e:
            print(f"Fehler beim Aufräumen von {work_dir}: {str(e)}")


@app.get("/download/{filename}")
async def download_file(filename: str):
    """
    Endpunkt zum direkten Download einer Datei aus dem /data/ost Verzeichnis.
    """
    # Sicherheitsprüfung - keine Pfad-Traversierung zulassen
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=403, detail="Ungültiger Dateiname")
    
    # Vollständigen Pfad erstellen
    file_path = os.path.join("/data/ost", filename)
    
    # Prüfen, ob die Datei existiert
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    
    # Dateierweiterung ermitteln für Content-Type
    _, extension = os.path.splitext(filename)
    content_type = "application/octet-stream"  # Standard
    
    # Content-Type basierend auf Dateierweiterung setzen
    if extension.lower() == ".zip":
        content_type = "application/zip"
    elif extension.lower() == ".txt":
        content_type = "text/plain"
    
    # Datei zurückgeben
    return FileResponse(
        path=file_path,
        media_type=content_type,
        filename=filename
    )


@app.post("/export/calendar")
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
    
    # MAPI-Eigenschaften für Kalendereinträge definieren
    # Diese MAPI-Property-IDs sind spezifisch für Kalendereinträge
    CALENDAR_PROPS = {
        0x001A: "Message Class",               # PR_MESSAGE_CLASS
        0x0037: "Subject",                     # PR_SUBJECT
        0x003D: "Creation Time",               # PR_CREATION_TIME (nur Info)
        0x1000: "Body",                        # PR_BODY
        0x0C1A: "Sender Name",                 # PR_SENDER_NAME
        0x8004: "Start Time",                  # PidLidAppointmentStartWhole
        0x8005: "End Time",                    # PidLidAppointmentEndWhole
        0x0063: "Response Status",             # PidLidResponseStatus
        0x0024: "Location",                    # PidLidLocation
        0x0065: "Reminder Minutes",            # PidLidReminderMinutesBeforeStart
        0x0E1D: "Normalized Subject",          # PR_NORMALIZED_SUBJECT
        0x0070: "Topic",                       # PR_CONVERSATION_TOPIC
        0x0023: "Creation Time",               # PR_LAST_MODIFICATION_TIME
        0x0E04: "Display To",                  # PR_DISPLAY_TO (Liste der Teilnehmer)
        0x0E03: "Display CC",                  # PR_DISPLAY_CC
        0x0062: "Importance",                  # PR_IMPORTANCE
        0x0017: "Importance",                  # PR_IMPORTANCE (zweite Methode)
        0x0036: "Sensitivity",                 # PR_SENSITIVITY
        0x000F: "Reply To",                    # PR_REPLY_RECIPIENT_NAMES
        0x0FFF: "Body HTML",                   # PR_HTML
        0x0C1F: "Sender Address Type",         # PR_SENDER_ADDRTYPE
        0x0075: "Received By Name",            # PR_RECEIVED_BY_NAME
        0x0E1F: "Message Status",              # PR_MSG_STATUS
        0x8201: "Is Recurring",                # Wiederholung - PidLidAppointmentRecur
        0x8216: "All Day Event",               # PidLidAppointmentAllDayEvent
        0x0E2D: "Has Attachment",              # PR_HASATTACH (Anhänge)
        0x8580: "Recurrence Type",             # PidLidRecurrenceType
        0x8582: "Recurrence Pattern",          # PidLidRecurrencePattern
        0x8501: "Reminder Set",                # PidLidReminderSet
        0x001F: "Organizer",                   # PidTagSenderName
    }
    
    # Zusätzliche erweiterte Eigenschaften
    EXTENDED_PROPS = {
        0x8530: "Appointment Color",           # PidLidAppointmentColor
        0x8502: "Reminder Time",               # PidLidReminderTime
        0x8560: "Attendee Type",               # Teilnehmertyp
        0x8518: "Appointment Type",            # PidLidAppointmentType
        0x8208: "Is Online Meeting",           # PidLidConferenceServer
        0x0029: "Description",                 # PidLidAutoStartCheck
        0x0020: "Attachment Files",            # PR_ATTACH_DATA_BIN
    }
    
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


@app.post("/export/calendar-debug")
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
    
    # MAPI-Eigenschaften für Kalendereinträge definieren
    # Diese MAPI-Property-IDs sind spezifisch für Kalendereinträge
    CALENDAR_PROPS = {
        0x001A: "Message Class",               # PR_MESSAGE_CLASS
        0x0037: "Subject",                     # PR_SUBJECT
        0x003D: "Creation Time",               # PR_CREATION_TIME
        0x1000: "Body",                        # PR_BODY
        0x0C1A: "Sender Name",                 # PR_SENDER_NAME
        0x8004: "Start Time",                  # PidLidAppointmentStartWhole
        0x8005: "End Time",                    # PidLidAppointmentEndWhole
        0x0063: "Response Status",             # PidLidResponseStatus
        0x0024: "Location",                    # PidLidLocation
        0x0065: "Reminder Minutes",            # PidLidReminderMinutesBeforeStart
        0x0E1D: "Normalized Subject",          # PR_NORMALIZED_SUBJECT
        0x0070: "Topic",                       # PR_CONVERSATION_TOPIC
        0x0023: "Creation Time",               # PR_LAST_MODIFICATION_TIME
        0x0E04: "Display To",                  # PR_DISPLAY_TO (Liste der Teilnehmer)
        0x0E03: "Display CC",                  # PR_DISPLAY_CC
        0x0062: "Importance",                  # PR_IMPORTANCE
        0x0017: "Importance",                  # PR_IMPORTANCE (zweite Methode)
        0x0036: "Sensitivity",                 # PR_SENSITIVITY
        0x000F: "Reply To",                    # PR_REPLY_RECIPIENT_NAMES
        0x0FFF: "Body HTML",                   # PR_HTML
        0x0C1F: "Sender Address Type",         # PR_SENDER_ADDRTYPE
        0x0075: "Received By Name",            # PR_RECEIVED_BY_NAME
        0x0E1F: "Message Status",              # PR_MSG_STATUS
        0x8201: "Is Recurring",                # Wiederholung - PidLidAppointmentRecur
        0x8216: "All Day Event",               # PidLidAppointmentAllDayEvent
        0x0E2D: "Has Attachment",              # PR_HASATTACH (Anhänge)
        0x8580: "Recurrence Type",             # PidLidRecurrenceType
        0x8582: "Recurrence Pattern",          # PidLidRecurrencePattern
        0x8501: "Reminder Set",                # PidLidReminderSet
        0x001F: "Organizer",                   # PidTagSenderName
    }
    
    # Zusätzliche erweiterte Eigenschaften
    EXTENDED_PROPS = {
        0x8530: "Appointment Color",           # PidLidAppointmentColor
        0x8502: "Reminder Time",               # PidLidReminderTime
        0x8560: "Attendee Type",               # Teilnehmertyp
        0x8518: "Appointment Type",            # PidLidAppointmentType
        0x8208: "Is Online Meeting",           # PidLidConferenceServer
        0x0029: "Description",                 # PidLidAutoStartCheck
        0x0020: "Attachment Files",            # PR_ATTACH_DATA_BIN
    }
    
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


@app.post("/debug/raw-pst")
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


@app.post("/calendar/advanced")
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
    
    # Standard MAPI-Properties, die für Kalendereinträge relevant sind
    STANDARD_CAL_PROPS = {
        0x001A: "MessageClass",               # PR_MESSAGE_CLASS
        0x0037: "Subject",                     # PR_SUBJECT
        0x003D: "CreationTime",                # PR_CREATION_TIME
        0x1000: "Body",                        # PR_BODY
        0x0C1A: "SenderName",                  # PR_SENDER_NAME
        0x8004: "StartTime",                   # PidLidAppointmentStartWhole
        0x8005: "EndTime",                     # PidLidAppointmentEndWhole
        0x0063: "ResponseStatus",              # PidLidResponseStatus
        0x0024: "Location",                    # PidLidLocation
        0x0065: "ReminderMinutesBeforeStart",  # PidLidReminderMinutesBeforeStart
        0x0E1D: "NormalizedSubject",           # PR_NORMALIZED_SUBJECT
        0x0070: "ConversationTopic",           # PR_CONVERSATION_TOPIC
        0x0E04: "DisplayTo",                   # PR_DISPLAY_TO (Teilnehmerliste)
        0x0E03: "DisplayCC",                   # PR_DISPLAY_CC
        0x0062: "Importance",                  # PR_IMPORTANCE
        0x0FFF: "HtmlBody",                    # PR_HTML
        0x8201: "IsRecurring",                 # PidLidAppointmentRecur
        0x8216: "AllDayEvent",                 # PidLidAppointmentAllDayEvent
        0x0E2D: "HasAttachment",               # PR_HASATTACH
        0x8501: "ReminderSet",                 # PidLidReminderSet
        0x001F: "OrganizerName",               # PidTagSenderName
    }
    
    # Erweiterte Property-Set - alternative IDs und zusätzliche Eigenschaften
    EXTENDED_CAL_PROPS = {
        # Alternative IDs für Standardeigenschaften
        0x00430102: "StartTime_Alt1",          # Alternative für Startzeit
        0x00440102: "EndTime_Alt1",            # Alternative für Endzeit
        0x0002: "StartTime_Alt2",              # Weitere Alternative für Startzeit
        0x0003: "EndTime_Alt2",                # Weitere Alternative für Endzeit
        0x0060: "StartTime_Alt3",              # Weitere Alternative für Startzeit
        0x0061: "EndTime_Alt3",                # Weitere Alternative für Endzeit
        0x82000102: "StartTime_Named",         # Named Property für Startzeit
        0x82010102: "EndTime_Named",           # Named Property für Endzeit
        0x82050102: "StartDate",               # Startdatum (Named Property)
        0x82060102: "EndDate",                 # Enddatum (Named Property)
        0x0094: "Location_Alt",                # Alternative für Ort
        0x8208: "Location_Named",              # Named Property für Ort
        
        # Zusätzliche Kalendereigenschaften
        0x8530: "AppointmentColor",            # PidLidAppointmentColor
        0x8502: "ReminderTime",                # PidLidReminderTime
        0x8560: "AttendeeType",                # Teilnehmertyp
        0x8518: "AppointmentType",             # PidLidAppointmentType
        0x8208: "IsOnlineMeeting",             # PidLidConferenceServer
        0x8582: "RecurrencePattern",           # PidLidRecurrencePattern
        0x8580: "RecurrenceType",              # PidLidRecurrenceType
        
        # Spezielle für RTF und HTML Inhalte
        0x1009: "RtfCompressed",               # PR_RTF_COMPRESSED
        0x1013: "HtmlContent",                 # Alternative HTML
        0x1014: "BodyContentId",               # Content-ID für HTML
        
        # Erweiterte Teilnehmer- und Organisator-Informationen
        0x0042: "OrganizerEmail",              # Organisator-E-Mail 
        0x0044: "ReceivedRepresentingName",    # Repräsentierende Person
        0x004D: "OrganizerAddressType",        # Organisator-Adresstyp
        0x0081: "OrganizerEmailAddress",       # E-Mail-Adresse des Organisators
        0x8084: "OrganizerPhoneNumber",        # Telefonnummer des Organisators
        
        # Anlagenspezifische Properties
        0x0E13: "AttachmentCount",             # Anzahl der Anlagen
        0x0E21: "AttachmentFiles",             # Anlagendateien
        
        # Für Unicode-Textfelder
        0x001F001F: "SubjectUnicode",          # Betreff (Unicode)
        0x0037001F: "SubjectAlt",              # Alternativer Betreff
        0x0070001F: "TopicUnicode",            # Thema (Unicode)
        0x1000001F: "BodyUnicode",             # Text (Unicode)
        0x0E04001F: "DisplayToUnicode",        # Empfänger (Unicode)
    }
    
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

def extract_all_properties_enhanced(msg):
    """
    Extrahiert ALLE verfügbaren Eigenschaften einer Nachricht mit erweiterter Erkennungslogik.
    
    Args:
        msg: Die Nachricht (pypff-Objekt)
        
    Returns:
        Ein Dictionary mit allen gefundenen Eigenschaften
    """
    all_props = {}
    debug_info = []
    
    # 1. Direkte Eigenschaftswerte über property_values (moderne API)
    if hasattr(msg, "property_values"):
        try:
            for prop_id, value in msg.property_values.items():
                prop_name = f"0x{prop_id:04X}"
                
                # Spezielle Behandlung für bestimmte Eigenschaftswerte
                if isinstance(value, bytes):
                    # Für Datumsfelder
                    if prop_id in [0x8004, 0x8005, 0x003D, 0x0023]:
                        if b":" in value and b"-" in value:
                            try:
                                text_value = value.decode('utf-8', errors='ignore').strip('\x00')
                                all_props[prop_name] = text_value
                            except:
                                all_props[prop_name] = f"Datum (binär): {value.hex()}"
                        else:
                            # Versuchen, als FILETIME zu interpretieren
                            try:
                                date_value = convert_filetime_to_datetime(value)
                                if date_value:
                                    all_props[prop_name] = date_value
                                else:
                                    all_props[prop_name] = f"Binär (wahrscheinlich Datum): {value.hex()}"
                            except:
                                all_props[prop_name] = f"Binär: {value.hex()}"
                    else:
                        # Allgemeine Textkonvertierung für andere Eigenschaften
                        try:
                            text_value = value.decode('utf-8', errors='ignore').strip('\x00')
                            # Prüfen, ob der String sinnvoll ist (mindestens ein alphanumerisches Zeichen)
                            if any(c.isalnum() for c in text_value):
                                all_props[prop_name] = text_value
                            else:
                                all_props[prop_name] = f"Binär: {value.hex()}"
                        except:
                            all_props[prop_name] = f"Binär: {value.hex()}"
                else:
                    all_props[prop_name] = value
                    
            debug_info.append(f"Über property_values: {len(all_props)} Eigenschaften gefunden")
        except Exception as e:
            debug_info.append(f"Fehler bei property_values: {str(e)}")
    
    # 2. Zugriff über get_number_of_properties und get_property_* (ältere API)
    # Dies könnte zusätzliche Eigenschaften offenbaren, die im property_values dict nicht enthalten sind
    if hasattr(msg, "get_number_of_properties"):
        try:
            num_props = msg.get_number_of_properties()
            debug_info.append(f"get_number_of_properties: {num_props} Eigenschaften gemeldet")
            
            # Alle verfügbaren Eigenschaften durchgehen
            for i in range(num_props):
                try:
                    prop_type = msg.get_property_type(i)
                    prop_tag = msg.get_property_tag(i)
                    prop_name = f"0x{prop_tag:04X}"
                    
                    # Wert abrufen, falls noch nicht vorhanden
                    if prop_name not in all_props:
                        try:
                            value = msg.get_property_data(prop_tag)
                            
                            # Wert konvertieren (ähnliche Logik wie oben)
                            if isinstance(value, bytes):
                                # Für Datumsfelder
                                if prop_tag in [0x8004, 0x8005, 0x003D, 0x0023]:
                                    if b":" in value and b"-" in value:
                                        text_value = value.decode('utf-8', errors='ignore').strip('\x00')
                                        all_props[prop_name] = text_value
                                    else:
                                        # Versuchen, als FILETIME zu interpretieren
                                        try:
                                            date_value = convert_filetime_to_datetime(value)
                                            if date_value:
                                                all_props[prop_name] = date_value
                                            else:
                                                all_props[prop_name] = f"Binär (Datum): {value.hex()}"
                                        except:
                                            all_props[prop_name] = f"Binär: {value.hex()}"
                                else:
                                    # Allgemeine Textkonvertierung
                                    try:
                                        text_value = value.decode('utf-8', errors='ignore').strip('\x00')
                                        if any(c.isalnum() for c in text_value):
                                            all_props[prop_name] = text_value
                                        else:
                                            all_props[prop_name] = f"Binär: {value.hex()}"
                                    except:
                                        all_props[prop_name] = f"Binär: {value.hex()}"
                            else:
                                all_props[prop_name] = value
                        except Exception as e:
                            all_props[f"{prop_name}_error"] = f"Fehler: {str(e)}"
                except Exception as e:
                    debug_info.append(f"Fehler bei Property {i}: {str(e)}")
                    
            debug_info.append(f"Nach get_property_*: Insgesamt {len(all_props)} Eigenschaften gefunden")
        except Exception as e:
            debug_info.append(f"Fehler bei get_number_of_properties: {str(e)}")
    
    # 3. Gezieltes Abtasten nach häufigen MAPI-Eigenschaften, die möglicherweise bisher verborgen sind
    common_props = [
        # Standardeigenschaften für Nachrichten
        0x001A, 0x0037, 0x003D, 0x1000, 0x0E1D, 0x0070, 0x0E04, 0x0E03, 0x0062, 0x0FFF,
        # Kalenderspezifische Eigenschaften 
        0x8004, 0x8005, 0x0024, 0x8201, 0x8216, 0x8580, 0x8582, 0x8501,
        # Verschiedene alternative Formate und Variationen
        0x001A001F, 0x0037001F, 0x1000001F, 0x0E04001F
    ]
    
    # Erweiterte Bereiche für bestimmte Eigenschaftstypen durchsuchen
    for base in [0x8000, 0x8100, 0x8200, 0x8300, 0x8400, 0x8500, 0x8600]:
        for offset in range(0, 0xFF, 10):  # In Schritten von 10, um Zeit zu sparen
            common_props.append(base + offset)
    
    for prop_id in common_props:
        prop_name = f"0x{prop_id:04X}"
        if prop_name not in all_props:
            try:
                value = None
                if hasattr(msg, "get_property_data"):
                    value = msg.get_property_data(prop_id)
                
                if value is not None:
                    # Wert konvertieren (ähnlich wie oben)
                    if isinstance(value, bytes):
                        try:
                            text_value = value.decode('utf-8', errors='ignore').strip('\x00')
                            if any(c.isalnum() for c in text_value):
                                all_props[prop_name] = text_value
                                debug_info.append(f"Zusätzliche Property {prop_name} gefunden")
                            else:
                                # Für nichtdruckbare Zeichen Binärformat verwenden
                                all_props[prop_name] = f"Binär: {value.hex()}"
                        except:
                            all_props[prop_name] = f"Binär: {value.hex()}"
                    else:
                        all_props[prop_name] = value
                        debug_info.append(f"Zusätzliche Property {prop_name} gefunden")
            except Exception:
                # Fehler ignorieren, da es normal ist, dass nicht alle Properties existieren
                pass
    
    # 4. Versuch, Named Properties zu extrahieren (falls verfügbar)
    # Dies ist ein experimenteller Ansatz, da pypff keine direkte API für Named Properties bietet
    if hasattr(msg, "get_named_properties"):
        try:
            named_props = msg.get_named_properties()
            for prop_name, prop_value in named_props.items():
                all_props[f"Named_{prop_name}"] = prop_value
                debug_info.append(f"Named Property {prop_name} gefunden")
        except Exception as e:
            debug_info.append(f"Fehler bei Named Properties: {str(e)}")
    
    # Debug-Info an alle_props anhängen (optional)
    all_props["_debug_info"] = debug_info
    
    return all_props

def convert_filetime_to_datetime(filetime_bytes):
    """
    Konvertiert einen binären FILETIME-Wert (8 Bytes) in ein lesbares Datum.
    
    FILETIME ist ein 64-Bit-Wert, der die Anzahl der 100-Nanosekunden-Intervalle 
    seit dem 1. Januar 1601 darstellt.
    
    Args:
        filetime_bytes: FILETIME als Bytes-Objekt
        
    Returns:
        Ein ISO-formatierter Datumsstring oder None bei Fehler
    """
    if not filetime_bytes or len(filetime_bytes) != 8:
        return None
        
    try:
        # Bytes in eine 64-Bit-Ganzzahl konvertieren (little-endian)
        filetime = int.from_bytes(filetime_bytes, byteorder='little')
        
        # FILETIME in einen Unix-Timestamp umwandeln
        # FILETIME ist die Anzahl der 100-Nanosekunden-Intervalle seit dem 1. Januar 1601
        # Unix-Timestamp ist die Anzahl der Sekunden seit dem 1. Januar 1970
        # Differenz in Sekunden zwischen 1601-01-01 und 1970-01-01
        epoch_diff = 11644473600
        
        # Umrechnen von 100-Nanosekunden in Sekunden und Epochendifferenz abziehen
        unix_timestamp = filetime / 10000000 - epoch_diff
        
        # In ein Datetime-Objekt umwandeln
        import datetime
        dt = datetime.datetime.fromtimestamp(unix_timestamp)
        
        # Als ISO-Format zurückgeben
        return dt.isoformat()
    except Exception as e:
        print(f"Fehler bei der Datumskonvertierung: {str(e)}")
        return f"Binäres Datum: {filetime_bytes.hex()}"
    
@app.post("/tools/convert-binary-date")
async def convert_binary_date(
    file: UploadFile = File(None),
    hex_value: str = Form(None)
):
    """
    Konvertiert binäre Datumswerte aus PST-Dateien in lesbare Formate.
    
    Parameters:
    - file: Optional, eine Datei, die binäre Daten enthält
    - hex_value: Optional, ein Hex-String (z.B. "0080F29544A5CA01")
    """
    result = {
        "input_type": None,
        "input_value": None,
        "converted_date": None,
        "datetime_formats": {},
        "error": None
    }
    
    try:
        # Entweder Datei oder Hex-Wert verwenden
        binary_data = None
        
        if hex_value:
            result["input_type"] = "hex_string"
            result["input_value"] = hex_value
            # Hex-String in Bytes umwandeln
            try:
                # Leerzeichen entfernen und in Bytes konvertieren
                cleaned_hex = hex_value.replace(" ", "")
                binary_data = bytes.fromhex(cleaned_hex)
            except Exception as e:
                result["error"] = f"Ungültiger Hex-String: {str(e)}"
                return result
        
        elif file:
            result["input_type"] = "file"
            # Datei lesen (maximal die ersten 1024 Bytes)
            content = await file.read(1024)
            binary_data = content
            result["input_value"] = content.hex()
        
        else:
            result["error"] = "Es muss entweder eine Datei oder ein Hex-Wert angegeben werden"
            return result
        
        # Analysieren der Bytes für verschiedene Datumsformate
        
        # 1. FILETIME (8 Bytes)
        if len(binary_data) >= 8:
            try:
                filetime_data = binary_data[:8]
                filetime_date = convert_filetime_to_datetime(filetime_data)
                if filetime_date:
                    result["datetime_formats"]["filetime"] = {
                        "description": "Windows FILETIME (8 Bytes, 100-Nanosekunden seit 1601-01-01)",
                        "bytes": filetime_data.hex(),
                        "date": filetime_date
                    }
                    
                    # Den ersten erfolgreichen Wert als Hauptergebnis setzen
                    if not result["converted_date"]:
                        result["converted_date"] = filetime_date
            except Exception as e:
                result["datetime_formats"]["filetime_error"] = str(e)
        
        # 2. OLE Automation Date (8 Bytes, Doublewert)
        if len(binary_data) >= 8:
            try:
                import struct
                double_data = binary_data[:8]
                # Als Double dekodieren
                double_value = struct.unpack('<d', double_data)[0]
                
                # OLE Automation Datum: Anzahl der Tage seit 30.12.1899
                # Ganzzahliger Teil = Tage, Bruchteil = Tagesanteil
                import datetime
                base_date = datetime.datetime(1899, 12, 30)
                
                days = int(double_value)
                day_fraction = double_value - days
                
                # Datumsteil berechnen
                date_part = base_date + datetime.timedelta(days=days)
                
                # Tagesbruchteil in Stunden/Minuten/Sekunden umrechnen
                seconds = int(day_fraction * 86400)  # 24*60*60 Sekunden pro Tag
                time_part = datetime.timedelta(seconds=seconds)
                
                # Kombiniertes Datum
                ole_date = date_part + time_part
                
                if 0 <= double_value <= 2958465:  # Plausibilitätsprüfung
                    result["datetime_formats"]["ole_automation"] = {
                        "description": "OLE Automation Date (8 Bytes Double, Tage seit 1899-12-30)",
                        "bytes": double_data.hex(),
                        "double_value": double_value,
                        "date": ole_date.isoformat()
                    }
                    
                    # Als Hauptergebnis setzen, falls noch nicht gesetzt
                    if not result["converted_date"]:
                        result["converted_date"] = ole_date.isoformat()
            except Exception as e:
                result["datetime_formats"]["ole_automation_error"] = str(e)
        
        # 3. Unix-Timestamp (4 Bytes, Sekunden seit 1970-01-01)
        if len(binary_data) >= 4:
            try:
                unix_data = binary_data[:4]
                # Als 32-Bit Integer dekodieren
                unix_timestamp = int.from_bytes(unix_data, byteorder='little')
                
                # In Datetime umwandeln
                import datetime
                unix_date = datetime.datetime.fromtimestamp(unix_timestamp)
                
                # Plausibilitätsprüfung: Zwischen 1980 und 2040
                if 315532800 <= unix_timestamp <= 2208988800:
                    result["datetime_formats"]["unix_timestamp"] = {
                        "description": "Unix-Timestamp (4 Bytes, Sekunden seit 1970-01-01)",
                        "bytes": unix_data.hex(),
                        "timestamp": unix_timestamp,
                        "date": unix_date.isoformat()
                    }
                    
                    # Als Hauptergebnis setzen, falls noch nicht gesetzt
                    if not result["converted_date"]:
                        result["converted_date"] = unix_date.isoformat()
            except Exception as e:
                result["datetime_formats"]["unix_timestamp_error"] = str(e)
        
        # 4. Windows SYSTEMTIME-Struktur (16 Bytes)
        if len(binary_data) >= 16:
            try:
                systemtime_data = binary_data[:16]
                # SYSTEMTIME-Struktur: Jahr, Monat, Tag, Wochentag, Stunde, Minute, Sekunde, Millisekunde
                # Jeweils als 16-Bit-Wort (2 Bytes)
                year = int.from_bytes(systemtime_data[0:2], byteorder='little')
                month = int.from_bytes(systemtime_data[2:4], byteorder='little')
                day = int.from_bytes(systemtime_data[6:8], byteorder='little')
                hour = int.from_bytes(systemtime_data[8:10], byteorder='little')
                minute = int.from_bytes(systemtime_data[10:12], byteorder='little')
                second = int.from_bytes(systemtime_data[12:14], byteorder='little')
                millisecond = int.from_bytes(systemtime_data[14:16], byteorder='little')
                
                # Plausibilitätsprüfung
                if (1601 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31 and
                    0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
                    
                    import datetime
                    try:
                        systemtime_date = datetime.datetime(
                            year, month, day, hour, minute, second, millisecond * 1000
                        )
                        
                        result["datetime_formats"]["systemtime"] = {
                            "description": "Windows SYSTEMTIME (16 Bytes)",
                            "bytes": systemtime_data.hex(),
                            "year": year,
                            "month": month,
                            "day": day,
                            "hour": hour,
                            "minute": minute,
                            "second": second,
                            "millisecond": millisecond,
                            "date": systemtime_date.isoformat()
                        }
                        
                        # Als Hauptergebnis setzen, falls noch nicht gesetzt
                        if not result["converted_date"]:
                            result["converted_date"] = systemtime_date.isoformat()
                    except ValueError:
                        # Ungültiges Datum
                        pass
            except Exception as e:
                result["datetime_formats"]["systemtime_error"] = str(e)
        
        # Wenn kein Format erkannt wurde
        if not result["converted_date"] and not result["error"]:
            result["error"] = "Keine bekannten Datumsformate erkannt"
        
        return result
        
    except Exception as e:
        result["error"] = f"Allgemeiner Fehler: {str(e)}"
        return result
    
def try_convert_binary_date(value, formats=None):
    """
    Versucht, einen binären Wert in ein Datum zu konvertieren, indem verschiedene Formate ausprobiert werden.
    
    Args:
        value: Der zu konvertierende binäre Wert (bytes)
        formats: Optionale Liste von zu versuchenden Formaten 
                 (gültige Werte: 'filetime', 'ole', 'unix', 'systemtime')
                 
    Returns:
        Ein ISO-formatierter Datumsstring oder None bei Fehler
    """
    if not formats:
        formats = ['filetime', 'ole', 'systemtime', 'unix']
    
    if not value or not isinstance(value, bytes):
        return None
    
    results = {}
    
    # 1. FILETIME-Format testen (8 Bytes)
    if 'filetime' in formats and len(value) >= 8:
        try:
            filetime_data = value[:8]
            date = convert_filetime_to_datetime(filetime_data)
            if date:
                results['filetime'] = date
        except Exception:
            pass
    
    # 2. OLE Automation Date testen (8 Bytes als Double)
    if 'ole' in formats and len(value) >= 8:
        try:
            import struct
            double_data = value[:8]
            double_value = struct.unpack('<d', double_data)[0]
            
            # OLE Datum (Tage seit 30.12.1899)
            import datetime
            base_date = datetime.datetime(1899, 12, 30)
            
            days = int(double_value)
            day_fraction = double_value - days
            
            date_part = base_date + datetime.timedelta(days=days)
            seconds = int(day_fraction * 86400)
            time_part = datetime.timedelta(seconds=seconds)
            
            ole_date = date_part + time_part
            
            # Plausibilitätsprüfung
            if 0 <= double_value <= 2958465:  # Etwa bis zum Jahr 9999
                results['ole'] = ole_date.isoformat()
        except Exception:
            pass
    
    # 3. Unix-Timestamp testen (4 Bytes)
    if 'unix' in formats and len(value) >= 4:
        try:
            unix_data = value[:4]
            unix_timestamp = int.from_bytes(unix_data, byteorder='little')
            
            import datetime
            unix_date = datetime.datetime.fromtimestamp(unix_timestamp)
            
            # Plausibilitätsprüfung: Zwischen 1980 und 2040
            if 315532800 <= unix_timestamp <= 2208988800:
                results['unix'] = unix_date.isoformat()
        except Exception:
            pass
    
    # 4. SYSTEMTIME-Struktur testen (16 Bytes)
    if 'systemtime' in formats and len(value) >= 16:
        try:
            systemtime_data = value[:16]
            year = int.from_bytes(systemtime_data[0:2], byteorder='little')
            month = int.from_bytes(systemtime_data[2:4], byteorder='little')
            day = int.from_bytes(systemtime_data[6:8], byteorder='little')
            hour = int.from_bytes(systemtime_data[8:10], byteorder='little')
            minute = int.from_bytes(systemtime_data[10:12], byteorder='little')
            second = int.from_bytes(systemtime_data[12:14], byteorder='little')
            millisecond = int.from_bytes(systemtime_data[14:16], byteorder='little')
            
            if (1601 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31 and
                0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
                
                import datetime
                try:
                    systemtime_date = datetime.datetime(
                        year, month, day, hour, minute, second, millisecond * 1000
                    )
                    results['systemtime'] = systemtime_date.isoformat()
                except ValueError:
                    pass
        except Exception:
            pass
    
    # Ergebnisse auswerten
    if results:
        # Prioritätsreihenfolge: FILETIME, SYSTEMTIME, OLE, UNIX
        for fmt in ['filetime', 'systemtime', 'ole', 'unix']:
            if fmt in results:
                return results[fmt]
        
        # Falls die Prioritätsformate nicht vorhanden sind, erstes gefundenes Ergebnis nehmen
        return next(iter(results.values()))
    
    return None

@app.post("/debug/inspect-calendar-properties")
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