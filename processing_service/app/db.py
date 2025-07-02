import os
import psycopg2
from dotenv import load_dotenv
from datetime import datetime
import re

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
            recording_date TIMESTAMP,
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
            participants TEXT
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
    
    # Zeitstempel aus Dateiname extrahieren
    base_name = os.path.splitext(filename)[0]
    m = re.match(r"(\d{4}-\d{2}-\d{2}) (\d{2}-\d{2}-\d{2})", base_name)
    if m:
        date_str = m.group(1) + " " + m.group(2).replace("-", ":")
        try:
            recording_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            recording_date = datetime.utcnow()
    else:
        recording_date = datetime.utcnow()
    
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
        recording_date,  # Jetzt verwenden wir das extrahierte Datum
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