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
    scope: str = Form("all")  # Optionen: all, message, attachment, calendar etc.
):
    """
    Exportiert Items (inkl. Kalender) via pffexport CLI.
    """
    with tempfile.TemporaryDirectory() as workdir:
        in_path = os.path.join(workdir, file.filename)
        out_dir = os.path.join(workdir, "output")
        os.makedirs(out_dir, exist_ok=True)

        # PST/OST sichern
        with open(in_path, "wb") as f:
            f.write(await file.read())

        # pffexport aufrufen - korrigierte Parameter
        # Das Tool unterstützt keine -s Option, verwende stattdessen -m für Modus
        # oder -t für Item-Typen
        
        # Basisbefehl
        cmd = ["pffexport", "-o", out_dir]
        
        # Je nach gewünschtem Scope/Modus den passenden Parameter hinzufügen
        if scope == "all":
            # Standard: Alles exportieren
            pass
        elif scope == "message":
            cmd.append("-t")
            cmd.append("message")
        elif scope == "calendar":
            cmd.append("-t")
            cmd.append("appointment")
        elif scope == "attachment":
            cmd.append("-t")
            cmd.append("attachment")
        else:
            # Fallback auf -t mit dem angegebenen Wert, falls es ein gültiger Typ ist
            cmd.append("-t")
            cmd.append(scope)
            
        # Dateinamen anfügen
        cmd.append(in_path)
        
        try:
            # Debug-Ausgabe des Befehls
            print(f"Ausführen: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd, 
                check=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
            
            # Debug-Ausgabe der Ergebnisse
            print(f"Stdout: {result.stdout.decode(errors='ignore')}")
            print(f"Stderr: {result.stderr.decode(errors='ignore')}")
            
        except subprocess.CalledProcessError as e:
            detail = e.stderr.decode(errors="ignore")
            raise HTTPException(status_code=500, detail=f"pffexport fehlgeschlagen: {detail}")

        # Output zippen und zurückgeben
        zip_path = shutil.make_archive(os.path.join(workdir, "export"), "zip", out_dir)
        return FileResponse(zip_path, media_type="application/zip", filename="export_pffexport.zip")

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