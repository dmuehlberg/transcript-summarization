# Hugging Face Token Deployment Strategien

Dieses Dokument beschreibt verschiedene sichere Methoden, um den Hugging Face Token (HF_TOKEN) auf AWS-Instanzen bereitzustellen, ohne ihn ins GitHub-Repository zu committen.

## 🚨 Wichtige Sicherheitshinweise

- **NIEMALS** den HF_TOKEN direkt ins GitHub-Repository committen
- Der Token wird automatisch invalidated, wenn er öffentlich wird
- Verwenden Sie immer sichere Methoden zur Token-Übertragung

## 📋 Implementierte Lösung: SCP-basierte Token-Übertragung

### ✅ Vorteile
- **Einfach**: Nur wenige Zeilen Code
- **Sicher**: Token wird direkt übertragen, nicht in AWS gespeichert
- **Kontrolliert**: Sie haben volle Kontrolle über den Transfer
- **Sofort**: Token ist sofort verfügbar, keine AWS-API-Aufrufe nötig
- **Keine AWS-Abhängigkeiten**: Funktioniert ohne zusätzliche AWS-Services

### 🔧 Implementierung

#### 1. Automatische Token-Übertragung beim Deployment
Das `create_aws_instance.sh` Skript:
- Erstellt die AWS-Instanz wie gewohnt
- Wartet auf SSH-Verfügbarkeit
- Überträgt automatisch die lokale `.env`-Datei per SCP
- Startet den Container neu, falls bereits läuft

#### 2. Manuelle Token-Übertragung auf bestehende Instanzen
```bash
# .env-Datei auf bestehende Instanz übertragen
./transfer_env.sh eu-central-1 whisperx-server
```

#### 3. Manuelle Token-Übertragung (direkt)
```bash
# Direkte SCP-Übertragung
scp -i whisperx-key.pem .env ec2-user@INSTANCE_IP:/home/ec2-user/transcript-summarization/
```

### 🔐 Sicherheitsfeatures
- **Direkte Übertragung**: Token wird nur zwischen Ihrem System und der Instanz übertragen
- **SSH-Verschlüsselung**: Sichere Übertragung über SSH
- **Lokale Kontrolle**: Token bleibt unter Ihrer Kontrolle
- **Keine AWS-Speicherung**: Token wird nicht in AWS gespeichert

## 🔄 Alternative Strategien

### Strategie 2: AWS Secrets Manager
```bash
# Token in Secrets Manager speichern
aws secretsmanager create-secret \
    --name "whisperx/hf_token" \
    --secret-string "{\"HF_TOKEN\":\"$HF_TOKEN\"}" \
    --region eu-central-1

# Token abrufen
aws secretsmanager get-secret-value \
    --secret-id "whisperx/hf_token" \
    --region eu-central-1 \
    --query "SecretString" --output text
```

**Vorteile**: Erweiterte Sicherheitsfeatures, automatische Rotation
**Nachteile**: Höhere Kosten, komplexere Implementierung

### Strategie 3: Environment Variables über User Data
```bash
# Token direkt in User Data (weniger sicher)
USER_DATA="
#!/bin/bash
export HF_TOKEN='$HF_TOKEN'
# ... rest of setup
"
```

**Vorteile**: Einfach zu implementieren
**Nachteile**: Token ist im User Data sichtbar, weniger sicher

### Strategie 4: S3 Bucket mit verschlüsselter Datei
```bash
# Token verschlüsselt in S3 speichern
echo "$HF_TOKEN" | gpg --encrypt --recipient your-key > hf_token.gpg
aws s3 cp hf_token.gpg s3://your-bucket/whisperx/hf_token.gpg

# Token auf Instanz entschlüsseln
aws s3 cp s3://your-bucket/whisperx/hf_token.gpg .
gpg --decrypt hf_token.gpg > .env
```

**Vorteile**: Sehr sicher, vollständige Kontrolle über Verschlüsselung
**Nachteile**: Komplex, zusätzliche Infrastruktur erforderlich

### Strategie 5: SSH-basierte Token-Übertragung
```bash
# Token über SSH übertragen
scp -i key.pem .env ec2-user@instance-ip:/home/ec2-user/transcript-summarization/
```

**Vorteile**: Einfach, direkte Kontrolle
**Nachteile**: Manuell, nicht automatisiert

## 🛠️ Troubleshooting

### Token wird nicht übertragen
```bash
# SSH-Verbindung testen
ssh -i whisperx-key.pem ec2-user@INSTANCE_IP 'echo "SSH OK"'

# Repository-Verzeichnis prüfen
ssh -i whisperx-key.pem ec2-user@INSTANCE_IP 'ls -la /home/ec2-user/transcript-summarization/'

# .env-Datei manuell übertragen
scp -i whisperx-key.pem .env ec2-user@INSTANCE_IP:/home/ec2-user/transcript-summarization/
```

### Container startet nicht
```bash
# Logs prüfen
docker-compose logs whisperx_cuda

# .env-Datei prüfen
cat .env | grep HF_TOKEN

# Token manuell setzen
export HF_TOKEN="your_token_here"
docker-compose up -d whisperx_cuda
```

### Container startet nicht
```bash
# Logs prüfen
docker-compose logs whisperx_cuda

# .env-Datei prüfen
cat .env | grep HF_TOKEN

# Token manuell setzen
export HF_TOKEN="your_token_here"
docker-compose up -d whisperx_cuda
```

## 📝 Best Practices

1. **Regelmäßige Token-Rotation**: Aktualisieren Sie den Token regelmäßig
2. **Minimale Berechtigungen**: Verwenden Sie IAM-Rollen mit minimalen Berechtigungen
3. **Monitoring**: Überwachen Sie Token-Zugriffe
4. **Backup-Strategie**: Haben Sie einen Plan für Token-Verlust
5. **Dokumentation**: Dokumentieren Sie alle Token-bezogenen Prozesse

## 🔄 Workflow für neue Instanzen

1. **Token vorbereiten**:
   ```bash
   # Token in .env-Datei definieren
   echo "HF_TOKEN=your_token_here" >> .env
   ```

2. **Instanz erstellen** (Token wird automatisch übertragen):
   ```bash
   ./create_aws_instance.sh --action create --gpu-type t4
   ```

3. **Verifizieren**:
   ```bash
   # API testen
   curl http://instance-ip:8000/health
   ```

## 🔄 Workflow für bestehende Instanzen

1. **Token vorbereiten** (falls noch nicht geschehen):
   ```bash
   # Token in .env-Datei definieren
   echo "HF_TOKEN=your_token_here" >> .env
   ```

2. **Token übertragen**:
   ```bash
   ./transfer_env.sh eu-central-1 whisperx-server
   ```

3. **Verifizieren**:
   ```bash
   # API testen
   curl http://instance-ip:8000/health
   ```

## 🚀 Nächste Schritte

- [ ] Token-Rotation automatisch implementieren
- [ ] Monitoring für Token-Zugriffe einrichten
- [ ] Backup-Strategie für Token entwickeln
- [ ] Dokumentation für Team-Mitglieder erstellen 