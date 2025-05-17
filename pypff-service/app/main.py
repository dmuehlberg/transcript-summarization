from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse
import os, subprocess, shutil, tempfile

# Bestehende pypff-Logik importieren
from extractor import (
    dump_message_classes,
    list_calendar_entries,
    extract_calendar_entries,
    extract_all_calendar_entries,
    dump_calendar_properties,
    list_folders
)
from datetime import datetime
from pst_analysis import analyze_pst

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

        # pffexport aufrufen
        cmd = ["pffexport", "-s", scope, "-o", out_dir, in_path]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            detail = e.stderr.decode(errors="ignore")
            raise HTTPException(status_code=500, detail=f"pffexport fehlgeschlagen: {detail}")

        # Output zippen und zurückgeben
        zip_path = shutil.make_archive(os.path.join(workdir, "export"), "zip", out_dir)
        return FileResponse(zip_path, media_type="application/zip", filename="export_pffexport.zip")

# ... weitere bestehende Endpoints ...