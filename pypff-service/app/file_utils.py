# file_utils.py
import os
import shutil
import zipfile
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse
import pypff

async def export_simple(
    file: UploadFile = File(...),
    item_type: str = Form("all")  # Optionen: all, message, appointment, contact
):
    """
    Einfache Version des Exports, die das ZIP-File direkt ins /data/ost Verzeichnis schreibt,
    aus dem auch die PST-Dateien gelesen werden.
    """
    # Implementierung aus main copy.py übernehmen
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