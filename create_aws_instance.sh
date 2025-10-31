#!/bin/bash
# Optimiertes Skript zum Deployment von WhisperX auf AWS mit GPU-Unterstützung
# Repliziert das funktionierende Brev-Setup mit NVIDIA 550.163.01 Treibern und CUDA 12.4

# Farben für bessere Lesbarkeit
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Log-Funktionen
log() { echo -e "${GREEN}[INFO] $1${NC}"; }
warn() { echo -e "${YELLOW}[WARN] $1${NC}"; }
info() { echo -e "${BLUE}[INFO] $1${NC}"; }
error() { echo -e "${RED}[ERROR] $1${NC}"; }

# Standardwerte
REGIONS=("eu-central-1" "eu-west-1" "eu-north-1" "us-east-1" "us-west-2")
INSTANCE_NAME="whisperx-server"
GPU_TYPE="t4"
KEY_NAME="whisperx-key"

# Parameter verarbeiten
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -r|--region) REGIONS=("$2"); shift ;;
        -t|--type) GPU_TYPE="$2"; shift ;;
        -n|--name) INSTANCE_NAME="$2"; shift ;;
        -k|--key) KEY_NAME="$2"; shift ;;
        *) shift ;;
    esac
    shift
done

# GPU-Typ überprüfen und Instance-Typ setzen
if [[ "$GPU_TYPE" == "t4" ]]; then
    INSTANCE_TYPE="g4dn.xlarge"
    log "GPU-Typ: T4 (g4dn.xlarge)"
elif [[ "$GPU_TYPE" == "a10g" ]]; then
    INSTANCE_TYPE="g5.xlarge"
    log "GPU-Typ: A10G (g5.xlarge)"
else
    error "Unbekannter GPU-Typ: $GPU_TYPE. Unterstützte Typen: t4, a10g"
    exit 1
fi

# Funktion zum Erstellen der Instanz in einer bestimmten Region
create_instance_in_region() {
    local region=$1
    log "Versuche EC2-Instanz in Region: $region, Instance-Typ: $INSTANCE_TYPE zu erstellen"

    # 1. Schlüsselpaar erstellen, falls es noch nicht existiert
    log "Prüfe auf vorhandenes Schlüsselpaar in $region..."
    KEY_EXISTS=$(aws ec2 describe-key-pairs --region $region --key-names $KEY_NAME --query 'KeyPairs[0].KeyName' --output text 2>/dev/null)

    # Temporäre Datei für das Schlüsselpaar
    KEY_FILE="$KEY_NAME.pem"
    TEMP_KEY_FILE="/tmp/$KEY_NAME-$(date +%s).pem"

    if [[ "$KEY_EXISTS" == "$KEY_NAME" ]]; then
        log "Schlüsselpaar '$KEY_NAME' existiert bereits in $region."
        
        # Prüfen, ob die Datei lokal existiert und beschreibbar ist
        if [[ ! -f "$KEY_FILE" || ! -w "$KEY_FILE" ]]; then
            warn "Die lokale Schlüsseldatei '$KEY_FILE' fehlt oder ist nicht beschreibbar!"
            warn "Lösche das vorhandene Schlüsselpaar und erstelle ein neues..."
            aws ec2 delete-key-pair --region $region --key-name $KEY_NAME
            
            # Neues Schlüsselpaar erstellen
            log "Erstelle neues Schlüsselpaar '$KEY_NAME' in $region..."
            if ! aws ec2 create-key-pair --region $region --key-name $KEY_NAME --query 'KeyMaterial' --output text > "$TEMP_KEY_FILE"; then
                error "Fehler beim Erstellen des Schlüsselpaars in $region."
                return 1
            fi
            
            # Versuche, die temporäre Datei an die gewünschte Stelle zu kopieren
            if ! cp "$TEMP_KEY_FILE" "$KEY_FILE" 2>/dev/null; then
                warn "Konnte Schlüsseldatei nicht nach '$KEY_FILE' kopieren. Verwende stattdessen: $TEMP_KEY_FILE"
                KEY_FILE="$TEMP_KEY_FILE"
            fi
            
            chmod 400 "$KEY_FILE"
            log "Schlüsselpaar erstellt und in '$KEY_FILE' gespeichert."
        fi
    else
        # Sicherstellen, dass kein Schlüsselpaar mit diesem Namen existiert
        aws ec2 delete-key-pair --region $region --key-name $KEY_NAME 2>/dev/null
        
        log "Erstelle neues Schlüsselpaar '$KEY_NAME' in $region..."
        
        # Zuerst in temporäre Datei schreiben
        if ! aws ec2 create-key-pair --region $region --key-name $KEY_NAME --query 'KeyMaterial' --output text > "$TEMP_KEY_FILE"; then
            error "Fehler beim Erstellen des Schlüsselpaars in $region. Bitte überprüfen Sie Ihre AWS-Berechtigungen."
            return 1
        fi
        
        # Versuche, die temporäre Datei an die gewünschte Stelle zu kopieren
        if ! cp "$TEMP_KEY_FILE" "$KEY_FILE" 2>/dev/null; then
            warn "Konnte Schlüsseldatei nicht nach '$KEY_FILE' kopieren. Verwende stattdessen: $TEMP_KEY_FILE"
            KEY_FILE="$TEMP_KEY_FILE"
        fi
        
        chmod 400 "$KEY_FILE"
        log "Schlüsselpaar erstellt und in '$KEY_FILE' gespeichert."
    fi

    # 2. Sicherheitsgruppe erstellen, falls sie noch nicht existiert
    SG_NAME="whisperx-sg"
    log "Prüfe auf vorhandene Sicherheitsgruppe in $region..."
    SG_ID=$(aws ec2 describe-security-groups --region $region --filters "Name=group-name,Values=$SG_NAME" --query "SecurityGroups[0].GroupId" --output text 2>/dev/null)

    if [[ "$SG_ID" != "None" && "$SG_ID" != "" ]]; then
        log "Sicherheitsgruppe '$SG_NAME' existiert bereits in $region mit ID: $SG_ID"
    else
        log "Erstelle neue Sicherheitsgruppe '$SG_NAME' in $region..."
        SG_ID=$(aws ec2 create-security-group --region $region \
            --group-name $SG_NAME \
            --description "Security Group for WhisperX Server" \
            --query "GroupId" --output text)
        
        log "Füge Sicherheitsregeln hinzu..."
        # SSH erlauben
        aws ec2 authorize-security-group-ingress --region $region \
            --group-id $SG_ID \
            --protocol tcp \
            --port 22 \
            --cidr 0.0.0.0/0 > /dev/null
        
        # WhisperX API auf Port 8000 erlauben
        aws ec2 authorize-security-group-ingress --region $region \
            --group-id $SG_ID \
            --protocol tcp \
            --port 8000 \
            --cidr 0.0.0.0/0 > /dev/null
        
        log "Sicherheitsgruppe erstellt mit ID: $SG_ID"
    fi

    # 3. AMI-ID für Amazon Linux 2 mit Deep Learning und NVIDIA Treibern
    log "Suche nach Deep Learning OSS Nvidia Driver AMI GPU PyTorch 2.8 (Amazon Linux 2023) in $region..."
    
    # Suche nach dem neuesten Deep Learning AMI
    AMI_ID=$(aws ec2 describe-images --region $region \
        --owners amazon \
        --filters "Name=name,Values=*Deep Learning OSS Nvidia Driver AMI GPU PyTorch 2.8 (Amazon Linux 2023)*" \
        --query "sort_by(Images, &CreationDate)[-1].ImageId" \
        --output text)

    if [[ -z "$AMI_ID" || "$AMI_ID" == "None" ]]; then
        error "Konnte kein passendes Deep Learning AMI in Region $region finden."
        return 1
    fi

    log "Gefundenes Deep Learning AMI: $AMI_ID"

    # AMI-Details anzeigen
    AMI_NAME=$(aws ec2 describe-images --region $region \
        --image-ids $AMI_ID \
        --query "Images[0].Name" \
        --output text)
    if [[ -n "$AMI_NAME" && "$AMI_NAME" != "None" ]]; then
        log "AMI Name: $AMI_NAME"
    else
        error "AMI Details konnten nicht abgerufen werden."
        return 1
    fi

    # 4. User-Data-Skript für die automatische Installation erstellen
    log "Erstelle User-Data-Skript..."
    USER_DATA=$(cat <<EOF
#!/bin/bash

# User-Data Skript für WhisperX Installation
# Logs werden in mehrere Dateien geschrieben für besseres Debugging

exec > >(tee /var/log/user-data.log) 2>&1
echo "=== WHISPERX INSTALLATION GESTARTET ==="
echo "Datum: $(date)"
echo "User: $(whoami)"
echo "Working Dir: $(pwd)"

# Cloud-init Status loggen
echo "Cloud-init Status: $(cloud-init status 2>/dev/null || echo 'unknown')"

echo "Starte WhisperX-Installation auf Amazon Linux 2023 mit NVIDIA Treibern..."

# Warte kurz bis System bereit ist
sleep 30

# System Update für Amazon Linux 2023
# echo "System Update..."
# yum update -y 2>&1

# Git und htop installieren falls nicht vorhanden
echo "Git und htop sowie nano und mc (midnight commander) Installation..."
yum install -y git htop nano mc 2>&1

# Docker installieren falls nicht vorhanden
if ! command -v docker &> /dev/null; then
    echo "Installiere Docker..."
    yum install -y docker 2>&1
    systemctl enable docker 2>&1
    systemctl start docker 2>&1
    usermod -aG docker ec2-user 2>&1
    echo "Docker installiert"
else
    echo "Docker bereits installiert"
    systemctl start docker 2>&1
fi

# Docker Status prüfen
echo "Docker Status:"
systemctl status docker --no-pager 2>&1
docker --version 2>&1

# Docker Compose v2 und Buildx installieren
echo "Installiere Docker Compose v2 und Buildx..."
# Verwende die korrekte URL für Linux x86_64
curl -L "https://github.com/docker/compose/releases/download/v2.40.1/docker-compose-linux-x86_64" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose

# Docker Buildx v0.18.0+ installieren (unterstützt --allow flag)
mkdir -p /usr/local/lib/docker/cli-plugins
curl -L "https://github.com/docker/buildx/releases/download/v0.18.0/buildx-v0.18.0.linux-amd64" -o /usr/local/lib/docker/cli-plugins/docker-buildx
chmod +x /usr/local/lib/docker/cli-plugins/docker-buildx

# Docker Buildx Builder erstellen
docker buildx create --use --name mybuilder

echo "Docker Compose v2 und Buildx v0.18.0+ installiert"

# ec2-user Setup-Skript schreiben
cat > /home/ec2-user/ec2_setup.sh <<'EOS'
#!/bin/bash

echo "=== EC2-USER SETUP GESTARTET ==="
cd /home/ec2-user

# Repository klonen (falls nicht vorhanden)
if [ ! -d "transcript-summarization" ]; then
    echo "Klone Repository..."
    git clone https://github.com/dmuehlberg/transcript-summarization.git 2>&1
    if [ $? -eq 0 ]; then
        echo "Repository erfolgreich geklont"
    else
        echo "FEHLER: Repository konnte nicht geklont werden"
        exit 1
    fi
else
    echo "Repository bereits vorhanden"
    cd transcript-summarization
    git pull 2>&1 || echo "Git pull fehlgeschlagen"
    cd ..
fi

cd transcript-summarization

# .env-Datei aus /tmp kopieren (falls verfügbar)
if [ -f "/tmp/.env" ]; then
    echo "Kopiere .env-Datei mit HF_TOKEN..."
    cp /tmp/.env .env
    echo "✅ .env-Datei mit HF_TOKEN kopiert"
else
    echo "⚠️ .env-Datei nicht verfügbar - erstelle Standard .env"
    cat > .env << 'ENVEOF'
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
    echo "Verfügbare Dateien:"
    ls -la 2>&1
    # Fallback: Lade das Skript herunter
    echo "Fallback: Lade container-setup.sh herunter..."
    wget https://raw.githubusercontent.com/dmuehlberg/transcript-summarization/main/container-setup.sh -O ./container-setup.sh 2>&1
    if [ -f "./container-setup.sh" ]; then
        chmod +x ./container-setup.sh
        echo "n" | timeout 1800 ./container-setup.sh 2>&1
    else
        echo "FEHLER: Fallback fehlgeschlagen"
    fi
fi

echo "=== EC2-USER SETUP ABGESCHLOSSEN ==="
EOS

chmod +x /home/ec2-user/ec2_setup.sh
sudo -u ec2-user bash /home/ec2-user/ec2_setup.sh

# Final Status
echo "=== INSTALLATION STATUS ==="
echo "Datum: $(date)"

echo "Docker Container:"
sudo -u ec2-user bash -c 'cd /home/ec2-user/transcript-summarization && docker-compose ps 2>/dev/null || echo "Container Status nicht verfügbar"'

PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
echo "Public IP: $PUBLIC_IP"
echo "API URL: http://$PUBLIC_IP:8000/docs"

curl -s http://localhost:8000/health 2>/dev/null && echo "API Health Check: OK" || echo "API Health Check: Nicht verfügbar"

echo "WhisperX-Setup abgeschlossen um $(date)"
echo "=== INSTALLATION LOG ENDE ==="

EOF
)

    # 5. EC2-Instanz erstellen
    log "Erstelle EC2-Instanz in $region..."
    INSTANCE_ID=$(aws ec2 run-instances --region $region \
        --image-id $AMI_ID \
        --instance-type $INSTANCE_TYPE \
        --key-name $KEY_NAME \
        --security-group-ids $SG_ID \
        --block-device-mappings "[{\"DeviceName\":\"/dev/sda1\",\"Ebs\":{\"VolumeSize\":128,\"VolumeType\":\"gp3\"}}]" \
        --user-data "$USER_DATA" \
        --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
        --query "Instances[0].InstanceId" \
        --output text)

    if [[ $? -ne 0 || -z "$INSTANCE_ID" ]]; then
        error "Fehler beim Erstellen der EC2-Instanz in $region."
        return 1
    fi

    log "EC2-Instanz wird erstellt mit ID: $INSTANCE_ID"
    log "Warte auf Instanzstart..."

    # 6. Warten, bis die Instanz läuft
    aws ec2 wait instance-running --region $region --instance-ids $INSTANCE_ID

    # 7. Public IP-Adresse abrufen
    PUBLIC_IP=$(aws ec2 describe-instances --region $region \
        --instance-ids $INSTANCE_ID \
        --query "Reservations[0].Instances[0].PublicIpAddress" \
        --output text)

    log "EC2-Instanz erfolgreich erstellt!"
    log "Instance ID: $INSTANCE_ID"
    log "Public IP: $PUBLIC_IP"
    log "SSH-Zugriff: ssh -i $KEY_FILE ec2-user@$PUBLIC_IP"
    log ""
    info "📋 NÄCHSTE SCHRITTE:"
    info "1. Warten Sie ~5-15 Minuten bis die Installation abgeschlossen ist"
    info "2. Installation-Logs prüfen:"
    info "   - User-Data Log: ssh -i $KEY_FILE ec2-user@$PUBLIC_IP 'sudo cat /var/log/user-data.log'"
    info "   - Cloud-init Log: ssh -i $KEY_FILE ec2-user@$PUBLIC_IP 'sudo tail -50 /var/log/cloud-init-output.log'"
    info "3. Container Status prüfen: ssh -i $KEY_FILE ec2-user@$PUBLIC_IP 'cd transcript-summarization && /usr/local/bin/docker-compose ps'"
    info "4. WhisperX API testen: http://$PUBLIC_IP:8000/docs"
    info "5. Health Check: curl http://$PUBLIC_IP:8000/health"
    info ""
    info "🔧 MANUELLE REPARATUR (falls nötig):"
    info "   ssh -i $KEY_FILE ec2-user@$PUBLIC_IP"
    info "   sudo ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose"
    info "   cd transcript-summarization && ./container-setup.sh"
    log ""
    warn "WICHTIG: Die automatische Installation läuft im Hintergrund!"
    warn "Bitte warten Sie mindestens 10 Minuten bevor Sie die API verwenden."

    # Automatisches Live-Monitoring der Installation
    log "Starte automatisches Live-Monitoring..."
    log "Drücken Sie Ctrl+C um zu beenden"

    # Warte bis SSH verfügbar ist
    log "Warte auf SSH-Verfügbarkeit..."
    for i in {1..30}; do
        if ssh -i "$KEY_FILE" -o ConnectTimeout=5 -o StrictHostKeyChecking=no ec2-user@$PUBLIC_IP 'echo "SSH bereit"' 2>/dev/null; then
            log "SSH Verbindung erfolgreich"
            break
        fi
        echo -n "."
        sleep 10
    done
    echo

    # SOFORT .env-Datei übertragen (falls verfügbar)
    if [[ -f ".env" ]]; then
        log "Übertrage .env-Datei mit HF_TOKEN SOFORT nach SSH-Verfügbarkeit..."
        if scp -i "$KEY_FILE" -o StrictHostKeyChecking=no .env ec2-user@$PUBLIC_IP:/tmp/.env 2>/dev/null; then
            log "✅ .env-Datei erfolgreich übertragen"
        else
            warn "⚠️  .env-Datei konnte nicht übertragen werden"
            warn "   Sie können die .env-Datei später manuell übertragen:"
            warn "   ./transfer_env.sh eu-central-1 whisperx-server"
        fi
    else
        warn "⚠️  .env-Datei nicht gefunden. HF_TOKEN wird nicht übertragen."
        warn "   Erstellen Sie eine .env-Datei mit HF_TOKEN=your_token"
    fi

    log "Live-Monitoring gestartet - verschiedene Log-Quellen:"
    
    # Intelligentes Log-Monitoring
    ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no ec2-user@$PUBLIC_IP "
        echo \"=== LOG MONITORING GESTARTET ===\"
        echo \"Zeit: \$(date)\"
        echo
        
        # Funktion für Log-Monitoring
        monitor_logs() {
            while true; do
                echo \"--- \$(date) ---\"
                
                # 1. User-Data Log (falls vorhanden)
                if [ -f /var/log/user-data.log ]; then
                    echo \"USER-DATA LOG (letzte 5 Zeilen):\"
                    sudo tail -5 /var/log/user-data.log
                else
                    echo \"User-Data Log: Noch nicht verfügbar\"
                fi
                
                # 2. Cloud-init Status
                echo \"CLOUD-INIT STATUS:\"
                sudo cloud-init status 2>/dev/null || echo \"unbekannt\"
                
                # 3. Docker Container Status (falls Setup läuft)
                if [ -d \"/home/ec2-user/transcript-summarization\" ]; then
                    cd /home/ec2-user/transcript-summarization
                    if command -v docker-compose &> /dev/null; then
                        echo \"CONTAINER STATUS:\"
                        docker-compose ps 2>/dev/null || echo \"Container noch nicht verfügbar\"
                        
                        echo \"BUILD LOGS (letzte 3 Zeilen):\"
                        docker-compose logs --tail=3 whisperx_cuda 2>/dev/null || echo \"Noch keine Build-Logs\"
                    elif [ -f \"/usr/local/bin/docker-compose\" ]; then
                        echo \"CONTAINER STATUS:\"
                        /usr/local/bin/docker-compose ps 2>/dev/null || echo \"Container noch nicht verfügbar\"
                        
                        echo \"BUILD LOGS (letzte 3 Zeilen):\"
                        /usr/local/bin/docker-compose logs --tail=3 whisperx_cuda 2>/dev/null || echo \"Noch keine Build-Logs\"
                    fi
                fi
                
                # 4. API Health Check
                echo \"API CHECK:\"
                if curl -s http://localhost:8000/health 2>/dev/null; then
                    echo \" - API verfügbar\"
                    echo \"\"
                    echo \"=== INSTALLATION ERFOLGREICH ABGESCHLOSSEN ===\"
                    echo \"Public IP: $PUBLIC_IP\"
                    echo \"SSH-Zugriff: ssh -i $KEY_FILE ec2-user@$PUBLIC_IP\"
                    echo \"API URL: http://$PUBLIC_IP:8000/docs\"
                    echo \"\"
                    echo \"Das Skript wird jetzt beendet.\"
                    exit 0
                else
                    echo \" - API noch nicht verfügbar\"
                fi
                
                echo \"================================\"
                sleep 30
            done
        }
        
        # Starte Monitoring
        monitor_logs
    "
    return 0
}

# Versuche die Instanz in verschiedenen Regionen zu erstellen
for region in "${REGIONS[@]}"; do
    if create_instance_in_region "$region"; then
        log "Instanz erfolgreich in Region $region erstellt!"
        exit 0
    else
        warn "Konnte keine Instanz in Region $region erstellen. Versuche nächste Region..."
    fi
done

error "Konnte in keiner der verfügbaren Regionen eine Instanz erstellen. Bitte versuchen Sie es später erneut oder kontaktieren Sie den AWS Support."
exit 1