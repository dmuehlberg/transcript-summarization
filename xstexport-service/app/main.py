import os
import subprocess
import tempfile
import shutil
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
import uuid

app = FastAPI(title="PST/OST Calendar Extractor API")

@app.post("/extract-calendar/")
async def extract_calendar(
    file: UploadFile = File(...),
    format: str = Form("csv"),  # csv oder native
    target_folder: Optional[str] = Form(None)
):
    # Temporäres Verzeichnis für die Verarbeitung erstellen
    temp_dir = tempfile.mkdtemp()
    result_dir = os.path.join(temp_dir, "result")
    os.makedirs(result_dir, exist_ok=True)
    
    # Upload-Datei speichern
    file_path = os.path.join(temp_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        # XstPortableExport aufrufen
        export_option = "-e" if format == "native" else "-p"
        cmd = [
            "dotnet", 
            "/app/XstPortableExport.dll", 
            export_option,
            "-f=Calendar", 
            "-t=" + result_dir,
            file_path
        ]
        
        process = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True
        )
        
        if process.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Extraction failed: {process.stderr}")
        
        # Ergebnisse als ZIP verpacken für den Download
        output_zip = os.path.join(temp_dir, "calendar_export.zip")
        shutil.make_archive(
            os.path.splitext(output_zip)[0],  # Basis-Dateiname ohne Erweiterung
            'zip',
            result_dir
        )
        
        # ZIP-Datei zurückgeben
        return FileResponse(
            output_zip, 
            media_type="application/zip",
            filename="calendar_export.zip"
        )
    
    finally:
        # Aufräumen (im Produktionscode würden Sie hier einen Job-Queue verwenden)
        # shutil.rmtree(temp_dir)
        pass

@app.get("/health")
def health_check():
    return {"status": "healthy"}