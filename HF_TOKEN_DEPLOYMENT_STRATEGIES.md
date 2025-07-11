# Hugging Face Token Deployment Strategien

Dieses Dokument beschreibt verschiedene sichere Methoden, um den Hugging Face Token (HF_TOKEN) auf AWS-Instanzen bereitzustellen, ohne ihn ins GitHub-Repository zu committen.

## 🚨 Wichtige Sicherheitshinweise

- **NIEMALS** den HF_TOKEN direkt ins GitHub-Repository committen
- Der Token wird automatisch invalidated, wenn er öffentlich wird
- Verwenden Sie immer sichere Methoden zur Token-Übertragung

## 📋 Implementierte Lösung: AWS Systems Manager Parameter Store

### ✅ Vorteile
- **Sicher**: Token wird verschlüsselt gespeichert
- **AWS-Nativ**: Integriert in AWS IAM und Security
- **Automatisch**: Token wird beim Deployment automatisch bereitgestellt
- **Zentral**: Token kann von mehreren Instanzen verwendet werden

### 🔧 Implementierung

#### 1. Token im Parameter Store speichern
```bash
# Token aus .env lesen und im Parameter Store speichern
./update_hf_token.sh eu-central-1
```

#### 2. Automatisches Deployment
Das `create_aws_instance.sh` Skript:
- Liest den HF_TOKEN aus der lokalen `.env`-Datei
- Speichert ihn sicher im AWS Parameter Store
- Die AWS-Instanz ruft den Token beim Start automatisch ab
- Erstellt die `.env`-Datei mit dem Token

#### 3. Token auf bestehenden Instanzen aktualisieren
```bash
# Token im Parameter Store aktualisieren
./update_hf_token.sh eu-central-1

# Optional: Token auch auf laufenden Instanzen aktualisieren
# (Wird interaktiv angeboten)
```

### 🔐 Sicherheitsfeatures
- **Verschlüsselung**: Token wird als `SecureString` gespeichert
- **IAM-Berechtigungen**: Nur autorisierte Benutzer können auf den Parameter zugreifen
- **Audit-Logging**: Alle Zugriffe werden protokolliert
- **Automatische Rotation**: Token kann einfach aktualisiert werden

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

### Token wird nicht abgerufen
```bash
# Parameter Store Status prüfen
aws ssm describe-parameters --region eu-central-1 \
    --parameter-filters "Key=Name,Values=/whisperx/hf_token"

# Parameter Wert prüfen (nur für Debugging)
aws ssm get-parameter --region eu-central-1 \
    --name "/whisperx/hf_token" --with-decryption
```

### IAM-Berechtigungen prüfen
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ssm:GetParameter",
                "ssm:PutParameter"
            ],
            "Resource": "arn:aws:ssm:eu-central-1:*:parameter/whisperx/*"
        }
    ]
}
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

2. **Parameter Store aktualisieren**:
   ```bash
   ./update_hf_token.sh eu-central-1
   ```

3. **Instanz erstellen**:
   ```bash
   ./create_aws_instance.sh --action create --gpu-type t4
   ```

4. **Verifizieren**:
   ```bash
   # API testen
   curl http://instance-ip:8000/health
   ```

## 🚀 Nächste Schritte

- [ ] Token-Rotation automatisch implementieren
- [ ] Monitoring für Token-Zugriffe einrichten
- [ ] Backup-Strategie für Token entwickeln
- [ ] Dokumentation für Team-Mitglieder erstellen 