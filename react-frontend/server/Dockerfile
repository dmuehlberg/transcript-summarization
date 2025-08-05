FROM node:18-alpine

# Arbeitsverzeichnis setzen
WORKDIR /app

# Package.json kopieren
COPY package*.json ./

# Dependencies installieren
RUN npm ci --only=production

# Source Code kopieren
COPY . .

# Logs Verzeichnis erstellen
RUN mkdir -p logs

# Port 3001 exponieren
EXPOSE 3001

# Server starten
CMD ["node", "server.js"] 