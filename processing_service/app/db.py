import os
import psycopg2
from dotenv import load_dotenv

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
    conn.commit()
    cur.close()
    conn.close() 