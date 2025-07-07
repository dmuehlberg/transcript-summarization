import os
from dotenv import load_dotenv
from urllib.parse import urlparse

# Lade Umgebungsvariablen
load_dotenv()

def get_db_config():
    """Gibt die Datenbankkonfiguration zurück."""
    # Versuche zuerst die DATABASE_URL zu verwenden
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        # Parse die URL
        parsed = urlparse(database_url)
        return {
            "host": parsed.hostname,
            "port": parsed.port or 5432,
            "database": parsed.path.lstrip('/'),
            "user": parsed.username,
            "password": parsed.password
        }
    
    # Fallback auf einzelne Umgebungsvariablen
    return {
        "host": os.getenv("DB_HOST", "db"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "database": os.getenv("DB_NAME", "xstexport"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", "postgres")
    } 