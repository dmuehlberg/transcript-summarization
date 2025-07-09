import os
import psycopg2
from dotenv import load_dotenv
from datetime import datetime
import re
import pytz

load_dotenv()

def get_db_connection():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "postgres"),
        port=os.getenv("DB_PORT", 5432),
        dbname=os.getenv("DB_NAME", "n8n"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "postgres")
    )
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS recipient_names (
            token TEXT PRIMARY KEY
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS manual_terms (
            term TEXT PRIMARY KEY,
            category TEXT,
            note TEXT
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transcriptions (
            id SERIAL PRIMARY KEY,
            filename TEXT UNIQUE,
            transcription_inputpath TEXT,
            recording_date TIMESTAMPTZ,
            detected_language TEXT,
            set_language TEXT,
            transcript_text TEXT,
            corrected_text TEXT,
            participants_firstname TEXT,
            participants_lastname TEXT,
            transcription_duration FLOAT,
            audio_duration FLOAT,
            created_at TIMESTAMP,
            transcription_status TEXT,
            participants TEXT,
            meeting_start_date TIMESTAMPTZ,
            meeting_end_date TIMESTAMPTZ,
            meeting_title TEXT,
            meeting_location TEXT,
            invitation_text TEXT
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

def upsert_transcription(data):
    data = data.copy()
    filepath = data.pop("filepath")
    data["filename"] = os.path.basename(filepath)
    data["transcription_inputpath"] = filepath  # kompletter Pfad inkl. Dateiname
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO transcriptions (
            filename, transcription_inputpath, recording_date, detected_language, set_language, transcript_text, corrected_text,
            participants_firstname, participants_lastname, transcription_duration, audio_duration, created_at, transcription_status, participants
        ) VALUES (
            %(filename)s, %(transcription_inputpath)s, %(recording_date)s, %(detected_language)s, %(set_language)s, %(transcript_text)s, %(corrected_text)s,
            %(participants_firstname)s, %(participants_lastname)s, %(transcription_duration)s, %(audio_duration)s, %(created_at)s, %(transcription_status)s, %(participants)s
        )
        ON CONFLICT (filename) DO UPDATE SET
            transcription_inputpath = EXCLUDED.transcription_inputpath,
            recording_date = EXCLUDED.recording_date,
            detected_language = EXCLUDED.detected_language,
            set_language = EXCLUDED.set_language,
            transcript_text = EXCLUDED.transcript_text,
            corrected_text = EXCLUDED.corrected_text,
            participants_firstname = EXCLUDED.participants_firstname,
            participants_lastname = EXCLUDED.participants_lastname,
            transcription_duration = EXCLUDED.transcription_duration,
            audio_duration = EXCLUDED.audio_duration,
            created_at = EXCLUDED.created_at,
            transcription_status = EXCLUDED.transcription_status,
            participants = EXCLUDED.participants;
    """, data)
    conn.commit()
    cur.close()
    conn.close()

def upsert_mp3_file(filepath):
    filename = os.path.basename(filepath)
    transcription_inputpath = filepath  # kompletter Pfad inkl. Dateiname
    
    # Zeitzone aus .env laden
    timezone_str = os.getenv("TIMEZONE", "Europe/Berlin")
    local_tz = pytz.timezone(timezone_str)
    
    # Zeitstempel aus Dateiname extrahieren
    base_name = os.path.splitext(filename)[0]
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
    
    conn = get_db_connection()
    cur = conn.cursor()
    # Falls vorhanden, alten Eintrag löschen
    cur.execute("DELETE FROM transcriptions WHERE filename = %s", (filename,))
    # Neuen Eintrag anlegen
    cur.execute("""
        INSERT INTO transcriptions (
            filename, transcription_inputpath, recording_date, detected_language, set_language, transcript_text, corrected_text,
            participants_firstname, participants_lastname, transcription_duration, audio_duration, created_at, transcription_status, participants
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
    """, (
        filename,
        transcription_inputpath,
        recording_date,  # Jetzt mit Zeitzoneninformation
        None,  # detected_language
        None,  # set_language
        None,  # transcript_text
        None,  # corrected_text
        None,  # participants_firstname
        None,  # participants_lastname
        None,  # transcription_duration
        None,  # audio_duration
        datetime.utcnow(),
        "pending",  # Initial status for new files
        None  # participants
    ))
    conn.commit()
    cur.close()
    conn.close()

def update_transcription_meeting_info(recording_date, info_dict):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # recording_date ist jetzt bereits mit Zeitzoneninformation
    # Wir verwenden es direkt für die Suche
    recording_date_for_search = recording_date
    
    # Erweitere die Suche um +/- 5 Minuten für flexiblere Zuordnung
    from datetime import timedelta
    time_window_start = recording_date_for_search - timedelta(minutes=5)
    time_window_end = recording_date_for_search + timedelta(minutes=5)
    
    # Update-Statement für die neuen Felder und participants
    # Verwende das gleiche Zeitfenster wie in get_meeting_info
    cur.execute("""
        UPDATE transcriptions
        SET meeting_start_date = %s,
            meeting_end_date = %s,
            meeting_title = %s,
            meeting_location = %s,
            invitation_text = %s,
            participants = %s
        WHERE recording_date BETWEEN %s AND %s
    """, (
        info_dict.get("meeting_start_date"),
        info_dict.get("meeting_end_date"),
        info_dict.get("meeting_title"),
        info_dict.get("meeting_location"),
        info_dict.get("invitation_text"),
        info_dict.get("participants"),
        time_window_start,
        time_window_end
    ))
    conn.commit()
    cur.close()
    conn.close() 