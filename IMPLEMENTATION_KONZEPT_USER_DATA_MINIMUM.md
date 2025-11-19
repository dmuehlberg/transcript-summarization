# Implementierungskonzept: User-Data auf Minimum reduzieren

## Problem-Analyse

**Aktuelle Situation:**
- User-Data Größe: **17.483 Bytes** (überschreitet AWS-Limit von 16.384 Bytes um ~1.100 Bytes)
- Größte Blöcke:
  - Docker Volume Migration: **8.421 Bytes** (48% des gesamten Skripts!)
  - Docker Compose Setup: **820 Bytes**
  - Repository + .env: **920 Bytes**
  - install_services.sh Erstellung: **142 Bytes** (aber das Skript selbst ist ~4 KB)

## Lösung: Drei-Stufen-Architektur

### Strategie

1. **User-Data (Phase 1)**: Nur absolutes Minimum - Docker-Setup + Repository-Klon
2. **Bootstrap-Skripte (Phase 2)**: Werden vom Repository geladen und ausgeführt
3. **Services-Installation (Phase 3)**: Läuft im Hintergrund

### Neue Architektur

```
User-Data (Phase 1)
├── System-Initialisierung
├── Git, Tools Installation
├── Docker Installation
├── Repository klonen
├── .env-Datei erstellen
└── Bootstrap-Skripte laden und starten
    ├── setup-docker-volume.sh (vom Repository)
    └── install-services.sh (vom Repository)
```

## Detaillierte Implementierung

### Phase 1: User-Data (muss < 16 KB sein)

**Enthält nur:**
- System-Initialisierung (~200 Bytes)
- Git, htop, nano, mc Installation (~300 Bytes)
- Docker Installation (~500 Bytes)
- Repository klonen (~400 Bytes)
- .env-Datei erstellen (~300 Bytes)
- Bootstrap-Skripte laden und starten (~500 Bytes)

**Geschätzte Größe:** ~2.200 Bytes ✅ (deutlich unter Limit!)

**Entfernt aus User-Data:**
- ❌ Docker Volume Migration (8.421 Bytes) → wird in `setup-docker-volume.sh` ausgelagert
- ❌ Docker Compose Installation (820 Bytes) → wird in `setup-docker-volume.sh` oder `install-services.sh` verschoben
- ❌ install_services.sh Inline-Erstellung (142 Bytes + ~4 KB Inhalt) → wird vom Repository geladen

### Phase 2: Bootstrap-Skripte (werden geladen)

**setup-docker-volume.sh** (wird vom Repository geladen):
- Docker Volume Migration (komplett)
- Docker Compose v2 und Buildx Installation
- Wird als erstes ausgeführt (vor Services-Installation)

**install-services.sh** (wird vom Repository geladen):
- container-setup.sh ausführen
- Ollama-GPU Installation
- Final Status

### Phase 3: Services-Installation (läuft im Hintergrund)

- Wie bisher, aber Skript wird geladen statt inline erstellt

## Detaillierte Code-Änderungen

### Änderung 1: User-Data drastisch kürzen

**Datei:** `create_aws_instance.sh`  
**Position:** Ab Zeile 178 (USER_DATA Block)

**Entfernen:**
1. **Docker Volume Migration Block** (Zeile 224-435) - **8.421 Bytes**
2. **Docker Compose Installation Block** (Zeile 437-452) - **820 Bytes**
3. **install_services.sh Inline-Erstellung** (Zeile 492-652) - **~4.200 Bytes**

**Behalten:**
1. System-Initialisierung (Zeile 179-196)
2. Git, Tools Installation (Zeile 202-204)
3. Docker Installation (Zeile 206-222)
4. Repository klonen (direkt, ohne Wrapper)
5. .env-Datei erstellen
6. Bootstrap-Skripte laden und starten

**Neuer User-Data Code (nach Zeile 222):**
```bash
echo "=== Docker Installation abgeschlossen ==="

# Repository klonen
echo "Klone Repository..."
cd /home/ec2-user
if [ ! -d "transcript-summarization" ]; then
    sudo -u ec2-user git clone https://github.com/dmuehlberg/transcript-summarization.git 2>&1
    if [ $? -eq 0 ]; then
        echo "Repository erfolgreich geklont"
    else
        echo "FEHLER: Repository konnte nicht geklont werden"
        exit 1
    fi
else
    echo "Repository bereits vorhanden"
    cd transcript-summarization
    sudo -u ec2-user git pull 2>&1 || echo "Git pull fehlgeschlagen"
fi

cd /home/ec2-user/transcript-summarization

# .env-Datei erstellen
if [ -f "/tmp/.env" ]; then
    echo "Kopiere .env-Datei..."
    sudo -u ec2-user cp /tmp/.env .env
else
    echo "Erstelle Standard .env..."
    sudo -u ec2-user cat > .env << 'ENVEOF'
POSTGRES_USER=root
POSTGRES_PASSWORD=postgres
POSTGRES_DB=n8n
N8N_ENCRYPTION_KEY=sombrero
N8N_USER_MANAGEMENT_JWT_SECRET=sombrero
TIMEZONE=Europe/Berlin
MEETING_TIME_WINDOW_MINUTES=5
TARGETPLATFORM=linux/amd64
ENVEOF
fi

# Bootstrap-Skripte laden und ausführen
echo "Lade Bootstrap-Skripte vom Repository..."

# 1. Docker Volume Setup laden und ausführen
echo "Lade setup-docker-volume.sh..."
curl -L https://raw.githubusercontent.com/dmuehlberg/transcript-summarization/main/setup-docker-volume.sh -o /root/setup-docker-volume.sh 2>&1
if [ -f "/root/setup-docker-volume.sh" ]; then
    chmod +x /root/setup-docker-volume.sh
    echo "Führe setup-docker-volume.sh aus..."
    /root/setup-docker-volume.sh 2>&1
else
    echo "⚠️ Warnung: setup-docker-volume.sh konnte nicht geladen werden"
fi

# 2. Services Installation laden und im Hintergrund starten
echo "Lade install-services.sh..."
curl -L https://raw.githubusercontent.com/dmuehlberg/transcript-summarization/main/install-services.sh -o /home/ec2-user/install-services.sh 2>&1
if [ -f "/home/ec2-user/install-services.sh" ]; then
    chmod +x /home/ec2-user/install-services.sh
    echo "Starte install-services.sh im Hintergrund..."
    sudo -u ec2-user nohup /home/ec2-user/install-services.sh > /var/log/install-services.log 2>&1 &
else
    echo "⚠️ Warnung: install-services.sh konnte nicht geladen werden"
fi

echo "=== USER-DATA ABGESCHLOSSEN ==="
echo "Bootstrap-Skripte laufen..."
echo "Logs: /var/log/install-services.log"
```

**Geschätzte Größe dieses Blocks:** ~1.200 Bytes

### Änderung 2: Neue Datei erstellen - setup-docker-volume.sh

**Neue Datei:** `setup-docker-volume.sh` (muss im Repository verfügbar sein)

**Inhalt:**
```bash
#!/bin/bash
# Docker Volume Migration und Docker Compose Installation
# Wird vom User-Data geladen und ausgeführt

exec >> /var/log/setup-docker-volume.log 2>&1
echo "=== DOCKER VOLUME SETUP GESTARTET ==="
echo "Datum: $(date)"

# Docker auf größeres EBS-Volume umziehen (falls verfügbar)
echo "=== Docker Volume Migration ==="
DOCKER_VOLUME_MOUNT="/mnt/docker-data"

# Warte auf EBS-Volumes
echo "Warte auf zusätzliche EBS-Volumes..."
MAX_WAIT=60
WAIT_COUNT=0
DOCKER_VOLUME_DEVICE=""

# [HIER KOMMT DER KOMPLETTE DOCKER VOLUME MIGRATION CODE - Zeile 228-433 aus aktuellem Skript]
# (Identisch mit dem aktuellen Code, nur ohne die echo-Statements die bereits im User-Data waren)

echo "=== Docker Volume Migration abgeschlossen ==="

# Docker Compose v2 und Buildx installieren
echo "Installiere Docker Compose v2 und Buildx..."
curl -L "https://github.com/docker/compose/releases/download/v2.40.1/docker-compose-linux-x86_64" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose

mkdir -p /usr/local/lib/docker/cli-plugins
curl -L "https://github.com/docker/buildx/releases/download/v0.18.0/buildx-v0.18.0.linux-amd64" -o /usr/local/lib/docker/cli-plugins/docker-buildx
chmod +x /usr/local/lib/docker/cli-plugins/docker-buildx

docker buildx create --use --name mybuilder

echo "Docker Compose v2 und Buildx v0.18.0+ installiert"
echo "=== DOCKER VOLUME SETUP ABGESCHLOSSEN ==="
```

**Geschätzte Größe:** ~8.500 Bytes (wird nicht im User-Data gezählt!)

### Änderung 3: install-services.sh ins Repository verschieben

**Neue Datei:** `install-services.sh` (muss im Repository verfügbar sein)

**Inhalt:** Identisch mit dem aktuellen Inline-Skript (Zeile 495-651), aber als separate Datei im Repository.

**Geschätzte Größe:** ~4.200 Bytes (wird nicht im User-Data gezählt!)

## Größenabschätzung nach Implementierung

### Phase 1 (User-Data):

- System-Initialisierung: ~200 Bytes
- Git, Tools: ~300 Bytes
- Docker Installation: ~500 Bytes
- Repository klonen: ~400 Bytes
- .env-Datei: ~300 Bytes
- Bootstrap-Skripte laden: ~500 Bytes

**Gesamt Phase 1: ~2.200 Bytes** ✅✅✅ (nur 13% des Limits!)

### Phase 2 (setup-docker-volume.sh):

- Docker Volume Migration: ~8.500 Bytes
- Docker Compose Installation: ~800 Bytes

**Gesamt Phase 2: ~9.300 Bytes** (wird geladen, nicht im User-Data)

### Phase 3 (install-services.sh):

- Services Installation: ~4.200 Bytes

**Gesamt Phase 3: ~4.200 Bytes** (wird geladen, nicht im User-Data)

## Vorteile dieser Lösung

1. ✅✅✅ **User-Data deutlich unter Limit** (~2.2 KB statt 17.5 KB)
2. ✅ **Keine zusätzliche Infrastruktur** (verwendet GitHub Raw URLs)
3. ✅ **Einfache Wartung** - Skripte können im Repository aktualisiert werden
4. ✅ **Klare Trennung** - Jede Phase hat eigene Verantwortlichkeit
5. ✅ **Robustheit** - Falls ein Skript fehlschlägt, können andere trotzdem laufen
6. ✅ **Flexibilität** - Skripte können später manuell ausgeführt werden

## Nachteile / Herausforderungen

1. ⚠️ **Abhängigkeit von GitHub** - Repository muss öffentlich oder authentifiziert sein
2. ⚠️ **Internet-Verfügbarkeit** - Skripte müssen vom Internet geladen werden können
3. ⚠️ **Mehrere Log-Dateien** - `/var/log/setup-docker-volume.log` und `/var/log/install-services.log`
4. ⚠️ **Reihenfolge** - setup-docker-volume.sh muss vor install-services.sh laufen

## Implementierungsschritte

### Schritt 1: Neue Dateien im Repository erstellen

1. **setup-docker-volume.sh** erstellen:
   - Docker Volume Migration Code aus User-Data kopieren
   - Docker Compose Installation hinzufügen
   - Logging hinzufügen
   - In Repository committen

2. **install-services.sh** erstellen:
   - Aktuellen Inline-Code aus User-Data extrahieren
   - Als separate Datei speichern
   - In Repository committen

### Schritt 2: User-Data kürzen

**Datei:** `create_aws_instance.sh`

**Entfernen:**
- Zeile 224-435: Docker Volume Migration
- Zeile 437-452: Docker Compose Installation  
- Zeile 492-652: install_services.sh Erstellung

**Ersetzen durch:**
- Repository klonen (vereinfacht)
- .env-Datei erstellen (vereinfacht)
- Bootstrap-Skripte laden und starten (neu)

### Schritt 3: Monitoring anpassen

**Datei:** `create_aws_instance.sh`  
**Position:** Monitoring-Block (ca. Zeile 779)

**Hinzufügen:**
```bash
# Docker Volume Setup Log (falls vorhanden)
if [ -f /var/log/setup-docker-volume.log ]; then
    echo "DOCKER VOLUME SETUP LOG (letzte 5 Zeilen):"
    sudo tail -5 /var/log/setup-docker-volume.log
else
    echo "Docker Volume Setup Log: Noch nicht verfügbar"
fi
```

## Validierung

Nach der Implementierung sollten folgende Checks funktionieren:

1. **User-Data Größe:** `echo -n "$USER_DATA" | wc -c` sollte < 16384 sein (erwartet: ~2.200 Bytes)
2. **Repository:** `/home/ec2-user/transcript-summarization` sollte existieren
3. **Bootstrap-Skripte:** 
   - `/root/setup-docker-volume.sh` sollte existieren (geladen)
   - `/home/ec2-user/install-services.sh` sollte existieren (geladen)
4. **Logs:** 
   - `/var/log/setup-docker-volume.log` sollte erstellt werden
   - `/var/log/install-services.log` sollte erstellt werden
5. **Services:** WhisperX und Ollama sollten nach einiger Zeit laufen

## Fallback-Strategien

### Fallback 1: GitHub nicht erreichbar

**Problem:** `curl` kann Skripte nicht laden

**Lösung:** Im User-Data Fallback-Code hinzufügen:
```bash
# Fallback: Falls curl fehlschlägt, warte und versuche erneut
if [ ! -f "/root/setup-docker-volume.sh" ]; then
    echo "Warte auf Internet-Verfügbarkeit..."
    sleep 30
    curl -L https://raw.githubusercontent.com/dmuehlberg/transcript-summarization/main/setup-docker-volume.sh -o /root/setup-docker-volume.sh 2>&1
fi
```

### Fallback 2: Skripte nicht im Repository

**Problem:** Dateien existieren noch nicht im Repository

**Lösung:** 
- Skripte müssen VOR dem ersten Deployment ins Repository committed werden
- Oder: Verwende Branch/Tag-spezifische URLs

### Fallback 3: Authentifizierung nötig

**Problem:** Repository ist privat

**Lösung:** 
- GitHub Token in User-Data verwenden (als Umgebungsvariable)
- Oder: S3-Bucket verwenden (erfordert IAM-Rolle)

## Test-Plan

### 1. Lokale Vorbereitung

1. **setup-docker-volume.sh** erstellen und testen:
   ```bash
   # Test auf lokaler Maschine
   bash setup-docker-volume.sh
   ```

2. **install-services.sh** erstellen und testen:
   ```bash
   # Test auf lokaler Maschine (mit Mock-Umgebung)
   bash install-services.sh
   ```

3. **Beide Dateien ins Repository committen:**
   ```bash
   git add setup-docker-volume.sh install-services.sh
   git commit -m "Add bootstrap scripts for AWS deployment"
   git push
   ```

### 2. User-Data Größe prüfen

```bash
# Prüfe User-Data Größe
python3 << 'PY'
import re
from pathlib import Path
text = Path('create_aws_instance.sh').read_text()
match = re.search(r"USER_DATA=\$\(cat <<'EOF'\n(.*?)\nEOF", text, re.DOTALL)
if match:
    print(f"User-Data Größe: {len(match.group(1))} Bytes")
    print(f"Limit: 16384 Bytes")
    print(f"Unterschreitung: {16384 - len(match.group(1))} Bytes")
PY
```

### 3. AWS-Tests

1. Erstelle Test-Instanz
2. Prüfe `/var/log/user-data.log` - sollte "USER-DATA ABGESCHLOSSEN" enthalten
3. Prüfe `/var/log/setup-docker-volume.log` - sollte Docker Volume Setup zeigen
4. Prüfe `/var/log/install-services.log` - sollte Services-Installation zeigen
5. Prüfe Container-Status nach 15-20 Minuten

### 4. Integration-Tests

1. Vollständige Installation durchführen
2. Alle Services prüfen
3. API-Endpunkte testen
4. Logs auf Vollständigkeit prüfen

## Zusammenfassung

Die Implementierung umfasst:

1. ✅ User-Data auf Minimum reduzieren (~2.2 KB)
2. ✅ Docker Volume Migration in `setup-docker-volume.sh` auslagern
3. ✅ install_services.sh ins Repository verschieben
4. ✅ Bootstrap-Skripte mit curl vom Repository laden
5. ✅ Monitoring um neue Log-Dateien erweitern

**Erwartete Größen:**
- Phase 1 (User-Data): ~2.200 Bytes ✅✅✅ (nur 13% des Limits!)
- Phase 2 (setup-docker-volume.sh): ~9.300 Bytes (wird geladen)
- Phase 3 (install-services.sh): ~4.200 Bytes (wird geladen)

**Wichtig:** Die neuen Skripte (`setup-docker-volume.sh` und `install-services.sh`) müssen VOR dem ersten Deployment ins Repository committed und gepusht werden!

**Alle Änderungen sind im `create_aws_instance.sh` Skript und in den neuen Repository-Dateien vorzunehmen.**

