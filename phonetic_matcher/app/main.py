from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from .sync import sync_recipient_names
from .transcript import tokenize_transcript, replace_tokens
from .matcher import match_tokens
from .db import init_db
from typing import Optional
import json

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