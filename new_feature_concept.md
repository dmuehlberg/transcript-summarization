Implementierungskonzept für den „CSV-Import-Endpoint“

Bestehende Funktionalität prüfen

Der Service xstexport-service importiert bereits Kalenderdaten aus PST/OST/ZIP-Dateien über /extract-calendar-from-file.

Die Logik zum Importieren in die Datenbank befindet sich in app/services/db_service.py (import_csv_to_db und read_csv_safely).

Es gibt derzeit keinen Endpoint für den direkten CSV-Upload.

Endpoint-Design

Route: POST /import-calendar-csv

Parameter (multipart form):

file: hochgeladene CSV-Datei (UploadFile).

Optionales table_name (Form, standardmäßig "calendar_data").

Ablauf:

Prüfen, ob file angegeben ist und auf .csv endet.

Datei in einem temporären Ordner speichern (tempfile.mkdtemp() verwenden).

db_service.import_csv_to_db(temp_file_path, table_name) aufrufen, um die Tabelle zu leeren und zu importieren.

Bei Erfolg eine JSON-Statusmeldung zurückgeben.

Temporäres Verzeichnis aufräumen.

Implementierungsschritte

Neue Funktion in app/main.py erstellen:

@app.post("/import-calendar-csv")
async def import_calendar_csv(
    file: UploadFile = File(...),
    table_name: str = Form("calendar_data")
):
    # Validierung und temporäres Speichern
    # db_service.import_csv_to_db aufrufen
    # JSONResponse({"status": "success"}) zurückgeben
Fehlerbehandlung analog zu den anderen Endpoints (HTTPException bei Fehlern) und sicherstellen, dass der File-Handle im finally geschlossen wird.

Vorhandenes Logging nutzen (logger.info usw.).

Dokumentation

README um die Nutzung des neuen Endpoints und seine Parameter (inklusive Beispiel curl-Befehl) erweitern oder neu erstellen.

Testvorschläge

Eine bereits von /extract-calendar-from-file erzeugte CSV-Datei verwenden, um den Import in die Datenbank zu testen.

Überprüfen, dass die Tabelle geleert und korrekt gefüllt wird.

Dieses Konzept kann als direkte Anweisung für den Cursor-Agenten dienen, um den neuen Endpoint hinzuzufügen.