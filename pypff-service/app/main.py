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