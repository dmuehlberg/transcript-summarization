from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from .sync import sync_recipient_names
from .transcript import tokenize_transcript, replace_tokens
from .matcher import match_tokens
from .db import init_db, upsert_transcription, upsert_mp3_file, get_db_connection, update_transcription_meeting_info, get_pending_transcriptions
from .confluence import (
    build_auth_header,
    get_space_id,
    get_parent_page_id,
    create_confluence_page,
    convert_markdown_to_storage_format
)
from typing import Optional
import json
import os
import glob
import re
from datetime import datetime
import pytz
from dotenv import load_dotenv
import requests

load_dotenv()

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
    # Konvertiere bytes zu strings für JSON-Serialisierung
    errors = []
    for error in exc.errors():
        cleaned_error = {}
        for key, value in error.items():
            if isinstance(value, bytes):
                cleaned_error[key] = value.decode('utf-8', errors='replace')
            else:
                cleaned_error[key] = value
        errors.append(cleaned_error)
    return JSONResponse(status_code=422, content={"detail": errors})

@app.exception_handler(Exception)
def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": str(exc)})

class CorrectionRequest(BaseModel):
    language: str
    transcript: str
    options: dict = {}

class MeetingInfoRequest(BaseModel):
    recording_date: Optional[str] = None

class MeetingsByDateRequest(BaseModel):
    recording_date: str

class ConfluencePageRequest(BaseModel):
    space_name: str
    parent_page_title: Optional[str] = None
    content: str
    content_format: Optional[str] = "storage"  # "markdown" oder "storage"
    page_title: str
    user: Optional[str] = None  # Optional, wird aus .env gelesen falls nicht angegeben
    site_url: str

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
    
    # Zeitzone aus .env laden
    timezone_str = os.getenv("TIMEZONE", "Europe/Berlin")
    local_tz = pytz.timezone(timezone_str)
    
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
                # Mit lokaler Zeitzone versehen
                recording_date = local_tz.localize(recording_date)
            except Exception:
                recording_date = datetime.utcnow().replace(tzinfo=pytz.UTC)
        else:
            recording_date = datetime.utcnow().replace(tzinfo=pytz.UTC)
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

@app.post("/get_meeting_info")
def get_meeting_info(request: MeetingInfoRequest):
    try:
        # Zeitzone aus .env laden
        timezone_str = os.getenv("TIMEZONE", "Europe/Berlin")
        local_tz = pytz.timezone(timezone_str)
        
        # Wenn recording_date angegeben ist, verarbeite nur dieses Datum
        if request.recording_date:
            try:
                recording_date = datetime.strptime(request.recording_date, "%Y-%m-%d %H-%M")
                recording_date_local = local_tz.localize(recording_date)
                recording_date_utc = recording_date_local.astimezone(pytz.UTC)
                
                conn = get_db_connection()
                cur = conn.cursor()
                
                # Suche nach passendem Eintrag in calendar_data mit UTC-Vergleich
                from datetime import timedelta
                time_window_minutes = int(os.getenv("MEETING_TIME_WINDOW_MINUTES", "5"))
                time_window_start = recording_date_utc - timedelta(minutes=time_window_minutes)
                time_window_end = recording_date_utc + timedelta(minutes=time_window_minutes)
                
                cur.execute("""
                    SELECT start_date, end_date, subject, has_picture, user_entry_id, display_to, display_cc
                    FROM calendar_data
                    WHERE start_date BETWEEN %s AND %s
                    ORDER BY ABS(EXTRACT(EPOCH FROM (start_date - %s))) ASC
                """, (time_window_start, time_window_end, recording_date_utc))
                rows = cur.fetchall()
                if not rows:
                    cur.close()
                    conn.close()
                    raise HTTPException(status_code=404, detail=f"Kein Meeting im Zeitfenster von +/- {time_window_minutes} Minuten um den angegebenen Zeitpunkt gefunden.")
                elif len(rows) > 1:
                    info_dict = {
                        "meeting_start_date": None,
                        "meeting_end_date": None,
                        "meeting_title": "Multiple Meetings found",
                        "meeting_location": None,
                        "invitation_text": None,
                        "participants": None
                    }
                    update_transcription_meeting_info(recording_date_local, info_dict)
                    cur.close()
                    conn.close()
                    return {"status": "success", "meeting_info": info_dict}
                else:
                    row = rows[0]
                    start_date, end_date, subject, has_picture, user_entry_id, display_to, display_cc = row
                # Teilnehmernamen kombinieren und deduplizieren
                import re as _re
                tokens = set()
                for field in [display_to, display_cc]:
                    if not field:
                        continue
                    parts = _re.split(r"[;,]", field)
                    for part in parts:
                        words = part.strip().split()
                        for word in words:
                            clean = _re.sub(r"[^\wäöüÄÖÜß-]", "", word)
                            if clean:
                                tokens.add(clean)
                participants = ";".join(sorted(tokens))
                info_dict = {
                    "meeting_start_date": start_date,
                    "meeting_end_date": end_date,
                    "meeting_title": subject,
                    "meeting_location": has_picture,
                    "invitation_text": user_entry_id,
                    "participants": participants
                }
                update_transcription_meeting_info(recording_date_local, info_dict)
                cur.close()
                conn.close()
                return {"status": "success", "meeting_info": info_dict}
            except Exception:
                raise HTTPException(status_code=400, detail="recording_date muss im Format YYYY-MM-DD HH-MM sein")
        
        # Wenn kein recording_date angegeben ist, verarbeite alle pending Transkriptionen
        pending_transcriptions = get_pending_transcriptions()
        results = []
        
        for transcription_id, recording_date in pending_transcriptions:
            try:
                # recording_date ist bereits ein datetime-Objekt mit Zeitzoneninformation
                recording_date_local = recording_date.astimezone(local_tz)
                recording_date_utc = recording_date_local.astimezone(pytz.UTC)
                
                conn = get_db_connection()
                cur = conn.cursor()
                
                # Suche nach passendem Eintrag in calendar_data mit UTC-Vergleich
                from datetime import timedelta
                time_window_minutes = int(os.getenv("MEETING_TIME_WINDOW_MINUTES", "5"))
                time_window_start = recording_date_utc - timedelta(minutes=time_window_minutes)
                time_window_end = recording_date_utc + timedelta(minutes=time_window_minutes)
                
                cur.execute("""
                    SELECT start_date, end_date, subject, has_picture, user_entry_id, display_to, display_cc
                    FROM calendar_data
                    WHERE start_date BETWEEN %s AND %s
                    ORDER BY ABS(EXTRACT(EPOCH FROM (start_date - %s))) ASC
                """, (time_window_start, time_window_end, recording_date_utc))
                rows = cur.fetchall()
                
                if not rows:
                    results.append({"id": transcription_id, "error": f"Kein Meeting im Zeitfenster von +/- {time_window_minutes} Minuten gefunden"})
                elif len(rows) > 1:
                    info_dict = {
                        "meeting_start_date": None,
                        "meeting_end_date": None,
                        "meeting_title": "Mehrere Meetings gefunden",
                        "meeting_location": None,
                        "invitation_text": None,
                        "participants": None
                    }
                    update_transcription_meeting_info(recording_date_local, info_dict)
                    results.append({"id": transcription_id, "meeting_info": info_dict})
                else:
                    row = rows[0]
                    start_date, end_date, subject, has_picture, user_entry_id, display_to, display_cc = row
                    # Teilnehmernamen kombinieren und deduplizieren
                    import re as _re
                    tokens = set()
                    for field in [display_to, display_cc]:
                        if not field:
                            continue
                        parts = _re.split(r"[;,]", field)
                        for part in parts:
                            words = part.strip().split()
                            for word in words:
                                clean = _re.sub(r"[^\wäöüÄÖÜß-]", "", word)
                                if clean:
                                    tokens.add(clean)
                    participants = ";".join(sorted(tokens))
                    info_dict = {
                        "meeting_start_date": start_date,
                        "meeting_end_date": end_date,
                        "meeting_title": subject,
                        "meeting_location": has_picture,
                        "invitation_text": user_entry_id,
                        "participants": participants
                    }
                    update_transcription_meeting_info(recording_date_local, info_dict)
                    results.append({"id": transcription_id, "meeting_info": info_dict})
                
                cur.close()
                conn.close()
                
            except Exception as e:
                results.append({"id": transcription_id, "error": str(e)})
        
        return {"status": "success", "processed": len(results), "details": results}
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_meetings_by_date")
def get_meetings_by_date(recording_date: str):
    """
    Lädt alle Meetings eines Tages basierend auf dem recording_date.
    Parameter: recording_date (Format: YYYY-MM-DD oder YYYY-MM-DD HH-MM)
    """
    try:
        # Zeitzone aus .env laden
        timezone_str = os.getenv("TIMEZONE", "Europe/Berlin")
        local_tz = pytz.timezone(timezone_str)
        
        # Parse recording_date
        try:
            # Versuche zuerst mit Zeit
            if " " in recording_date and "-" in recording_date.split(" ")[1]:
                recording_date_parsed = datetime.strptime(recording_date, "%Y-%m-%d %H-%M")
            else:
                # Nur Datum
                recording_date_parsed = datetime.strptime(recording_date, "%Y-%m-%d")
            recording_date_local = local_tz.localize(recording_date_parsed)
            recording_date_utc = recording_date_local.astimezone(pytz.UTC)
        except ValueError:
            raise HTTPException(status_code=400, detail="recording_date muss im Format YYYY-MM-DD oder YYYY-MM-DD HH-MM sein")
        
        # Extrahiere nur das Datum (ohne Uhrzeit)
        date_only = recording_date_local.date()
        date_start = local_tz.localize(datetime.combine(date_only, datetime.min.time()))
        date_end = local_tz.localize(datetime.combine(date_only, datetime.max.time()))
        date_start_utc = date_start.astimezone(pytz.UTC)
        date_end_utc = date_end.astimezone(pytz.UTC)
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Suche alle Meetings des Tages
        cur.execute("""
            SELECT start_date, end_date, subject, has_picture, user_entry_id, display_to, display_cc
            FROM calendar_data
            WHERE start_date >= %s AND start_date <= %s
            ORDER BY start_date ASC
        """, (date_start_utc, date_end_utc))
        rows = cur.fetchall()
        
        # Formatiere Ergebnisse
        meetings = []
        for row in rows:
            start_date, end_date, subject, has_picture, user_entry_id, display_to, display_cc = row
            
            # Teilnehmernamen kombinieren und deduplizieren
            import re as _re
            tokens = set()
            for field in [display_to, display_cc]:
                if not field:
                    continue
                parts = _re.split(r"[;,]", field)
                for part in parts:
                    words = part.strip().split()
                    for word in words:
                        clean = _re.sub(r"[^\wäöüÄÖÜß-]", "", word)
                        if clean:
                            tokens.add(clean)
            participants = ";".join(sorted(tokens))
            
            meetings.append({
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "subject": subject,
                "location": has_picture,
                "invitation_text": user_entry_id,
                "participants": participants
            })
        
        cur.close()
        conn.close()
        
        return {"status": "success", "meetings": meetings}
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/create-confluence-page")
async def create_confluence_page_endpoint(
    http_request: Request,
    space_name: Optional[str] = Form(None),
    parent_page_title: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    content_format: Optional[str] = Form(None),
    page_title: Optional[str] = Form(None),
    user: Optional[str] = Form(None),
    site_url: Optional[str] = Form(None)
):
    """
    Erstellt eine neue Seite in Confluence über die V2 API.
    
    Unterstützt sowohl JSON (application/json) als auch multipart/form-data.
    
    Steps:
    1. API Key aus .env laden
    2. Auth Header erstellen
    3. Content Format prüfen und ggf. konvertieren
    4. Space ID lookup
    5. Parent Page ID lookup (optional)
    6. Page erstellen
    7. Response zurückgeben
    """
    try:
        # Request-Daten aus JSON oder Form-Data extrahieren
        content_type = http_request.headers.get("content-type", "")
        
        if content_type.startswith("application/json"):
            # JSON-Request
            data = await http_request.json()
            json_request = ConfluencePageRequest(**data)
            
            space_name = json_request.space_name
            parent_page_title = json_request.parent_page_title
            content = json_request.content
            content_format = json_request.content_format
            page_title = json_request.page_title
            user_email = json_request.user  # Kann None sein
            site_url = json_request.site_url
        elif content_type.startswith("multipart/form-data"):
            # Form-Data Request - Parameter werden bereits von FastAPI geparst
            if not space_name:
                raise HTTPException(
                    status_code=400,
                    detail="space_name muss angegeben werden"
                )
            if not content:
                raise HTTPException(
                    status_code=400,
                    detail="content muss angegeben werden"
                )
            if not page_title:
                raise HTTPException(
                    status_code=400,
                    detail="page_title muss angegeben werden"
                )
            if not site_url:
                raise HTTPException(
                    status_code=400,
                    detail="site_url muss angegeben werden"
                )
            # user ist optional, wird aus .env gelesen falls nicht angegeben
            user_email = user  # Kann None sein
            if not content_format:
                content_format = "storage"
        else:
            raise HTTPException(
                status_code=400,
                detail="Content-Type muss application/json oder multipart/form-data sein"
            )
        
        # 1. API Key laden
        api_key = os.getenv("CONFLUENCE_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="CONFLUENCE_API_KEY nicht in .env gefunden"
            )
        
        # 2. Email bestimmen (aus .env oder Parameter, .env hat Priorität wenn beide vorhanden)
        # Wenn user_email im Request angegeben ist, wird es verwendet, sonst aus .env
        email = user_email if user_email else os.getenv("CONFLUENCE_EMAIL")
        if not email:
            raise HTTPException(
                status_code=400,
                detail="User (Email) muss entweder als Parameter 'user' übergeben werden oder in .env als CONFLUENCE_EMAIL gesetzt sein"
            )
        
        # 3. Auth Header erstellen
        auth_header = build_auth_header(email, api_key)
        
        # 4. Content Format prüfen und ggf. konvertieren
        content_format = content_format.lower() if content_format else "storage"
        if content_format not in ["markdown", "storage"]:
            raise HTTPException(
                status_code=400,
                detail="content_format muss 'markdown' oder 'storage' sein"
            )
        
        if content_format == "markdown":
            try:
                confluence_content = convert_markdown_to_storage_format(content)
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Fehler bei Markdown-Konvertierung: {str(e)}"
                )
        else:
            confluence_content = content
        
        # 5. Space ID lookup
        try:
            space_id = get_space_id(site_url, space_name, auth_header)
        except ValueError as e:
            # Space nicht gefunden
            raise HTTPException(
                status_code=404,
                detail=str(e)
            )
        except requests.exceptions.HTTPError as e:
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                error_detail = str(e)
                
                # Versuche mehr Details aus der Response zu extrahieren
                try:
                    error_body = e.response.text
                    if error_body:
                        error_detail += f" - Response: {error_body[:500]}"  # Erste 500 Zeichen
                except:
                    pass
                
                if status_code == 401:
                    raise HTTPException(
                        status_code=401,
                        detail=f"Confluence API Authentifizierung fehlgeschlagen. Bitte prüfe API Key und Email-Adresse. Details: {error_detail}"
                    )
                elif status_code == 403:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Keine Berechtigung für diese Aktion. Details: {error_detail}"
                    )
                elif status_code == 404:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Confluence API Endpoint nicht gefunden. Möglicherweise wird V2 API nicht unterstützt oder die URL ist falsch. Details: {error_detail}"
                    )
                else:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Fehler beim Space Lookup (Status {status_code}): {error_detail}"
                    )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Fehler beim Space Lookup: {str(e)}"
                )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Fehler beim Space Lookup: {str(e)}"
            )
        
        # 6. Parent Page ID lookup (optional)
        parent_id = None
        if parent_page_title:
            try:
                parent_id = get_parent_page_id(
                    site_url,
                    space_id,
                    parent_page_title,
                    auth_header
                )
                if parent_id is None:
                    # Parent Page nicht gefunden, aber kein Fehler (wird als Root-Level erstellt)
                    pass
            except requests.exceptions.HTTPError as e:
                if hasattr(e, 'response') and e.response is not None:
                    if e.response.status_code == 401:
                        raise HTTPException(
                            status_code=401,
                            detail="Confluence API Authentifizierung fehlgeschlagen"
                        )
                    elif e.response.status_code == 403:
                        raise HTTPException(
                            status_code=403,
                            detail="Keine Berechtigung für diese Aktion"
                        )
                # Parent Page nicht gefunden ist kein Fehler
                parent_id = None
            except Exception as e:
                # Bei anderen Fehlern Parent ID auf None setzen
                parent_id = None
        
        # 7. Page erstellen
        try:
            page_response = create_confluence_page(
                site_url,
                space_id,
                page_title,
                confluence_content,
                parent_id,
                auth_header
            )
        except requests.exceptions.HTTPError as e:
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 401:
                    raise HTTPException(
                        status_code=401,
                        detail="Confluence API Authentifizierung fehlgeschlagen"
                    )
                elif e.response.status_code == 403:
                    raise HTTPException(
                        status_code=403,
                        detail="Keine Berechtigung für diese Aktion"
                    )
                elif e.response.status_code == 400:
                    error_detail = "Ungültige Request-Parameter"
                    try:
                        error_data = e.response.json()
                        if "message" in error_data:
                            error_detail = error_data["message"]
                    except:
                        error_detail = e.response.text
                    raise HTTPException(
                        status_code=400,
                        detail=f"Confluence API Fehler: {error_detail}"
                    )
                else:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Confluence API Fehler: {e.response.text}"
                    )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Confluence API Fehler: {str(e)}"
                )
        
        # 8. Response formatieren
        page_url = page_response.get("_links", {}).get("webui", "")
        if page_url and not page_url.startswith("http"):
            # Relativer Pfad, muss mit site_url kombiniert werden
            page_url = f"{site_url}{page_url}"
        
        return {
            "status": "success",
            "page_id": page_response.get("id"),
            "page_title": page_response.get("title"),
            "page_url": page_url,
            "space_id": space_id,
            "parent_id": parent_id,
            "content_format_used": content_format
        }
        
    except HTTPException:
        # HTTPExceptions weiterwerfen
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 