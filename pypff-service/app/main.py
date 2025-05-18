from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse
import os, subprocess, shutil, tempfile

# Bestehende pypff-Logik importieren
# from extractor import (
#     dump_message_classes,
#     list_calendar_entries,
#     extract_calendar_entries,
#     extract_all_calendar_entries,
#     dump_calendar_properties,
#     list_folders
# )
from datetime import datetime
# from pst_analysis import analyze_pst

# Python-Bindings
import pypff

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