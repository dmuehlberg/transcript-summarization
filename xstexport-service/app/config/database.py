import os
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from urllib.parse import urlparse

# Lade Umgebungsvariablen
load_dotenv()

logger = logging.getLogger(__name__)

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

def get_ollama_config(db_service: Optional[Any] = None) -> Dict[str, Any]:
    """
    Gibt die Ollama-Konfiguration zurück.
    Liest aws_host aus der Datenbank, falls db_service übergeben wird.
    
    Args:
        db_service: Optionaler DatabaseService zum Lesen aus der DB
    
    Returns:
        Dictionary mit 'base_url', 'model' und 'timeout'
    """
    base_url = None
    
    # Versuche zuerst aus Datenbank zu lesen
    if db_service is not None:
        try:
            aws_host = db_service.get_transcription_setting("aws_host")
            if aws_host:
                # Entferne http:// oder https:// falls vorhanden
                aws_host = aws_host.replace("http://", "").replace("https://", "").strip()
                # Entferne Port falls vorhanden
                if ":" in aws_host:
                    aws_host = aws_host.split(":")[0]
                base_url = f"http://{aws_host}:11434"
                logger.info(f"Ollama-Host aus Datenbank gelesen: {base_url}")
        except Exception as e:
            logger.warning(f"Fehler beim Lesen des aws_host aus der DB: {str(e)}, verwende Fallback")
    
    # Fallback auf .env oder Standard
    if base_url is None:
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        logger.info(f"Ollama-Host aus .env/Standard verwendet: {base_url}")
    
    # Timeout aus .env lesen mit Fallback auf 30 Sekunden
    timeout_str = os.getenv("OLLAMA_TIMEOUT", "30")
    try:
        timeout = float(timeout_str)
        logger.info(f"OLLAMA_TIMEOUT aus Umgebungsvariable gelesen: {timeout} Sekunden")
    except (ValueError, TypeError):
        logger.warning(f"Ungültiger OLLAMA_TIMEOUT-Wert '{timeout_str}', verwende Fallback 30.0")
        timeout = 30.0
    
    return {
        "base_url": base_url,
        "model": os.getenv("OLLAMA_MODEL", "phi4-mini:3.8b"),
        "timeout": timeout
    } 