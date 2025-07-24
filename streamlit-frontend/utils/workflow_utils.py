"""
Workflow-Utilities für n8n API-Calls.
"""
import requests
import logging
import os
from typing import Dict, Any, Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time

# Logger konfigurieren
logger = logging.getLogger(__name__)

class N8nWorkflowClient:
    """Client für n8n Workflow-API-Calls."""
    
    def __init__(self, base_url: str = "http://n8n:5678", timeout: int = 30):
        """Initialisiert den n8n Workflow Client."""
        self.base_url = base_url
        self.timeout = timeout
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Erstellt eine Session mit Retry-Logic."""
        session = requests.Session()
        
        # Retry-Strategie konfigurieren
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def start_transcription_workflow(self) -> Dict[str, Any]:
        """
        Startet den Transcription Workflow über n8n Webhook.
        
        Returns:
            Dict mit Status und Message
        """
        try:
            url = f"{self.base_url}/webhook/start-transcription"
            logger.info(f"Starte Transcription Workflow: {url}")
            
            response = self.session.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                logger.info("Transcription Workflow erfolgreich gestartet")
                return {
                    "success": True,
                    "message": "Transcription Workflow erfolgreich gestartet",
                    "status_code": response.status_code
                }
            else:
                logger.error(f"Workflow-Start fehlgeschlagen: {response.status_code}")
                return {
                    "success": False,
                    "message": f"Workflow-Start fehlgeschlagen: HTTP {response.status_code}",
                    "status_code": response.status_code
                }
                
        except requests.exceptions.Timeout:
            logger.error("Timeout beim Starten des Workflows")
            return {
                "success": False,
                "message": "Timeout beim Starten des Workflows",
                "status_code": None
            }
        except requests.exceptions.ConnectionError:
            logger.error("Verbindungsfehler zu n8n")
            return {
                "success": False,
                "message": "Verbindungsfehler zu n8n - Service nicht erreichbar",
                "status_code": None
            }
        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim Workflow-Start: {e}")
            return {
                "success": False,
                "message": f"Unerwarteter Fehler: {str(e)}",
                "status_code": None
            }
    
    def test_connection(self) -> bool:
        """Testet die Verbindung zu n8n."""
        try:
            response = self.session.get(f"{self.base_url}/", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"n8n Verbindungstest fehlgeschlagen: {e}")
            return False
    
    def close(self) -> None:
        """Schließt die Session."""
        self.session.close()

# Globale Instanz des n8n Clients (nur erstellen wenn nicht in Test-Umgebung)
if not os.getenv('TESTING'):
    n8n_client = N8nWorkflowClient()
else:
    n8n_client = None 