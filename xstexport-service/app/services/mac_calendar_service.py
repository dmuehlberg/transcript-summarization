import os
import subprocess
from pathlib import Path
import xml.etree.ElementTree as ET
import pandas as pd
from typing import List, Dict, Any
import tempfile
import paramiko
from scp import SCPClient
import requests

EXPORT_SCRIPT = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))) / "export_calendar.scpt"
EXPORT_RESULT = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))) / "outlook_calendar_export_with_attendees.xml"

APPLE_SCRIPT_PATH = "/app/export_calendar.scpt"

# Der Name der XML-Datei, wie im Skript verwendet
XML_FILENAME = "outlook_calendar_export_with_attendees.xml"

SSH_USER = os.getenv("SSH_USER")
SSH_PASSWORD = os.getenv("SSH_PASSWORD")
SSH_HOST = os.getenv("SSH_HOST", "host.docker.internal")
SSH_PORT = 22

PROXY_URL = os.getenv("APPLE_PROXY_URL", "http://host.docker.internal:5001/run-applescript")

def run_applescript() -> Path:
    import tempfile
    from pathlib import Path
    import logging
    logger = logging.getLogger(__name__)
    with tempfile.TemporaryDirectory() as tmpdir:
        xml_path = Path(tmpdir) / XML_FILENAME
        response = requests.post(PROXY_URL)
        logger.info(f"Proxy-Service Status: {response.status_code}")
        logger.info(f"Proxy-Service Content-Type: {response.headers.get('Content-Type')}")
        if response.status_code != 200:
            logger.error(f"Proxy-Service Fehler: {response.text}")
            raise RuntimeError(f"Proxy-Service Fehler: {response.text}")
        logger.info(f"Empfangene Dateigröße: {len(response.content)} Bytes")
        with open(xml_path, \"wb\") as f:
            f.write(response.content)
        logger.info(f\"Datei gespeichert unter: {xml_path}, Größe: {xml_path.stat().st_size} Bytes\")
        return xml_path

def parse_calendar_xml(xml_path: Path) -> List[Dict[str, Any]]:
    """
    Parst die XML-Datei und gibt eine Liste von Event-Dictionaries zurück.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    events = []
    for event in root.findall(".//event"):
        calendar = event.findtext("calendar", "")
        subject = event.findtext("subject", "")
        start = event.findtext("start", "")
        end = event.findtext("end", "")
        location = event.findtext("location", "")
        content = event.findtext("content", "")
        required = event.findtext("requiredAttendees", "")
        optional = event.findtext("optionalAttendees", "")
        # Datumsfelder konvertieren
        start_date = pd.to_datetime(start, errors='coerce')
        end_date = pd.to_datetime(end, errors='coerce')
        # Attendees als Strings
        display_to = required if required else ""
        display_cc = optional if optional else ""
        # Dummy-Felder für Kompatibilität
        has_picture = ""
        user_entry_id = ""
        events.append({
            "calendar": calendar,
            "subject": subject,
            "start_date": start_date,
            "end_date": end_date,
            "has_picture": has_picture,
            "user_entry_id": user_entry_id,
            "display_to": display_to,
            "display_cc": display_cc
        })
    return events 