# WhisperX AWS-Deployment

Dieses Verzeichnis enthält Skripte zum Deployment des WhisperX-Services auf AWS mit GPU-Unterstützung. Mit diesen Skripten kannst du schnell eine EC2-Instanz mit T4 oder A10G GPU erstellen, das Repository klonen, alle notwendigen Komponenten installieren und den WhisperX-Container starten.

## Voraussetzungen

- AWS-Konto mit Berechtigungen zum Erstellen von EC2-Instanzen
- AWS CLI installiert und konfiguriert (`aws configure`)
- jq installiert (auf macOS: `brew install jq`)

## Verfügbare Skripte

### 1. `deploy_whisperx_aws.sh`

Hauptskript zum Erstellen, Überwachen und Löschen von EC2-Instanzen.

#### Verwendung:

```bash
./deploy_whisperx_aws.sh [Optionen]
```

#### Optionen:

- `-h, --help`: Zeigt die Hilfe an
- `-a, --action ACTION`: Aktion: create, delete oder status (Standard: create)
- `-n, --name NAME`: Name der EC2-Instanz (Standard: whisperx-server)
- `-r, --region REGION`: AWS-Region (Standard: eu-central-1)
- `-g, --gpu-type TYPE`: GPU-Typ: t4 oder a10g (Standard: t4)

#### Beispiele:

```bash
# Erstellen einer EC2-Instanz mit T4 GPU
./deploy_whisperx_aws.sh --action create --gpu-type t4

# Erstellen einer EC2-Instanz mit A10G GPU
./deploy_whisperx_aws.sh --action create --gpu-type a10g

# Status einer EC2-Instanz anzeigen
./deploy_whisperx_aws.sh --action status

# EC2-Instanz löschen
./deploy_whisperx_aws.sh --action delete
```

### 2. `monitor_whisperx_installation.sh`

Überwacht die Installation von WhisperX auf einer EC2-Instanz und zeigt den Status an.

#### Verwendung:

```bash
./monitor_whisperx_installation.sh [Optionen]
```

#### Optionen:

- `-h, --help`: Zeigt die Hilfe an
- `-n, --name NAME`: Name der EC2-Instanz (Standard: whisperx-server)
- `-r, --region REGION`: AWS-Region (Standard: eu-central-1)
- `-k, --key KEY`: Pfad zum SSH-Schlüssel (Standard: whisperx-key.pem)
- `-i, --ip IP`: IP-Adresse der Instanz (optional)

### 3. `cleanup_aws_resources.sh`

Bereinigt alle AWS-Ressourcen, die mit WhisperX zusammenhängen (EC2-Instanzen, Sicherheitsgruppen, Schlüsselpaare).

#### Verwendung:

```bash
./cleanup_aws_resources.sh [Optionen]
```

#### Optionen:

- `-h, --help`: Zeigt die Hilfe an
- `-n, --name NAME`: Name der EC2-Instanz (Standard: whisperx-server)
- `-r, --region REGION`: AWS-Region (Standard: eu-central-1)
- `-f, --force`: Keine Bestätigung abfragen

## Deployment-Workflow

1. **Instanz erstellen**:
   ```bash
   ./deploy_whisperx_aws.sh --action create --gpu-type t4
   ```

2. **Installationsfortschritt überwachen**:
   ```bash
   ./monitor_whisperx_installation.sh
   ```

3. **Status überprüfen**:
   ```bash
   ./deploy_whisperx_aws.sh --action status
   ```

4. **Instanz bei Bedarf löschen**:
   ```bash
   ./deploy_whisperx_aws.sh --action delete
   ```

## WhisperX-Service

Nach erfolgreicher Installation ist der WhisperX-Service unter folgender URL erreichbar:

```
http://<EC2-PUBLIC-IP>:8000
```

Die API-Dokumentation ist verfügbar unter:

```
http://<EC2-PUBLIC-IP>:8000/docs
```

## Hinweise

- Die Installation kann einige Minuten dauern, besonders das Herunterladen der Docker-Images und der WhisperX-Modelle.
- Die Skripte verwenden standardmäßig die HuggingFace-Token aus deiner `.env`-Datei. Du kannst diesen Token im `user_data.sh`-Skript anpassen.
- Die EC2-Instanz wird mit einer 50GB-Festplatte erstellt, um genügend Platz für die Docker-Images und die WhisperX-Modelle zu haben.
- Die Sicherheitsgruppe öffnet die Ports 22 (SSH) und 8000 (WhisperX API) für alle IP-Adressen. In einer Produktionsumgebung solltest du den Zugriff einschränken.

## Kostenschätzung

Die ungefähren Kosten für die AWS-Instanzen (ohne Datenübertragung, Stand: Mai 2025):

- **g4dn.xlarge (T4 GPU)**: ~$0.53 pro Stunde
- **g5.xlarge (A10G GPU)**: ~$1.10 pro Stunde

Denke daran, die Instanz zu löschen, wenn du sie nicht mehr benötigst, um unnötige Kosten zu vermeiden.