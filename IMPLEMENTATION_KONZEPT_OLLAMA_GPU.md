# Implementierungskonzept: Ollama-GPU Integration in AWS-Instanz-Setup
## Übersicht
Dieses Dokument beschreibt die notwendigen Änderungen am `create_aws_instance.sh` Skript, um nach der WhisperX-Installation automatisch den `ollama-gpu` Container zu installieren und das Modell `qwen2.5:7b` zu pullen. Zusätzlich muss Port 11434 in der Security Group geöffnet werden.
## Anforderungen
1. **Ollama-GPU Container** muss nach der WhisperX-Installation gestartet werden
2. **Modell qwen2.5:7b** muss automatisch gepullt werden
3. **Port 11434** muss in der AWS Security Group geöffnet werden
4. **GPU-Unterstützung** muss für Ollama aktiviert sein (nvidia runtime)
## Implementierungsschritte
### 1. Security Group Erweiterung (Port 11434)
**Datei:** `create_aws_instance.sh`  
**Position:** Nach Zeile 135 (nach dem Öffnen von Port 8000)
**Änderung:**
```bash
# Ollama API auf Port 11434 erlauben
aws ec2 authorize-security-group-ingress --region $region \
    --group-id $SG_ID \
    --protocol tcp \
    --port 11434 \
    --cidr 0.0.0.0/0 > /dev/null
```
**Kontext:** Diese Zeile sollte direkt nach dem Öffnen von Port 8000 (Zeile 131-135) eingefügt werden, innerhalb des Blocks, der die Sicherheitsregeln hinzufügt.
### 2. Ollama-GPU Installation im User-Data Skript
**Datei:** `create_aws_instance.sh`  
**Position:** Im `ec2_setup.sh` Skript (innerhalb des USER_DATA Blocks), nach der WhisperX-Installation
**Änderung:** Nach dem `container-setup.sh` Aufruf (ca. Zeile 496-518) muss ein neuer Abschnitt hinzugefügt werden:
```bash
# Ollama-GPU Container starten
echo "=== OLLAMA-GPU INSTALLATION ==="
echo "Starte Ollama-GPU Container..."
# Warte kurz, damit Docker bereit ist
sleep 5
# Starte Ollama-GPU Container mit GPU-Unterstützung
cd /home/ec2-user/transcript-summarization
# Prüfe ob docker-compose verfügbar ist
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
elif [ -f "/usr/local/bin/docker-compose" ]; then
    DOCKER_COMPOSE_CMD="/usr/local/bin/docker-compose"
else
    echo "FEHLER: docker-compose nicht gefunden"
    exit 1
fi
# Starte Ollama-GPU Container mit gpu-nvidia Profil
echo "Starte Ollama-GPU Container..."
$DOCKER_COMPOSE_CMD --profile gpu-nvidia up -d ollama-gpu 2>&1
# Warte auf Container-Start
echo "Warte auf Ollama-Container-Start..."
MAX_WAIT=120
WAIT_COUNT=0
while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "✅ Ollama-Container läuft"
        break
    fi
    echo "Warte auf Ollama... ($WAIT_COUNT/$MAX_WAIT Sekunden)"
    sleep 5
    WAIT_COUNT=$((WAIT_COUNT + 5))
done
# Pull qwen2.5:7b Modell
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Pulle qwen2.5:7b Modell..."
    # Verwende einen temporären Container zum Pullen des Modells
    docker run --rm \
        --network transcript-summarization_demo \
        --volumes-from $(docker ps -q -f name=ollama) \
        ollama/ollama:latest \
        ollama pull qwen2.5:7b 2>&1
    
    if [ $? -eq 0 ]; then
        echo "✅ qwen2.5:7b Modell erfolgreich gepullt"
    else
        echo "⚠️ Warnung: Modell-Pull fehlgeschlagen, versuche alternativen Ansatz..."
        # Alternativer Ansatz: Direkt im laufenden Container
        docker exec ollama ollama pull qwen2.5:7b 2>&1
    fi
else
    echo "⚠️ Warnung: Ollama-Container nicht erreichbar, Modell-Pull wird übersprungen"
fi
echo "=== OLLAMA-GPU INSTALLATION ABGESCHLOSSEN ==="
```
**Alternative Implementierung (robuster):**
Falls der obige Ansatz Probleme macht, kann ein separater Init-Container verwendet werden (analog zu `ollama-pull-llama-gpu` in docker-compose.yml):
```bash
# Erstelle temporären Container zum Pullen des Modells
echo "Pulle qwen2.5:7b Modell mit Init-Container..."
docker run --rm \
    --network transcript-summarization_demo \
    -v transcript-summarization_ollama_storage:/root/.ollama \
    ollama/ollama:latest \
    /bin/sh -c "sleep 5; OLLAMA_HOST=ollama:11434 ollama pull qwen2.5:7b" 2>&1
```
### 3. Status-Ausgabe erweitern
**Datei:** `create_aws_instance.sh`  
**Position:** Im "Final Status" Abschnitt (ca. Zeile 526-540)
**Änderung:** Erweitere die Status-Ausgabe um Ollama-Informationen:
```bash
echo "Ollama Status:"
sudo -u ec2-user bash -c 'cd /home/ec2-user/transcript-summarization && docker ps --filter name=ollama --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "Ollama Container Status nicht verfügbar"'
# Ollama API Test
curl -s http://localhost:11434/api/tags 2>/dev/null && echo "Ollama API: OK" || echo "Ollama API: Nicht verfügbar"
# Prüfe ob qwen2.5:7b Modell verfügbar ist
if curl -s http://localhost:11434/api/tags | grep -q "qwen2.5:7b"; then
    echo "✅ qwen2.5:7b Modell verfügbar"
else
    echo "⚠️ qwen2.5:7b Modell nicht gefunden"
fi
```
### 4. Monitoring erweitern
**Datei:** `create_aws_instance.sh`  
**Position:** Im Log-Monitoring Abschnitt (ca. Zeile 630-694)
**Änderung:** Erweitere das Monitoring um Ollama-Status:
```bash
# 5. Ollama Status
echo "OLLAMA STATUS:"
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo " - Ollama API verfügbar"
    if curl -s http://localhost:11434/api/tags | grep -q "qwen2.5:7b"; then
        echo " - qwen2.5:7b Modell verfügbar"
    else
        echo " - qwen2.5:7b Modell noch nicht verfügbar"
    fi
else
    echo " - Ollama API noch nicht verfügbar"
fi
```
### 5. Info-Ausgabe erweitern
**Datei:** `create_aws_instance.sh`  
**Position:** Im "NÄCHSTE SCHRITTE" Abschnitt (ca. Zeile 580-595)
**Änderung:** Füge Ollama-spezifische Informationen hinzu:
```bash
info "6. Ollama API testen: http://$PUBLIC_IP:11434/api/tags"
info "7. Ollama Modell-Liste: curl http://$PUBLIC_IP:11434/api/tags"
```
## Detaillierte Code-Änderungen
### Änderung 1: Security Group (Zeile ~136)
**Vor:**
```bash
        log "Sicherheitsgruppe erstellt mit ID: $SG_ID"
    fi
```
**Nach:**
```bash
        # Ollama API auf Port 11434 erlauben
        aws ec2 authorize-security-group-ingress --region $region \
            --group-id $SG_ID \
            --protocol tcp \
            --port 11434 \
            --cidr 0.0.0.0/0 > /dev/null
        
        log "Sicherheitsgruppe erstellt mit ID: $SG_ID"
    fi
```
### Änderung 2: User-Data Skript - Ollama Installation (nach Zeile ~518)
**Einfügen nach:**
```bash
echo "=== EC2-USER SETUP ABGESCHLOSSEN ==="
EOS
```
**Neuer Code-Block:**
```bash
# Ollama-GPU Installation
echo "=== OLLAMA-GPU INSTALLATION ==="
cd /home/ec2-user/transcript-summarization
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
EOS
```
**Wichtig:** Dieser Block muss VOR dem `chmod +x /home/ec2-user/ec2_setup.sh` (Zeile 523) eingefügt werden, aber NACH dem `EOS` des `ec2_setup.sh` Skripts.
### Änderung 3: Status-Ausgabe (nach Zeile ~531)
**Einfügen nach:**
```bash
echo "Docker Container:"
sudo -u ec2-user bash -c 'cd /home/ec2-user/transcript-summarization && docker-compose ps 2>/dev/null || echo "Container Status nicht verfügbar"'
```
**Neuer Code:**
```bash
echo "Ollama Container:"
sudo -u ec2-user bash -c 'cd /home/ec2-user/transcript-summarization && docker ps --filter name=ollama --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "Ollama Container Status nicht verfügbar"'
echo "Ollama API Check:"
curl -s http://localhost:11434/api/tags > /dev/null 2>&1 && echo "✅ Ollama API: OK" || echo "⚠️ Ollama API: Nicht verfügbar"
echo "Ollama Modell Check:"
if curl -s http://localhost:11434/api/tags 2>/dev/null | grep -q "qwen2.5:7b"; then
    echo "✅ qwen2.5:7b Modell verfügbar"
else
    echo "⚠️ qwen2.5:7b Modell nicht gefunden"
fi
```
### Änderung 4: Info-Ausgabe (nach Zeile ~587)
**Einfügen nach:**
```bash
info "5. Health Check: curl http://$PUBLIC_IP:8000/health"
```
**Neuer Code:**
```bash
info "6. Ollama API testen: curl http://$PUBLIC_IP:11434/api/tags"
info "7. Ollama Modell-Liste: curl http://$PUBLIC_IP:11434/api/tags | jq"
```
### Änderung 5: Monitoring (nach Zeile ~685)
**Einfügen nach:**
```bash
                else
                    echo " - API noch nicht verfügbar"
                fi
```
**Neuer Code:**
```bash
                else
                    echo " - API noch nicht verfügbar"
                fi
                
                # 5. Ollama Status
                echo "OLLAMA CHECK:"
                if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
                    echo " - Ollama API verfügbar"
                    if curl -s http://localhost:11434/api/tags 2>/dev/null | grep -q "qwen2.5:7b"; then
                        echo " - qwen2.5:7b Modell verfügbar"
                    else
                        echo " - qwen2.5:7b Modell noch nicht verfügbar"
                    fi
                else
                    echo " - Ollama API noch nicht verfügbar"
                fi
```
## Technische Details
### Docker Compose Profil
Das `ollama-gpu` Service verwendet das Profil `gpu-nvidia`, daher muss beim Start das Profil angegeben werden:
```bash
docker-compose --profile gpu-nvidia up -d ollama-gpu
```
### GPU-Unterstützung
Der Container benötigt:
- NVIDIA Container Runtime (bereits im Deep Learning AMI vorhanden)
- GPU-Zugriff über `runtime: nvidia` (in docker-compose.yml definiert)
- Deploy-Resources mit GPU-Reservierung
### Netzwerk
Ollama läuft im Docker-Netzwerk `transcript-summarization_demo` (basierend auf dem Verzeichnisnamen). Der Container-Name ist `ollama`.
### Modell-Pull
Das Modell `qwen2.5:7b` wird über die Ollama CLI gepullt. Der Pull kann mehrere Minuten dauern, abhängig von der Internetverbindung.
## Validierung
Nach der Implementierung sollten folgende Checks funktionieren:
1. **Security Group:** Port 11434 sollte von außen erreichbar sein
2. **Container:** `docker ps` sollte den `ollama` Container zeigen
3. **API:** `curl http://<PUBLIC_IP>:11434/api/tags` sollte eine JSON-Antwort zurückgeben
4. **Modell:** Die API-Antwort sollte `qwen2.5:7b` enthalten
## Fehlerbehandlung
### Fallback-Strategien
1. **Container-Start fehlgeschlagen:**
   - Prüfe Docker-Logs: `docker logs ollama`
   - Prüfe GPU-Verfügbarkeit: `nvidia-smi`
   - Prüfe Container-Status: `docker ps -a`
2. **Modell-Pull fehlgeschlagen:**
   - Manueller Pull: `docker exec ollama ollama pull qwen2.5:7b`
   - Prüfe Internetverbindung
   - Prüfe verfügbaren Speicherplatz
3. **Port nicht erreichbar:**
   - Prüfe Security Group Regeln in AWS Console
   - Prüfe Container-Port-Mapping: `docker ps` zeigt Ports
   - Prüfe Firewall auf der Instanz
## Hinweise
- Die Installation von Ollama und das Pullen des Modells kann zusätzliche 5-15 Minuten dauern
- Das Modell `qwen2.5:7b` benötigt ca. 4-5 GB Speicherplatz
- GPU-Speicher wird für das Modell benötigt (abhängig von der Modellgröße)
- Die Security Group Änderung wird sofort wirksam, keine Instanz-Neustarts nötig
## Zusammenfassung
Die Implementierung umfasst:
1. ✅ Security Group Erweiterung für Port 11434
2. ✅ Ollama-GPU Container Start im User-Data Skript
3. ✅ Automatisches Pull des qwen2.5:7b Modells
4. ✅ Status-Ausgabe und Monitoring Erweiterung
5. ✅ Info-Ausgabe für Benutzer
Alle Änderungen sind im `create_aws_instance.sh` Skript vorzunehmen, keine zusätzlichen Dateien erforderlich.

