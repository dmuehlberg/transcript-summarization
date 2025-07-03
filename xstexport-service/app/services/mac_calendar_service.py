import os
import subprocess
from pathlib import Path
import xml.etree.ElementTree as ET
import pandas as pd
from typing import List, Dict, Any
import tempfile
import paramiko
from scp import SCPClient

EXPORT_SCRIPT = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))) / "export_calendar.scpt"
EXPORT_RESULT = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))) / "outlook_calendar_export_with_attendees.xml"

APPLE_SCRIPT_PATH = "/app/export_calendar.scpt"

# Der Name der XML-Datei, wie im Skript verwendet
XML_FILENAME = "outlook_calendar_export_with_attendees.xml"

SSH_USER = os.getenv("SSH_USER")
SSH_PASSWORD = os.getenv("SSH_PASSWORD")
SSH_HOST = os.getenv("SSH_HOST", "host.docker.internal")
SSH_PORT = 22

def run_applescript() -> Path:
    """
    Überträgt das AppleScript per SSH auf den Host, führt es dort aus und kopiert die XML-Datei zurück.
    """
    if not SSH_USER or not SSH_PASSWORD or not SSH_HOST:
        raise RuntimeError("SSH-Umgebungsvariablen (SSH_USER, SSH_PASSWORD, SSH_HOST) müssen gesetzt sein!")
    with tempfile.TemporaryDirectory() as tmpdir:
        script_path = Path(tmpdir) / "export_calendar.scpt"
        # Skript aus Datei lesen und ins temp kopieren
        with open(APPLE_SCRIPT_PATH, "r", encoding="utf-8") as src, open(script_path, "w", encoding="utf-8") as dst:
            dst.write(src.read())
        xml_path = Path(tmpdir) / XML_FILENAME
        # SSH-Verbindung aufbauen
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASSWORD)
        with SCPClient(ssh.get_transport()) as scp:
            remote_script = f"/Users/{SSH_USER}/export_calendar.scpt"
            remote_xml = f"/Users/{SSH_USER}/{XML_FILENAME}"
            scp.put(str(script_path), remote_script)
            stdin, stdout, stderr = ssh.exec_command(f"osascript {remote_script}")
            exit_code = stdout.channel.recv_exit_status()
            if exit_code != 0:
                err = stderr.read().decode()
                raise RuntimeError(f"AppleScript-Fehler auf Host: {err}")
            scp.get(remote_xml, str(xml_path))
            ssh.exec_command(f"rm {remote_script} {remote_xml}")
        ssh.close()
        if not xml_path.exists():
            raise FileNotFoundError(f"Exportierte XML nicht gefunden: {xml_path}")
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