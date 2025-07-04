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
import shutil
from datetime import datetime

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

XML_TARGET_PATH = os.getenv("XML_TARGET_PATH", "/data/ost/outlook_calendar_export_with_attendees.xml")

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
        with open(xml_path, "wb") as f:
            f.write(response.content)
        logger.info(f"Datei gespeichert unter: {xml_path}, Größe: {xml_path.stat().st_size} Bytes")
        # Kopiere die Datei an den Zielpfad
        final_path = Path(XML_TARGET_PATH)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(xml_path, final_path)
        logger.info(f"Datei nach {final_path} kopiert")
        return final_path

def parse_german_datetime(dt_str):
    """
    Parst deutsche Datumsstrings wie 'Montag, 23. Juni 2025 um 14:00:00' zu datetime.
    Gibt None zurück, wenn das Parsen fehlschlägt.
    """
    try:
        if not dt_str:
            return None
        # Entferne Wochentag und "um"
        parts = dt_str.split(',', 1)[-1].replace(' um ', ' ').strip()
        # Ersetze deutschen Monatsnamen durch Zahl
        monate = {
            'Januar': '01', 'Februar': '02', 'März': '03', 'April': '04',
            'Mai': '05', 'Juni': '06', 'Juli': '07', 'August': '08',
            'September': '09', 'Oktober': '10', 'November': '11', 'Dezember': '12'
        }
        for name, num in monate.items():
            if name in parts:
                parts = parts.replace(name, num)
                break
        # Jetzt: '23. 06 2025 14:00:00' oder '23.06 2025 14:00:00'
        # Ersetze doppelten Punkt
        parts = parts.replace('. ', '.')
        # Jetzt: '23.06.2025 14:00:00'
        # Füge Punkt zwischen Tag, Monat und Jahr ein, falls nötig
        tokens = parts.split()
        if len(tokens) == 3 and '.' not in tokens[1]:
            # z.B. ['23.06', '2025', '14:00:00']
            date = f"{tokens[0]}.{tokens[1]}"
            parts = f"{date} {tokens[2]}"
        # Versuche zu parsen
        return datetime.strptime(parts, "%d.%m.%Y %H:%M:%S")
    except Exception as e:
        return None

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
        start_date = parse_german_datetime(start)
        end_date = parse_german_datetime(end)
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