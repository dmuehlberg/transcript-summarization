FROM node:18-alpine

# Arbeitsverzeichnis setzen
WORKDIR /app

# Package.json kopieren
COPY package*.json ./

# Dependencies installieren und package-lock.json erstellen
RUN npm install --only=production && npm cache clean --force

# Source Code kopieren
COPY . .

# Logs Verzeichnis erstellen
RUN mkdir -p logs

# Port 3001 exponieren
EXPOSE 3001

# Server starten
CMD ["node", "server.js"] 