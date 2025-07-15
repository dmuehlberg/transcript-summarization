# extractor.py
import os
import subprocess
import shutil
import tempfile
import zipfile
from fastapi import UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from datetime import datetime
import pypff

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
    pass