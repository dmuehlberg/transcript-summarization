# Implementierungskonzept: User-Data-Skript Aufteilung
## Problem
Das User-Data-Skript in `create_aws_instance.sh` ist mit ~25.329 Bytes zu groß für das AWS-Limit von 16.384 Bytes (16 KB).
## Lösung: Zweistufige Aufteilung
Das Skript wird in zwei Phasen aufgeteilt:
1. **Phase 1 (User-Data)**: Basis-Setup - Docker, Repository klonen
2. **Phase 2 (zweites Skript)**: WhisperX + Ollama-Installation
## Analyse der aktuellen Struktur
### Aktuelles User-Data-Skript enthält:
1. **Basis-Setup** (~8-10 KB):
   - System-Initialisierung (sleep, logging)
   - Git, htop, nano, mc Installation
   - Docker Installation und Konfiguration
   - Docker Volume Migration (sehr groß, ~6-7 KB)
   - Docker Compose v2 und Buildx Installation
2. **ec2_setup.sh Erstellung** (~2-3 KB):
   - Repository klonen
   - .env-Datei kopieren/erstellen
   - container-setup.sh ausführen
3. **Ollama-GPU Installation** (~3-4 KB):
   - Warte auf WhisperX-Container
   - Ollama-GPU Container starten
   - qwen2.5:7b Modell pullen
4. **Final Status** (~1 KB):
   - Status-Ausgabe
   - Health Checks
**Gesamt: ~25 KB (überschreitet Limit)**
## Aufteilungsstrategie
### Phase 1: User-Data (muss < 16 KB sein)
**Enthält:**
- System-Initialisierung
- Git, htop, nano, mc Installation
- Docker Installation und Konfiguration
- Docker Volume Migration (kann nicht weggelassen werden)
- Docker Compose v2 und Buildx Installation
- Repository klonen
- .env-Datei kopieren/erstellen
- **Zweites Skript erstellen und ausführen** (als Hintergrundprozess)
**Geschätzte Größe:** ~12-14 KB (sollte unter Limit sein)
### Phase 2: Zweites Skript (`/home/ec2-user/install_services.sh`)
**Enthält:**
- Warte auf Repository-Verfügbarkeit
- container-setup.sh ausführen
- Warte auf WhisperX-Container
- Ollama-GPU Installation
- Final Status-Ausgabe
**Geschätzte Größe:** ~3-4 KB
## Detaillierte Implementierung
### Änderung 1: User-Data-Skript kürzen
**Datei:** `create_aws_instance.sh`  
**Position:** Ab Zeile 178 (USER_DATA Block)
**Entfernen aus User-Data:**
1. Ollama-GPU Installation Block (Zeile 533-628)
2. Final Status Block (Zeile 630-647) - kann ins zweite Skript
3. ec2_setup.sh Ausführung (Zeile 531) - wird durch zweites Skript ersetzt
**Behalten in User-Data:**
1. Basis-Setup (System, Git, Docker)
2. Docker Volume Migration (muss bleiben, da vor Repository-Klon)
3. Docker Compose Installation
4. Repository klonen (direkt im User-Data)
5. .env-Datei kopieren/erstellen
6. **Zweites Skript erstellen und starten**
### Änderung 2: Zweites Skript erstellen
**Neue Datei:** Wird im User-Data erstellt als `/home/ec2-user/install_services.sh`
**Inhalt des zweiten Skripts:**
```bash
#!/bin/bash
# Zweites Installations-Skript für WhisperX und Ollama
# Wird nach Repository-Klon ausgeführt
exec >> /var/log/install-services.log 2>&1
echo "=== SERVICES INSTALLATION GESTARTET ==="
echo "Datum: $(date)"
# Warte auf Repository-Verfügbarkeit
if [ ! -d "/home/ec2-user/transcript-summarization" ]; then
    echo "Warte auf Repository..."
    MAX_WAIT=300
    WAIT_COUNT=0
    while [ $WAIT_COUNT -lt $MAX_WAIT ] && [ ! -d "/home/ec2-user/transcript-summarization" ]; do
        sleep 5
        WAIT_COUNT=$((WAIT_COUNT + 5))
    done
fi
cd /home/ec2-user/transcript-summarization
# container-setup.sh ausführen
if [ -f "./container-setup.sh" ]; then
    echo "Führe container-setup.sh aus..."
    chmod +x ./container-setup.sh
    echo "n" | timeout 1800 ./container-setup.sh 2>&1
    SETUP_EXIT_CODE=$?
    if [ $SETUP_EXIT_CODE -eq 0 ]; then
        echo "container-setup.sh erfolgreich abgeschlossen"
    elif [ $SETUP_EXIT_CODE -eq 124 ]; then
        echo "WARNUNG: container-setup.sh Timeout nach 30 Minuten"
    else
        echo "FEHLER: container-setup.sh fehlgeschlagen (Exit Code: $SETUP_EXIT_CODE)"
    fi
else
    echo "FEHLER: container-setup.sh nicht gefunden!"
    exit 1
fi
# Ollama-GPU Installation (nach WhisperX-Installation)
echo "=== OLLAMA-GPU INSTALLATION ==="
# Warte auf WhisperX-Container (max. 10 Minuten)
echo "Warte auf WhisperX-Container..."
WHISPERX_WAIT=600
WHISPERX_COUNT=0
WHISPERX_READY=false
while [ $WHISPERX_COUNT -lt $WHISPERX_WAIT ]; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ WhisperX-Container läuft"
        WHISPERX_READY=true
        break
    fi
    if [ $((WHISPERX_COUNT % 60)) -eq 0 ]; then
        echo "Warte auf WhisperX... ($WHISPERX_COUNT/$WHISPERX_WAIT Sekunden)"
    fi
    sleep 10
    WHISPERX_COUNT=$((WHISPERX_COUNT + 10))
done
if [ "$WHISPERX_READY" != "true" ]; then
    echo "⚠️ Warnung: WhisperX-Container nicht erreichbar nach $WHISPERX_WAIT Sekunden"
    echo "Ollama-Installation wird trotzdem versucht..."
fi
# Prüfe docker-compose Verfügbarkeit
DOCKER_COMPOSE_CMD=""
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
elif [ -f "/usr/local/bin/docker-compose" ]; then
    DOCKER_COMPOSE_CMD="/usr/local/bin/docker-compose"
else
    echo "FEHLER: docker-compose nicht gefunden"
    exit 1
fi
# Starte Ollama-GPU Container
echo "Starte Ollama-GPU Container..."
$DOCKER_COMPOSE_CMD --profile gpu-nvidia up -d ollama-gpu 2>&1
# Warte auf Container-Start (max. 2 Minuten)
echo "Warte auf Ollama-Container-Start..."
MAX_WAIT=120
WAIT_COUNT=0
OLLAMA_READY=false
while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "✅ Ollama-Container läuft"
        OLLAMA_READY=true
        break
    fi
    if [ $((WAIT_COUNT % 15)) -eq 0 ]; then
        echo "Warte auf Ollama... ($WAIT_COUNT/$MAX_WAIT Sekunden)"
    fi
    sleep 5
    WAIT_COUNT=$((WAIT_COUNT + 5))
done
# Pull qwen2.5:7b Modell
if [ "$OLLAMA_READY" = "true" ]; then
    echo "Pulle qwen2.5:7b Modell..."
    
    # Versuche Modell-Pull direkt im Container
    if docker exec ollama ollama pull qwen2.5:7b 2>&1; then
        echo "✅ qwen2.5:7b Modell erfolgreich gepullt"
    else
        echo "⚠️ Warnung: Direkter Pull fehlgeschlagen, versuche alternativen Ansatz..."
        # Alternativer Ansatz: Temporärer Container mit shared volume
        docker run --rm \
            --network transcript-summarization_demo \
            -v transcript-summarization_ollama_storage:/root/.ollama \
            ollama/ollama:latest \
            /bin/sh -c "sleep 3; OLLAMA_HOST=ollama:11434 ollama pull qwen2.5:7b" 2>&1
        
        if [ $? -eq 0 ]; then
            echo "✅ qwen2.5:7b Modell erfolgreich gepullt (alternativer Ansatz)"
        else
            echo "⚠️ Warnung: Modell-Pull fehlgeschlagen, kann später manuell durchgeführt werden"
        fi
    fi
else
    echo "⚠️ Warnung: Ollama-Container nicht erreichbar, Modell-Pull wird übersprungen"
fi
echo "=== OLLAMA-GPU INSTALLATION ABGESCHLOSSEN ==="
# Final Status
echo "=== INSTALLATION STATUS ==="
echo "Datum: $(date)"
echo "Docker Container:"
cd /home/ec2-user/transcript-summarization
$DOCKER_COMPOSE_CMD ps 2>/dev/null || echo "Container Status nicht verfügbar"
echo "Ollama Container:"
docker ps --filter name=ollama --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "Ollama Container Status nicht verfügbar"
echo "Ollama API Check:"
curl -s http://localhost:11434/api/tags > /dev/null 2>&1 && echo "✅ Ollama API: OK" || echo "⚠️ Ollama API: Nicht verfügbar"
echo "Ollama Modell Check:"
if curl -s http://localhost:11434/api/tags 2>/dev/null | grep -q "qwen2.5:7b"; then
    echo "✅ qwen2.5:7b Modell verfügbar"
else
    echo "⚠️ qwen2.5:7b Modell nicht gefunden"
fi
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
echo "Public IP: $PUBLIC_IP"
echo "API URL: http://$PUBLIC_IP:8000/docs"
echo "Ollama API: http://$PUBLIC_IP:11434/api/tags"
curl -s http://localhost:8000/health 2>/dev/null && echo "API Health Check: OK" || echo "API Health Check: Nicht verfügbar"
echo "=== SERVICES INSTALLATION ABGESCHLOSSEN ==="
```
## Detaillierte Code-Änderungen
### Änderung 1: User-Data Skript kürzen
**Position:** Nach Zeile 452 (nach "Docker Compose v2 und Buildx installiert")
**Entfernen:**
- Zeile 454-528: `ec2_setup.sh` Erstellung (wird durch direktes Repository-Klonen ersetzt)
- Zeile 530-531: `chmod` und Ausführung von `ec2_setup.sh`
- Zeile 533-628: Ollama-GPU Installation Block
- Zeile 630-647: Final Status Block
**Hinzufügen:**
- Direktes Repository-Klonen (ohne ec2_setup.sh Wrapper)
- .env-Datei kopieren/erstellen
- Zweites Skript (`install_services.sh`) erstellen
- Zweites Skript im Hintergrund starten
**Neuer Code-Block (nach Zeile 452):**
```bash
# Repository klonen (direkt, ohne ec2_setup.sh Wrapper)
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
# .env-Datei aus /tmp kopieren (falls verfügbar)
if [ -f "/tmp/.env" ]; then
    echo "Kopiere .env-Datei mit HF_TOKEN..."
    sudo -u ec2-user cp /tmp/.env .env
    echo "✅ .env-Datei mit HF_TOKEN kopiert"
else
    echo "⚠️ .env-Datei nicht verfügbar - erstelle Standard .env"
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
# Zweites Installations-Skript erstellen
echo "Erstelle install_services.sh Skript..."
cat > /home/ec2-user/install_services.sh << 'INSTALLEOF'
[HIER KOMMT DER INHALT DES ZWEITEN SKRIPTS - siehe oben]
INSTALLEOF
chmod +x /home/ec2-user/install_services.sh
# Zweites Skript im Hintergrund starten (als ec2-user)
echo "Starte install_services.sh im Hintergrund..."
sudo -u ec2-user nohup /home/ec2-user/install_services.sh > /var/log/install-services.log 2>&1 &
echo "=== USER-DATA ABGESCHLOSSEN ==="
echo "Services-Installation läuft im Hintergrund"
echo "Log: /var/log/install-services.log"
```
### Änderung 2: Monitoring anpassen
**Position:** Im Monitoring-Block (ca. Zeile 630-694)
**Anpassung:** Monitoring sollte auch `/var/log/install-services.log` prüfen
**Hinzufügen:**
```bash
# Services Installation Log (falls vorhanden)
if [ -f /var/log/install-services.log ]; then
    echo "SERVICES INSTALLATION LOG (letzte 5 Zeilen):"
    sudo tail -5 /var/log/install-services.log
else
    echo "Services Installation Log: Noch nicht verfügbar"
fi
```
## Größenabschätzung
### Phase 1 (User-Data) - Geschätzte Größe:
- Basis-Setup: ~1 KB
- Git, Tools Installation: ~0.5 KB
- Docker Installation: ~1 KB
- Docker Volume Migration: ~6 KB (kann nicht reduziert werden)
- Docker Compose Installation: ~1 KB
- Repository klonen: ~0.5 KB
- .env-Datei: ~0.5 KB
- Zweites Skript erstellen: ~0.5 KB
- Zweites Skript starten: ~0.3 KB
**Gesamt Phase 1: ~11-12 KB** ✅ (unter 16 KB Limit)
### Phase 2 (install_services.sh) - Geschätzte Größe:
- Header/Logging: ~0.3 KB
- Repository-Wartezeit: ~0.5 KB
- container-setup.sh Ausführung: ~0.5 KB
- Ollama-GPU Installation: ~2 KB
- Final Status: ~0.7 KB
**Gesamt Phase 2: ~4 KB**
## Vorteile dieser Lösung
1. ✅ **Keine zusätzliche Infrastruktur nötig** (kein S3, keine IAM-Rollen)
2. ✅ **Klare Trennung** zwischen Basis-Setup und Services-Installation
3. ✅ **Einfaches Debugging** - separate Log-Dateien
4. ✅ **Robustheit** - zweites Skript läuft unabhängig
5. ✅ **Flexibilität** - zweites Skript kann später manuell ausgeführt werden
## Nachteile / Herausforderungen
1. ⚠️ **Asynchrone Ausführung** - User-Data ist fertig, bevor Services installiert sind
2. ⚠️ **Log-Verteilung** - Logs in zwei Dateien (`/var/log/user-data.log` und `/var/log/install-services.log`)
3. ⚠️ **Monitoring** - muss beide Logs prüfen
## Validierung
Nach der Implementierung sollten folgende Checks funktionieren:
1. **User-Data Größe:** `echo -n "$USER_DATA" | wc -c` sollte < 16384 sein
2. **Repository:** `/home/ec2-user/transcript-summarization` sollte existieren
3. **Zweites Skript:** `/home/ec2-user/install_services.sh` sollte existieren und ausführbar sein
4. **Logs:** `/var/log/install-services.log` sollte erstellt werden
5. **Services:** WhisperX und Ollama sollten nach einiger Zeit laufen
## Zusammenfassung
Die Implementierung umfasst:
1. ✅ User-Data Skript kürzen (entfernen: ec2_setup.sh, Ollama-Installation, Final Status)
2. ✅ Direktes Repository-Klonen im User-Data
3. ✅ Zweites Skript (`install_services.sh`) erstellen
4. ✅ Zweites Skript im Hintergrund starten
5. ✅ Monitoring anpassen (beide Logs prüfen)
**Erwartete Größen:**
- Phase 1 (User-Data): ~11-12 KB ✅
- Phase 2 (install_services.sh): ~4 KB
**Alle Änderungen sind im `create_aws_instance.sh` Skript vorzunehmen.**
