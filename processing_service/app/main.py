from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from .sync import sync_recipient_names
from .transcript import tokenize_transcript, replace_tokens
from .matcher import match_tokens
from .db import init_db, upsert_transcription, upsert_mp3_file, get_db_connection
from typing import Optional
import json
import os
import glob
import re
from datetime import datetime

app = FastAPI()

# Initialisiere die DB beim Start
@app.on_event("startup")
def on_startup():
    init_db()

# Einheitliches Error-Handling
@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

@app.exception_handler(Exception)
def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": str(exc)})

class CorrectionRequest(BaseModel):
    language: str
    transcript: str
    options: dict = {}

@app.post("/correct-transcript")
async def correct_transcript(
    request: Request,
    file: Optional[UploadFile] = File(None),
    language: Optional[str] = Form(None),
    options: Optional[str] = Form(None),
    transcript: Optional[str] = Form(None)
):
    try:
        content_type = request.headers.get("content-type", "")
        # JSON-Request
        if content_type.startswith("application/json"):
            data = await request.json()
            transcript_text = data.get("transcript")
            language = data.get("language")
            opts = data.get("options", {})
        # multipart/form-data
        elif content_type.startswith("multipart/form-data"):
            if file is not None:
                content = await file.read()
                transcript_text = content.decode("utf-8")
            elif transcript is not None:
                transcript_text = transcript
            else:
                raise HTTPException(status_code=400, detail="Es muss entweder ein Text oder eine Datei übergeben werden.")
            if not language:
                raise HTTPException(status_code=400, detail="language muss als Form-Field übergeben werden.")
            opts = json.loads(options) if options else {}
        else:
            raise HTTPException(status_code=400, detail="Content-Type muss application/json oder multipart/form-data sein.")

        # 1. Empfängernamen synchronisieren
        sync_recipient_names()
        # 2. Tokenisierung
        tokens = tokenize_transcript(transcript_text)
        # 3. Matching
        matches = match_tokens(tokens, language, opts)
        # 4. Ersetzen
        corrected_transcript = replace_tokens(transcript_text, matches)
        # 5. Response
        return {
            "corrected_transcript": corrected_transcript,
            "matches": matches,
            "language": language
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sync-now")
def sync_now():
    try:
        sync_recipient_names()
        return {"status": "success", "message": "Empfängernamen wurden synchronisiert."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/update_transcript_data")
def update_transcript_data():
    base_dir = "/data/shared/transcription_finished"
    json_files = glob.glob(os.path.join(base_dir, "*.json"))
    processed = []
    for json_path in json_files:
        base_name = os.path.splitext(os.path.basename(json_path))[0]
        txt_path = os.path.join(base_dir, base_name + ".txt")
        if not os.path.exists(txt_path):
            continue
        # Lade JSON
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                json_data = f.read()
            import json as _json
            meta = _json.loads(json_data)[0]
        except Exception as e:
            continue
        # Lade TXT
        try:
            with open(txt_path, "r", encoding="utf-8") as f:
                transcript_text = f.read()
        except Exception as e:
            continue
        # Zeitstempel aus Dateiname
        m = re.match(r"(\d{4}-\d{2}-\d{2}) (\d{2}-\d{2}-\d{2})", base_name)
        if m:
            date_str = m.group(1) + " " + m.group(2).replace("-", ":")
            try:
                recording_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            except Exception:
                recording_date = datetime.now()
        else:
            recording_date = datetime.now()
        # Datenbank-Eintrag
        data = {
            "filepath": txt_path,
            "recording_date": recording_date,
            "detected_language": meta.get("metadata", {}).get("language"),
            "set_language": None,
            "transcript_text": transcript_text,
            "corrected_text": "",
            "participants_firstname": "",
            "participants_lastname": "",
            "transcription_duration": meta.get("metadata", {}).get("duration"),
            "audio_duration": meta.get("metadata", {}).get("audio_duration"),
            "created_at": datetime.utcnow(),
            "transcription_status": "imported"
        }
        upsert_transcription(data)
        processed.append(base_name)
    return {"status": "success", "processed": processed}

@app.post("/import_mp3_files")
def import_mp3_files():
    base_dir = "/data/shared/transcription_input"
    mp3_files = []
    import glob
    import os
    mp3_files = glob.glob(os.path.join(base_dir, "*.mp3"))
    processed = []
    conn = get_db_connection()
    cur = conn.cursor()
    for mp3_path in mp3_files:
        filename = os.path.basename(mp3_path)
        cur.execute("SELECT transcription_status FROM transcriptions WHERE filename = %s", (filename,))
        row = cur.fetchone()
        if row is not None and row[0] == "pending":
            continue  # Datei mit Status 'pending' überspringen
        upsert_mp3_file(mp3_path)
        processed.append(filename)
    cur.close()
    conn.close()
    return {"status": "success", "processed": processed} 