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

APPLE_SCRIPT = '''
-- Verzeichnis des Skripts ermitteln
set scriptPath to (POSIX path of (path to me))
set scriptDir to do shell script "dirname " & quoted form of scriptPath

-- Zielpfad für die XML-Datei im gleichen Verzeichnis wie das Skript
set outputPath to (POSIX file (scriptDir & "/outlook_calendar_export_with_attendees.xml"))

-- XML-Dokument vorbereiten
set xmlContent to "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<calendarEvents>\n"

tell application "Microsoft Outlook"
	set theCalendars to calendars
	repeat with cal in theCalendars
		set calendarItems to calendar events of cal
		repeat with evt in calendarItems
			set evtSubject to subject of evt
			set evtStart to start time of evt
			set evtEnd to end time of evt
			set evtLocation to location of evt
			set evtContent to content of evt

			-- Teilnehmer extrahieren
			set requiredAttendees to required attendees of evt
			set optionalAttendees to optional attendees of evt

			-- Event-Start
			set xmlContent to xmlContent & "  <event>\n"
			set xmlContent to xmlContent & "    <calendar>" & my escapeXML(name of cal) & "</calendar>\n"
			set xmlContent to xmlContent & "    <subject>" & my escapeXML(evtSubject) & "</subject>\n"
			set xmlContent to xmlContent & "    <start>" & (evtStart as string) & "</start>\n"
			set xmlContent to xmlContent & "    <end>" & (evtEnd as string) & "</end>\n"
			set xmlContent to xmlContent & "    <location>" & my escapeXML(evtLocation) & "</location>\n"
			set xmlContent to xmlContent & "    <content>" & my escapeXML(evtContent) & "</content>\n"

			-- Pflichtteilnehmer
			set xmlContent to xmlContent & "    <requiredAttendees>\n"
			repeat with r in requiredAttendees
				set rName to ""
				try
					set rName to name of r
				end try
				set rEmail to ""
				try
					set rEmail to address of r
				end try
				set xmlContent to xmlContent & "      <attendee name=\"" & my escapeXML(rName) & "\" email=\"" & my escapeXML(rEmail) & "\" />\n"
			repeat
			set xmlContent to xmlContent & "    </requiredAttendees>\n"

			-- Optionale Teilnehmer
			set xmlContent to xmlContent & "    <optionalAttendees>\n"
			repeat with o in optionalAttendees
				set oName to ""
				try
					set oName to name of o
				end try
				set oEmail to ""
				try
					set oEmail to address of o
				end try
				set xmlContent to xmlContent & "      <attendee name=\"" & my escapeXML(oName) & "\" email=\"" & my escapeXML(oEmail) & "\" />\n"
			repeat
			set xmlContent to xmlContent & "    </optionalAttendees>\n"

			-- Event-Ende
			set xmlContent to xmlContent & "  </event>\n"
		repeat
	repeat
end tell

-- XML abschließen
set xmlContent to xmlContent & "</calendarEvents>\n"

-- Datei schreiben
do shell script "echo " & quoted form of xmlContent & " > " & quoted form of POSIX path of outputPath

-- XML-Escape-Funktion
on escapeXML(theText)
	if theText is missing value then set theText to ""
	set theText to my replaceText("&", "&amp;", theText)
	set theText to my replaceText("<", "&lt;", theText)
	set theText to my replaceText(">", "&gt;", theText)
	set theText to my replaceText("\"", "&quot;", theText)
	set theText to my replaceText("'", "&apos;", theText)
	return theText
end escapeXML

-- Hilfsfunktion: Text ersetzen
on replaceText(find, replace, textInput)
	set AppleScript's text item delimiters to find
	set textItems to every text item of textInput
	set AppleScript's text item delimiters to replace
	set newText to textItems as string
	set AppleScript's text item delimiters to ""
	return newText
end replaceText
'''

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
        xml_path = Path(tmpdir) / XML_FILENAME
        # AppleScript lokal schreiben
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(APPLE_SCRIPT)
        # SSH-Verbindung aufbauen
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASSWORD)
        with SCPClient(ssh.get_transport()) as scp:
            # Skript auf Host kopieren (z.B. ins Home-Verzeichnis)
            remote_script = f"/Users/{SSH_USER}/export_calendar.scpt"
            remote_xml = f"/Users/{SSH_USER}/{XML_FILENAME}"
            scp.put(str(script_path), remote_script)
            # AppleScript auf Host ausführen
            stdin, stdout, stderr = ssh.exec_command(f"osascript {remote_script}")
            exit_code = stdout.channel.recv_exit_status()
            if exit_code != 0:
                err = stderr.read().decode()
                raise RuntimeError(f"AppleScript-Fehler auf Host: {err}")
            # XML-Datei zurückkopieren
            scp.get(remote_xml, str(xml_path))
            # Aufräumen: Skript und XML auf Host löschen
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