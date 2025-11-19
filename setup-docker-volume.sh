#!/bin/bash
#
# Docker Volume Migration und Docker Compose Installation
# Dieses Skript wird vom User-Data Bootstrap geladen und ausgeführt.

set -euo pipefail

LOG_FILE="/var/log/setup-docker-volume.log"
exec >> "${LOG_FILE}" 2>&1

echo "=== DOCKER VOLUME SETUP GESTARTET ==="
echo "Datum: $(date)"

DOCKER_VOLUME_MOUNT="/mnt/docker-data"

echo "=== Docker Volume Migration ==="
echo "Warte auf zusätzliche EBS-Volumes..."
MAX_WAIT=60
WAIT_COUNT=0
DOCKER_VOLUME_DEVICE=""

while [ $WAIT_COUNT -lt $MAX_WAIT ] && [ -z "$DOCKER_VOLUME_DEVICE" ]; do
    for device in /dev/nvme*n1; do
        if [ -b "$device" ] 2>/dev/null; then
            IS_MOUNTED=false
            if command -v findmnt >/dev/null 2>&1; then
                if findmnt "$device" >/dev/null 2>&1; then
                    IS_MOUNTED=true
                fi
            else
                if df | grep -q "$device"; then
                    IS_MOUNTED=true
                fi
            fi

            if [ "$IS_MOUNTED" = "false" ]; then
                if command -v findmnt >/dev/null 2>&1; then
                    ROOT_DEVICE=$(findmnt -n -o SOURCE / 2>/dev/null || echo "")
                else
                    ROOT_DEVICE=$(df / | tail -1 | awk '{print $1}' 2>/dev/null || echo "")
                fi
                if [ "$device" != "$ROOT_DEVICE" ] && [ "$device" != "/dev/nvme0n1" ]; then
                    DOCKER_VOLUME_DEVICE="$device"
                    echo "Gefundenes zusätzliches Volume: $DOCKER_VOLUME_DEVICE"
                    break 2
                fi
            fi
        fi
    done

    if [ -z "$DOCKER_VOLUME_DEVICE" ]; then
        for device in /dev/nvme1n1 /dev/nvme2n1 /dev/nvme3n1; do
            if [ -b "$device" ] 2>/dev/null; then
                IS_MOUNTED=false
                if command -v findmnt >/dev/null 2>&1; then
                    if findmnt "$device" >/dev/null 2>&1; then
                        IS_MOUNTED=true
                    fi
                else
                    if df | grep -q "$device"; then
                        IS_MOUNTED=true
                    fi
                fi
                if [ "$IS_MOUNTED" = "false" ]; then
                    DOCKER_VOLUME_DEVICE="$device"
                    echo "Verwende Fallback-Device: $DOCKER_VOLUME_DEVICE"
                    break 2
                fi
            fi
        done
    fi

    if [ -z "$DOCKER_VOLUME_DEVICE" ]; then
        sleep 2
        WAIT_COUNT=$((WAIT_COUNT + 2))
        if [ $((WAIT_COUNT % 10)) -eq 0 ]; then
            echo "Warte auf zusätzliche Volumes... ($WAIT_COUNT/$MAX_WAIT Sekunden)"
        fi
    fi
done

if [ -n "$DOCKER_VOLUME_DEVICE" ] && [ -b "$DOCKER_VOLUME_DEVICE" ]; then
    echo "Zusätzliches Volume $DOCKER_VOLUME_DEVICE gefunden"

    if command -v blkid >/dev/null 2>&1; then
        if ! blkid "$DOCKER_VOLUME_DEVICE" > /dev/null 2>&1; then
            echo "Formatiere $DOCKER_VOLUME_DEVICE mit XFS..."
            mkfs.xfs -f "$DOCKER_VOLUME_DEVICE" 2>&1
            echo "Formatierung abgeschlossen"
        else
            echo "Volume ist bereits formatiert"
        fi
    else
        if file -s "$DOCKER_VOLUME_DEVICE" | grep -q "filesystem"; then
            echo "Volume ist bereits formatiert"
        else
            echo "Formatiere $DOCKER_VOLUME_DEVICE mit XFS..."
            mkfs.xfs -f "$DOCKER_VOLUME_DEVICE" 2>&1
            echo "Formatierung abgeschlossen"
        fi
    fi

    mkdir -p "$DOCKER_VOLUME_MOUNT" 2>&1

    if ! mountpoint -q "$DOCKER_VOLUME_MOUNT"; then
        echo "Mounte $DOCKER_VOLUME_DEVICE auf $DOCKER_VOLUME_MOUNT..."
        mount "$DOCKER_VOLUME_DEVICE" "$DOCKER_VOLUME_MOUNT" 2>&1
        echo "Volume erfolgreich gemountet"
    else
        echo "Volume ist bereits gemountet"
    fi

    echo "Stoppe Docker für Migration..."
    systemctl stop docker 2>&1

    if [ -d "/var/lib/docker" ] && [ "$(ls -A /var/lib/docker 2>/dev/null)" ]; then
        echo "Migriere bestehende Docker-Daten..."
        if [ ! "$(ls -A $DOCKER_VOLUME_MOUNT 2>/dev/null)" ]; then
            rsync -av /var/lib/docker/ "$DOCKER_VOLUME_MOUNT/" 2>&1
            echo "Daten-Migration abgeschlossen"
        else
            echo "Docker-Daten bereits auf Volume vorhanden"
        fi
    else
        echo "Keine bestehenden Docker-Daten zum Migrieren"
        mkdir -p "$DOCKER_VOLUME_MOUNT" 2>&1
    fi

    if [ -d "/var/lib/docker" ] && [ ! -L "/var/lib/docker" ]; then
        echo "Erstelle Backup und Symlink..."
        mv /var/lib/docker /var/lib/docker.backup 2>&1
    fi

    if [ ! -e "/var/lib/docker" ]; then
        ln -s "$DOCKER_VOLUME_MOUNT" /var/lib/docker 2>&1
        echo "Symlink /var/lib/docker -> $DOCKER_VOLUME_MOUNT erstellt"
    fi

    sleep 2

    VOLUME_UUID=""
    if command -v blkid >/dev/null 2>&1; then
        VOLUME_UUID=$(blkid -s UUID -o value "$DOCKER_VOLUME_DEVICE" 2>/dev/null || echo "")
        if [ -z "$VOLUME_UUID" ]; then
            sleep 3
            VOLUME_UUID=$(blkid -s UUID -o value "$DOCKER_VOLUME_DEVICE" 2>/dev/null || echo "")
        fi
    elif command -v lsblk >/dev/null 2>&1; then
        VOLUME_UUID=$(lsblk -no UUID "$DOCKER_VOLUME_DEVICE" 2>/dev/null || echo "")
    fi

    if [ -n "$VOLUME_UUID" ]; then
        if ! grep -q "$DOCKER_VOLUME_MOUNT" /etc/fstab; then
            echo "UUID=$VOLUME_UUID $DOCKER_VOLUME_MOUNT xfs defaults,nofail 0 2" >> /etc/fstab
            echo "Eintrag in /etc/fstab hinzugefügt (UUID: $VOLUME_UUID)"
        else
            echo "Eintrag bereits in /etc/fstab vorhanden"
        fi
    else
        if ! grep -q "$DOCKER_VOLUME_MOUNT" /etc/fstab; then
            echo "$DOCKER_VOLUME_DEVICE $DOCKER_VOLUME_MOUNT xfs defaults,nofail 0 2" >> /etc/fstab
            echo "Eintrag in /etc/fstab hinzugefügt (mit Device-Name)"
        else
            echo "Eintrag bereits in /etc/fstab vorhanden"
        fi
    fi

    echo "Starte Docker..."
    systemctl start docker 2>&1
    sleep 3

    if systemctl is-active --quiet docker; then
        echo "✅ Docker Volume Migration erfolgreich!"
        echo "Docker Root Dir: $(docker info 2>/dev/null | grep 'Docker Root Dir' | awk '{print $4}')"
        df -h "$DOCKER_VOLUME_MOUNT" 2>&1
    else
        echo "⚠️ Warnung: Docker konnte nicht gestartet werden, verwende Standard-Verzeichnis"
        if [ -L "/var/lib/docker" ]; then
            rm /var/lib/docker
            if [ -d "/var/lib/docker.backup" ]; then
                mv /var/lib/docker.backup /var/lib/docker
            else
                mkdir -p /var/lib/docker
            fi
            systemctl start docker 2>&1
        fi
    fi
else
    echo "Kein zusätzliches Volume gefunden - verwende Standard /var/lib/docker"
fi

echo "=== Docker Volume Migration abgeschlossen ==="

echo "Installiere Docker Compose v2 und Buildx..."
curl -L "https://github.com/docker/compose/releases/download/v2.40.1/docker-compose-linux-x86_64" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose

mkdir -p /usr/local/lib/docker/cli-plugins
curl -L "https://github.com/docker/buildx/releases/download/v0.18.0/buildx-v0.18.0.linux-amd64" -o /usr/local/lib/docker/cli-plugins/docker-buildx
chmod +x /usr/local/lib/docker/cli-plugins/docker-buildx

docker buildx create --use --name mybuilder || true

echo "Docker Compose v2 und Buildx v0.18.0+ installiert"
echo "=== DOCKER VOLUME SETUP ABGESCHLOSSEN ==="

