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
    # Hier wird ein temporäres Verzeichnis erstellt, das nach der Funktion automatisch gelöscht wird
    temp_dir = tempfile.mkdtemp()
    try:
        # Pfade erstellen
        in_path = os.path.join(temp_dir, file.filename)
        out_dir = os.path.join(temp_dir, "output")
        os.makedirs(out_dir, exist_ok=True)
        zip_path = os.path.join(temp_dir, "export.zip")

        # PST/OST-Datei in das temporäre Verzeichnis speichern
        with open(in_path, "wb") as f:
            content = await file.read()
            f.write(content)
            f.flush()
            os.fsync(f.fileno())  # Sicherstellen, dass Datei auf Festplatte geschrieben wird

        # Ausgabeformat und Modus definieren
        valid_scopes = ["all", "debug", "items", "recovered"]
        export_mode = scope if scope in valid_scopes else "items"
        
        # pffexport-Befehl zusammenstellen
        cmd = [
            "pffexport",
            "-m", export_mode,
            "-f", "all",
            in_path
        ]
        
        # Debug-Ausgabe
        print(f"Ausführen: {' '.join(cmd)}")
        print(f"Ausgabeverzeichnis: {out_dir}")
        
        # pffexport ausführen
        try:
            result = subprocess.run(
                cmd,
                cwd=out_dir,  # Im Ausgabeverzeichnis ausführen lassen
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            print(f"Stdout: {result.stdout.decode(errors='ignore')}")
            print(f"Stderr: {result.stderr.decode(errors='ignore')}")
        except subprocess.CalledProcessError as e:
            detail = e.stderr.decode(errors='ignore')
            raise HTTPException(status_code=500, detail=f"pffexport fehlgeschlagen: {detail}")
        
        # Prüfen, ob Dateien exportiert wurden
        if not os.path.exists(out_dir) or not os.listdir(out_dir):
            # Manuelles Kopieren der PST-Datei als Fallback
            fallback_dir = os.path.join(out_dir, "fallback")
            os.makedirs(fallback_dir, exist_ok=True)
            shutil.copy(in_path, os.path.join(fallback_dir, "original.pst"))
            with open(os.path.join(fallback_dir, "info.txt"), "w") as f:
                f.write("Export mit pffexport hat keine Dateien erzeugt.\n")
                f.write(f"Befehl: {' '.join(cmd)}\n")
                f.write("Die Originaldatei wurde stattdessen kopiert.")
                
        # Verzeichnisinhalt auflisten (für Debugging)
        print(f"Inhalt des Ausgabeverzeichnisses: {os.listdir(out_dir)}")
        
        # Output zippen
        print(f"Erstelle ZIP-Datei: {zip_path}")
        try:
            # Direkter Zugriff auf die shutil.make_archive Funktion
            # Der Basisname der ZIP-Datei ohne Erweiterung
            zip_base = os.path.join(temp_dir, "export")
            # Erstelle das Archiv
            created_zip = shutil.make_archive(zip_base, 'zip', out_dir)
            print(f"ZIP-Datei erstellt: {created_zip}")
            
            # Überprüfen, ob die ZIP-Datei erstellt wurde
            if not os.path.exists(created_zip):
                raise HTTPException(status_code=500, detail=f"Fehler beim Erstellen der ZIP-Datei: {created_zip} existiert nicht")
            
            # Datei explizit in Binärmodus öffnen, um sicherzustellen, dass sie existiert und lesbar ist
            with open(created_zip, "rb") as f:
                # Ersten Bytes lesen, um zu prüfen, ob die Datei valide ist
                first_bytes = f.read(10)
                if not first_bytes:
                    raise HTTPException(status_code=500, detail="ZIP-Datei scheint leer zu sein")
            
            # Die ZIP-Datei zurückgeben
            return FileResponse(
                path=created_zip,
                media_type="application/zip",
                filename="export_pffexport.zip"
            )
        except Exception as e:
            print(f"Fehler beim Erstellen oder Zurückgeben der ZIP-Datei: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Fehler beim Erstellen der ZIP-Datei: {str(e)}")
    
    except Exception as e:
        # Allgemeine Fehlerbehandlung
        print(f"Unerwarteter Fehler: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Export fehlgeschlagen: {str(e)}")
    
    finally:
        # Temporäres Verzeichnis aufräumen, aber nur wenn wir nicht im Debug-Modus sind
        try:
            if os.path.exists(temp_dir):
                print(f"Lösche temporäres Verzeichnis: {temp_dir}")
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as cleanup_error:
            print(f"Fehler beim Aufräumen: {str(cleanup_error)}")
            # Kein Fehler werfen, da die ZIP-Datei möglicherweise schon zurückgegeben wurde</parameter>



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