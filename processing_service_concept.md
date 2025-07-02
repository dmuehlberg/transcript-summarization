Erweitere den FastAPI-Service processing_service, sodass Meeting-Informationen aus calendar_data in die Tabelle transcriptions geschrieben werden können. Diese Tabelle enthält bisher nur grundlegende Metadaten hochgeladener MP3-Transkripte.

1. Datenbankschema
Füge folgende Spalten zur Tabelle transcriptions hinzu:

meeting_start_date TIMESTAMPTZ
meeting_end_date   TIMESTAMPTZ
meeting_title      TEXT
meeting_location   TEXT
invitation_text    TEXT
Aktualisiere init_db() in processing_service/app/db.py, damit diese Felder beim Start des Services erstellt werden. 

2. Hilfsfunktion für Meeting-Info-Update
Erstelle eine neue Funktion in db.py, z. B. update_transcription_meeting_info(recording_date, info_dict):

Nutze recording_date, um die passende Zeile in transcriptions zu finden.

Aktualisiere die neuen Meeting-Spalten sowie die vorhandene participants-Spalte.

Commit und Schließen der Verbindung.

3. Neuer API-Endpoint
Implementiere in processing_service/app/main.py einen Endpoint (POST /get_meeting_info), der einen JSON-Body erwartet:

{ "recording_date": "2024-05-01 10-30" }
Vorgehensweise:

Timestamp parsen.

In calendar_data nach einem Eintrag suchen, dessen start_date diesem Timestamp entspricht.

Falls gefunden, Meeting-Informationen sammeln:

start_date → meeting_start_date

end_date → meeting_end_date

subject → meeting_title

has_picture → meeting_location

user_entry_id → invitation_text

Namen aus display_to und display_cc kombinieren, an ;/, trennen, deduplizieren → participants.

Mit diesen Werten update_transcription_meeting_info() aufrufen.

Erfolg oder 404 zurückgeben, falls nichts gefunden wurde.

Verwende zum Deduplizieren die Logik aus sync_recipient_names.

4. Registrierung des Endpoints
Füge die neue Route nach den bestehenden Endpoints in main.py (ca. Zeile 97) hinzu. Stelle sicher, dass die Datenbank beim Start initialisiert wird (bereits in on_startup() erledigt).

So kann der n8n-Workflow nach jeder Transkription den Kontext für die Meeting-Zusammenfassung anhand des Zeitstempels aus dem MP3-Dateinamen anreichern.