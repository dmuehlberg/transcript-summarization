import os
import psycopg2
from dotenv import load_dotenv
from datetime import datetime

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
            recording_date TIMESTAMP,
            detected_language TEXT,
            set_language TEXT,
            transcript_text TEXT,
            corrected_text TEXT,
            participants_firstname TEXT,
            participants_lastname TEXT,
            transcription_duration FLOAT,
            audio_duration FLOAT,
            created_at TIMESTAMP
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

def upsert_transcription(data):
    data = data.copy()
    # Nur Dateiname speichern
    data["filename"] = os.path.basename(data.pop("filepath"))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO transcriptions (
            filename, recording_date, detected_language, set_language, transcript_text, corrected_text,
            participants_firstname, participants_lastname, transcription_duration, audio_duration, created_at
        ) VALUES (
            %(filename)s, %(recording_date)s, %(detected_language)s, %(set_language)s, %(transcript_text)s, %(corrected_text)s,
            %(participants_firstname)s, %(participants_lastname)s, %(transcription_duration)s, %(audio_duration)s, %(created_at)s
        )
        ON CONFLICT (filename) DO UPDATE SET
            recording_date = EXCLUDED.recording_date,
            detected_language = EXCLUDED.detected_language,
            set_language = EXCLUDED.set_language,
            transcript_text = EXCLUDED.transcript_text,
            corrected_text = EXCLUDED.corrected_text,
            participants_firstname = EXCLUDED.participants_firstname,
            participants_lastname = EXCLUDED.participants_lastname,
            transcription_duration = EXCLUDED.transcription_duration,
            audio_duration = EXCLUDED.audio_duration,
            created_at = EXCLUDED.created_at;
    """, data)
    conn.commit()
    cur.close()
    conn.close()

def upsert_mp3_file(filepath):
    filename = os.path.basename(filepath)
    conn = get_db_connection()
    cur = conn.cursor()
    # Falls vorhanden, alten Eintrag löschen
    cur.execute("DELETE FROM transcriptions WHERE filename = %s", (filename,))
    # Neuen Eintrag anlegen
    cur.execute("""
        INSERT INTO transcriptions (
            filename, recording_date, detected_language, set_language, transcript_text, corrected_text,
            participants_firstname, participants_lastname, transcription_duration, audio_duration, created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
    """, (
        filename,
        datetime.utcnow(),  # Aufnahmezeitpunkt unbekannt, daher jetzt
        None,  # detected_language
        None,  # set_language
        None,  # transcript_text
        None,  # corrected_text
        None,  # participants_firstname
        None,  # participants_lastname
        None,  # transcription_duration
        None,  # audio_duration
        datetime.utcnow(),
    ))
    conn.commit()
    cur.close()
    conn.close() 