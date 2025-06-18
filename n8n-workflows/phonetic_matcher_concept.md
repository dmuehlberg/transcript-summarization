Hier ist dein vollständig integriertes und aktualisiertes Konzept mit dem Zusatz zur automatischen Befüllung von recipient_names aus calendar_data, sauber eingebettet in die bestehende Struktur.

⸻

🧾 Ziel & thematischer Kontext (für Cursor)

Du entwickelst einen FastAPI-Webservice, der innerhalb eines bestehenden Projekts (transcript-summarization) läuft.
Der Dienst soll ein Transkript (Text) entgegennehmen und es phonetisch analysieren, um Namen und Begriffe anhand einer Referenzliste in einer PostgreSQL-Datenbank zu korrigieren.

Die Korrekturen erfolgen auf Basis phonetischer Ähnlichkeit (Cologne oder Metaphone) mit optionalem Fuzzy-Matching.

Zusätzlich sollen Empfängernamen automatisch aus der Tabelle calendar_data extrahiert und in die Matching-Tabelle recipient_names übernommen werden. Diese Extraktion erfolgt automatisch vor dem Matching-Prozess bei jedem API-Aufruf.

Die Referenzliste besteht aus zwei Datenquellen:
	1.	recipient_names: automatisch generierte Liste von Namen aus calendar_data (Felder: sender_name, display_to, display_cc)
	2.	manual_terms: händisch gepflegte Liste von Fachbegriffen (später per Web-UI verwaltbar)

⸻

🛠️ Systemdetails
	•	Framework: FastAPI
	•	Datenbank: PostgreSQL (läuft im selben Docker-Netzwerk)
	•	DB-Zugang:
	•	Host: postgres
	•	Port: 5432
	•	DB-Name: n8n
	•	User: root
	•	Passwort: postgres
	•	Service-Name in docker-compose: phonetic-matcher
	•	Bestehende Struktur: Wird in das Projekt transcript-summarization integriert

⸻

🔧 API-Spezifikation

🔹 Endpoint

POST /correct-transcript

📥 Request Body

{
  "language": "de",
  "transcript": "Hallo, ich bin der Herr Smidt und spreche mit Frau Meyr.",
  "options": {
    "match_type": "phonetic_first",
    "include_manual_list": true,
    "min_score": 80
  }
}

📤 Response

{
  "corrected_transcript": "Hallo, ich bin der Herr Schmidt und spreche mit Frau Meier.",
  "matches": [
    {
      "original": "Smidt",
      "corrected": "Schmidt",
      "match_type": "phonetic",
      "score": null,
      "source": "recipient_names"
    },
    {
      "original": "Meyr",
      "corrected": "Meier",
      "match_type": "fuzzy",
      "score": 91,
      "source": "manual_terms"
    }
  ],
  "language": "de"
}


⸻

✅ Cursor-Anweisung: Schritt-für-Schritt-Implementierung

📌 Ziel: Baue einen FastAPI-Service namens phonetic_matcher, der in transcript-summarization integriert wird und die oben spezifizierte Funktionalität abbildet. Verwende Postgres für den Datenzugriff, führe ein tokenbasiertes phonetisches Matching durch und ersetze erkannte Begriffe im Transkript.

⸻

🔷 1. Projektstruktur

Im Hauptprojektverzeichnis transcript-summarization/:

mkdir phonetic_matcher
cd phonetic_matcher

Dann:

phonetic_matcher/
├── app/
│   ├── main.py
│   ├── matcher.py
│   ├── transcript.py
│   ├── db.py
│   ├── sync.py            ◀️ enthält Logik zum Auffüllen von recipient_names
│   ├── models.py
│   └── config.py
├── requirements.txt
├── Dockerfile


⸻

🔷 2. requirements.txt

fastapi
uvicorn
psycopg2-binary
pyphonetics
jellyfish
rapidfuzz
python-dotenv


⸻

🔷 3. Dockerfile

FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]


⸻

🔷 4. .env Datei erweitern (im Projektroot, wird bereits verwendet)

DB_HOST=postgres
DB_PORT=5432
DB_NAME=n8n
DB_USER=root
DB_PASSWORD=postgres


⸻

🔷 5. docker-compose.yml erweitern

services:
  phonetic-matcher:
    build:
      context: ./phonetic_matcher
    container_name: phonetic_matcher
    ports:
      - "8080:8080"
    env_file:
      - .env
    depends_on:
      - postgres


⸻

🔷 6. Datenbanktabellen

🔹 recipient_names

CREATE TABLE recipient_names (name TEXT);

🔹 manual_terms

CREATE TABLE manual_terms (term TEXT, category TEXT, note TEXT);


⸻

🔷 7. Automatische Extraktion aus calendar_data

Implementiere eine Funktion sync_recipient_names() in sync.py, die:
	1.	Aus der bestehenden Tabelle calendar_data die Spalten sender_name, display_to, display_cc liest
	2.	Strings in display_to und display_cc auftrennt (z. B. per ; oder ,)
	3.	Alle Namen cleaned und dedupliziert
	4.	Die Einträge in recipient_names schreibt (ggf. vorher TRUNCATE)

Diese Funktion wird bei jedem API-Aufruf von /correct-transcript vor dem Matching ausgeführt.

⸻

🔷 8. API-Endpunkt: main.py

Erstelle den POST-Endpunkt /correct-transcript, der:
	1.	sync_recipient_names() ausführt
	2.	das Transkript tokenisiert
	3.	jedes Token gegen recipient_names und optional manual_terms vergleicht
	4.	erkannte Begriffe ersetzt und das Ergebnis zurückgibt

⸻

🔷 9. Matching-Logik
	•	Cologne für Deutsch (pyphonetics)
	•	Metaphone für Englisch (jellyfish)
	•	Optional: Fuzzy-Fallback mit rapidfuzz
	•	Matching nur gegen Begriffe aus der DB (recipient_names + optional manual_terms)
	•	Ergebnisse inklusive: original, corrected, match_type, score, source

⸻

🔷 10. Rückgabeformat

Siehe Abschnitt “Response” weiter oben.
Gebe das korrigierte Transkript + alle Änderungen als Liste zurück.

⸻

🟩 Bonus (optional)
	•	Einheitliches Error-Handling für 400 / 422 / 500
	•	Beispiel-Request via Swagger UI oder curl-Snippet
	•	Endpunkt /sync-now zum manuellen Aktualisieren von recipient_names

⸻

✅ Ausgabe

Der Service soll lokal über http://localhost:8080/correct-transcript erreichbar sein und die Empfängerinformationen automatisch aus der Tabelle calendar_data extrahieren und verarbeiten.

⸻

🟢 Cursor kann mit dieser Spezifikation sofort loslegen.
Wenn du möchtest, fasse ich sie dir direkt als Markdown-Datei zusammen (SPEC.md) für dein Repo.