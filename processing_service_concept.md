Bitte erweitere den bestehenden FastAPI-Service processing-service im Projekt transcript_summarization um folgende Funktionalität:

⸻

🧩 Neuer Endpoint: /update_transcript_data

Implementiere einen neuen POST-Endpoint /update_transcript_data, der das Verzeichnis
/shared/transcription_finished durchsucht und dort alle .json- und .txt-Paare verarbeitet.

Dateibenennung:
Die Dateien folgen dem Muster YYYY-MM-DD HH-MM-SS.txt bzw. .json. Aus dem Dateinamen soll ein Zeitstempel (recording_date) extrahiert werden. Falls dieser nicht extrahiert werden kann, verwende datetime.now().

⸻

📂 Was soll eingelesen werden?

Für jede Transkription existieren:
	•	eine .txt-Datei mit dem Transkriptions-Text
	•	eine .json-Datei mit dem gleichen Basisnamen, die folgendes enthält:
	•	metadata.language → detected_language
	•	metadata.duration → transcription_duration
	•	metadata.audio_duration → audio_duration

Verwende die JSON-Struktur aus folgendem Beispiel als Referenz:
Die JSON-Datei enthält ein Array mit einem Objekt (also Zugriff auf [0]).

⸻

🗄️ PostgreSQL-Tabelle: transcriptions

Beim Start des processing-service soll geprüft werden, ob die Tabelle transcriptions existiert. Falls nicht, erstelle sie mit folgendem Schema:

Spalte	Typ	Beschreibung
id	SERIAL PRIMARY KEY	Eindeutiger Identifier
filepath	TEXT	Pfad zur .txt-Datei
recording_date	TIMESTAMP	Extrahierter oder aktueller Zeitstempel
detected_language	TEXT	Aus JSON (metadata.language)
set_language	TEXT	Manuell auswählbare Sprache (initial NULL)
transcript_text	TEXT	Inhalt der .txt-Datei
corrected_text	TEXT	Text nach phonetischer Korrektur (initial leer)
participants_firstname	TEXT	Vornamen, kommasepariert (initial leer)
participants_lastname	TEXT	Nachnamen, kommasepariert (initial leer)
transcription_duration	FLOAT	Aus JSON (metadata.duration)
audio_duration	FLOAT	Aus JSON (metadata.audio_duration)
created_at	TIMESTAMP	Zeitstempel des DB-Eintrags (jetzt)

Wenn ein Datensatz mit identischem filepath bereits existiert, überschreibe ihn.

⸻

🧾 Verarbeitungsschritte
	1.	Liste alle .json-Dateien in /shared/transcription_finished auf.
	2.	Für jede .json-Datei:
	•	Extrahiere den Basenamen (ohne Endung)
	•	Lade zugehörige .txt-Datei
	•	Lade die JSON-Datei (Array-Zugriff: [0])
	•	Extrahiere:
	•	metadata.language
	•	metadata.duration
	•	metadata.audio_duration
	•	Analysiere Dateinamen zur Bestimmung von recording_date
	•	Schreibe oder überschreibe den Datensatz in der Tabelle transcriptions

⸻

🌐 Budibase-Integration

Ergänze die docker-compose.yml im Projekt-Root um folgenden Budibase-Container:

  budibase:
    image: budibase/budibase:latest
    ports:
      - "8400:80"
    environment:
      - INTERNAL_POSTGRES_ENABLED=false
    depends_on:
      - postgres

Budibase soll Zugriff auf dieselbe PostgreSQL-Datenbank wie n8n haben.
Das Feld set_language in der Tabelle transcriptions soll in Budibase als Dropdown-Feld mit den Werten de und en editierbar sein.

⸻

🛠 Technische Hinweise
	•	Verwende SQLAlchemy oder psycopg2 für den Datenbankzugriff
	•	Dateinamen-Parsing z. B. mit Regex: (\d{4}-\d{2}-\d{2}) (\d{2}-\d{2}-\d{2})
	•	Füge bei jedem Eintrag ein created_at = datetime.utcnow() hinzu
	•	Nutze UTF-8 beim Einlesen der .txt-Dateien

⸻

Setze die komplette Funktionalität in processing-service um. Integriere den neuen Endpoint in die vorhandene main.py oder router.py. Ergänze ggf. eine neue Datei db.py oder schema.py für das Tabellenmodell.