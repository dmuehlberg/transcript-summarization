# Multi-stage build für React App
FROM node:18-alpine AS builder

# Arbeitsverzeichnis setzen
WORKDIR /app

# Package.json und package-lock.json kopieren
COPY package*.json ./

# Dependencies installieren
RUN npm ci --only=production

# Source Code kopieren
COPY . .

# Build erstellen
RUN npm run build

# Production Stage
FROM nginx:alpine

# Nginx Konfiguration kopieren
COPY nginx.conf /etc/nginx/nginx.conf

# Build-Artefakte aus dem Builder-Stage kopieren
COPY --from=builder /app/dist /usr/share/nginx/html

# Port 8400 exponieren
EXPOSE 8400

# Nginx starten
CMD ["nginx", "-g", "daemon off;"] 