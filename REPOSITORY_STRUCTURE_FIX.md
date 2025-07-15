# Repository-Struktur Fix: Doppelter Klon behoben

## 🐛 **Problem identifiziert**

Das `container-setup.sh` Skript führte zu einer doppelten Repository-Struktur:

```
/home/ec2-user/
└── transcript-summarization/          # Erster Klon (User-Data-Skript)
    └── transcript-summarization/      # Zweiter Klon (container-setup.sh)
        └── docker-compose.yml
        └── container-setup.sh
        └── ...
```

**Ursache**: 
- User-Data-Skript klont das Repository nach `/home/ec2-user/transcript-summarization/`
- User-Data-Skript wechselt in das Repository: `cd transcript-summarization`
- User-Data-Skript ruft `./container-setup.sh` auf
- container-setup.sh klont das Repository erneut in `./transcript-summarization/`

## ✅ **Lösung implementiert**

### **Änderungen in `container-setup.sh`:**

1. **Repository-Klon-Logik entfernt**
   - Kein `git clone` mehr im container-setup.sh
   - Kein `cd transcript-summarization` mehr

2. **Verzeichnis-Validierung hinzugefügt**
   - Prüft, ob `docker-compose.yml` vorhanden ist
   - Stellt sicher, dass das Skript im richtigen Verzeichnis ausgeführt wird

3. **Bessere Fehlerbehandlung**
   - `error()` Funktion hinzugefügt
   - Klare Fehlermeldungen bei falschem Verzeichnis

### **Neue Verzeichnisstruktur:**

```
/home/ec2-user/
└── transcript-summarization/          # Einziger Klon
    └── docker-compose.yml
    └── container-setup.sh
    └── whisperX-FastAPI-cuda/
    └── ...
```

## 🔧 **Vorteile der Lösung**

### **1. Saubere Verzeichnisstruktur**
- Nur ein Repository-Klon
- Keine verschachtelten Verzeichnisse
- Klare, vorhersagbare Pfade

### **2. Bessere Performance**
- Weniger Speicherplatz benötigt
- Schnellere Git-Operationen
- Weniger Netzwerk-Traffic

### **3. Wiederverwendbarkeit**
- `container-setup.sh` funktioniert weiterhin als eigenständiges Skript
- Kann sowohl automatisiert als auch manuell verwendet werden

### **4. Konsistente Updates**
- Git-Pull erfolgt nur an einer Stelle
- Keine Inkonsistenzen zwischen verschiedenen Repository-Kopien

## 🚀 **Verwendung**

### **Automatisiert (User-Data-Skript):**
```bash
# Repository wird automatisch geklont
# container-setup.sh wird im richtigen Verzeichnis aufgerufen
./container-setup.sh
```

### **Manuell:**
```bash
# Repository manuell klonen
git clone https://github.com/dmuehlberg/transcript-summarization.git
cd transcript-summarization

# Setup ausführen
./container-setup.sh
```

## 🧪 **Tests**

### **Verzeichnis-Validierung:**
```bash
# Im richtigen Verzeichnis
cd /home/ec2-user/transcript-summarization
./container-setup.sh  # ✅ Funktioniert

# Im falschen Verzeichnis
cd /home/ec2-user
./transcript-summarization/container-setup.sh  # ❌ Fehler: docker-compose.yml nicht gefunden
```

### **Docker-Setup:**
```bash
# Container bauen und starten
docker-compose build whisperx_cuda
docker-compose up -d whisperx_cuda
```

## 📝 **Changelog**

### **Version 2.0 (Aktuell)**
- ✅ Doppelter Repository-Klon behoben
- ✅ Verzeichnis-Validierung hinzugefügt
- ✅ Bessere Fehlerbehandlung
- ✅ Saubere Verzeichnisstruktur

### **Version 1.0 (Vorher)**
- ❌ Doppelter Repository-Klon
- ❌ Verschachtelte Verzeichnisstruktur
- ❌ Inkonsistente Updates

## 🔍 **Monitoring**

Nach der Implementierung können Sie die Verzeichnisstruktur prüfen:

```bash
# SSH zur Instanz
ssh -i whisperx-key.pem ec2-user@INSTANCE_IP

# Verzeichnisstruktur prüfen
ls -la /home/ec2-user/
ls -la /home/ec2-user/transcript-summarization/

# Container-Status prüfen
cd /home/ec2-user/transcript-summarization
docker-compose ps
```

Die Verzeichnisstruktur sollte jetzt sauber und ohne Duplikate sein! 