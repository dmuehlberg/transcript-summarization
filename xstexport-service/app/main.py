from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import FileResponse
from typing import Optional

from app.models.request_models import CalendarExtractionParams
from app.services.calendar_extractor import extract_calendar_data

app = FastAPI(title="PST/OST Calendar Extractor API")

def get_extraction_params(
    format: str = Form("csv"),
    target_folder: Optional[str] = Form(None)
) -> CalendarExtractionParams:
    return CalendarExtractionParams(
        format=format,
        target_folder=target_folder
    )

@app.post("/extract-calendar/")
async def extract_calendar(
    file: UploadFile = File(...),
    params: CalendarExtractionParams = Depends()
):
    """
    Extrahiert Kalenderdaten aus PST/OST-Dateien und gibt sie als ZIP-Datei zurück.
    """
    result = await extract_calendar_data(file, params)
    return FileResponse(
        result.zip_path,
        media_type="application/zip",
        filename="calendar_export.zip"
    )

@app.get("/health")
def health_check():
    """
    Endpoint zum Überprüfen der Anwendungsverfügbarkeit.
    """
    return {"status": "healthy", "version": "1.0.0"}