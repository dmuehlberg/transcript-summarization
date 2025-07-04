#!/bin/bash

# Setze venv-Pfad
VENV="$HOME/flask-proxy-venv"

# Lege venv an, falls nicht vorhanden
if [ ! -d "$VENV" ]; then
    echo "Erstelle virtuelle Umgebung unter $VENV ..."
    python3 -m venv "$VENV"
fi

# Aktiviere venv
source "$VENV/bin/activate"

# Installiere Flask, falls nicht vorhanden
pip install --upgrade pip
pip install flask

# Kopiere das aktuelle AppleScript ins Home-Verzeichnis
cp "$(dirname "$0")/export_calendar.scpt" "$HOME/export_calendar.scpt"

# Starte den Proxy-Service
python3 $(dirname "$0")/applescript_proxy.py 