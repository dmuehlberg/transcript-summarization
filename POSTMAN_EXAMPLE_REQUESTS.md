# Postman Beispiel-Requests für Confluence Page Creation Endpoint

## Basis-Informationen

- **URL**: `http://localhost:8300/create-confluence-page`
- **Methode**: `POST`
- **Content-Type**: `application/json`

---

## Beispiel 1: Mit Markdown-Content (empfohlen für Tests)

### Request-Konfiguration

**URL:**
```
POST http://localhost:8300/create-confluence-page
```

**Headers:**
```
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "space_name": "My Space",
  "parent_page_title": "Parent Page",
  "content": "# Überschrift 1\n\nDies ist ein **fetter** und *kursiver* Text.\n\n## Überschrift 2\n\n- Erster Punkt\n- Zweiter Punkt\n- Dritter Punkt\n\n### Code-Beispiel\n\n```python\ndef hello_world():\n    print(\"Hello, World!\")\n```\n\n[Link zu Google](https://www.google.com)",
  "content_format": "markdown",
  "page_title": "Neue Test-Seite",
  "user": "deine-email@example.com",
  "site_url": "https://deine-domain.atlassian.net"
}
```

### Erwartete Response (Success)
```json
{
  "status": "success",
  "page_id": "123456",
  "page_title": "Neue Test-Seite",
  "page_url": "https://deine-domain.atlassian.net/wiki/spaces/SPACE/pages/123456/Neue+Test-Seite",
  "space_id": "65758",
  "parent_id": "654321",
  "content_format_used": "markdown"
}
```

---

## Beispiel 2: Mit Confluence Storage Format

### Request-Konfiguration

**URL:**
```
POST http://localhost:8300/create-confluence-page
```

**Headers:**
```
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "space_name": "My Space",
  "parent_page_title": null,
  "content": "<h1>Überschrift 1</h1><p>Dies ist ein <strong>fetter</strong> und <em>kursiver</em> Text.</p><h2>Überschrift 2</h2><ul><li>Erster Punkt</li><li>Zweiter Punkt</li><li>Dritter Punkt</li></ul>",
  "content_format": "storage",
  "page_title": "Seite im Storage Format",
  "user": "deine-email@example.com",
  "site_url": "https://deine-domain.atlassian.net"
}
```

---

## Beispiel 3: Ohne Parent Page (Root-Level)

### Request-Konfiguration

**URL:**
```
POST http://localhost:8300/create-confluence-page
```

**Headers:**
```
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "space_name": "My Space",
  "content": "# Neue Root-Seite\n\nDiese Seite wird auf Root-Level erstellt, da keine Parent Page angegeben wurde.",
  "content_format": "markdown",
  "page_title": "Root-Level Seite",
  "user": "deine-email@example.com",
  "site_url": "https://deine-domain.atlassian.net"
}
```

**Hinweis:** `parent_page_title` kann weggelassen werden oder auf `null` gesetzt werden.

---

## Beispiel 4: Minimaler Request (Storage Format als Standard)

### Request-Konfiguration

**URL:**
```
POST http://localhost:8300/create-confluence-page
```

**Headers:**
```
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "space_name": "My Space",
  "content": "<p>Minimaler Test-Content</p>",
  "page_title": "Minimale Test-Seite",
  "user": "deine-email@example.com",
  "site_url": "https://deine-domain.atlassian.net"
}
```

**Hinweis:** `content_format` wird standardmäßig auf `"storage"` gesetzt, wenn nicht angegeben.

---

## Beispiel 5: Mit erweitertem Markdown-Content

### Request-Konfiguration

**URL:**
```
POST http://localhost:8300/create-confluence-page
```

**Headers:**
```
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "space_name": "My Space",
  "parent_page_title": "Dokumentation",
  "content": "# Meeting-Protokoll\n\n**Datum:** 2025-01-15\n**Teilnehmer:** Max Mustermann, Anna Schmidt\n\n## Agenda\n\n1. Punkt 1\n2. Punkt 2\n3. Punkt 3\n\n## Diskussion\n\n### Thema A\n\n- Wichtiger Diskussionspunkt\n- Entscheidung getroffen\n\n### Thema B\n\n```\nCode-Beispiel:\nfunction test() {\n  return true;\n}\n```\n\n## Action Items\n\n- [ ] Task 1\n- [ ] Task 2\n- [x] Task 3 (erledigt)\n\n## Links\n\n- [Externe Ressource](https://example.com)\n- [Interne Dokumentation](./dokumentation)\n\n---\n\n*Erstellt automatisch am 2025-01-15*",
  "content_format": "markdown",
  "page_title": "Meeting-Protokoll 2025-01-15",
  "user": "deine-email@example.com",
  "site_url": "https://deine-domain.atlassian.net"
}
```

---

## Fehlerbeispiele

### Fehler 1: Space nicht gefunden

**Request:**
```json
{
  "space_name": "Nicht existierender Space",
  "content": "<p>Test</p>",
  "page_title": "Test",
  "user": "deine-email@example.com",
  "site_url": "https://deine-domain.atlassian.net"
}
```

**Response (404):**
```json
{
  "detail": "Space 'Nicht existierender Space' nicht gefunden"
}
```

### Fehler 2: API Key fehlt

**Response (500):**
```json
{
  "detail": "CONFLUENCE_API_KEY nicht in .env gefunden"
}
```

### Fehler 3: Authentifizierungsfehler

**Response (401):**
```json
{
  "detail": "Confluence API Authentifizierung fehlgeschlagen"
}
```

### Fehler 4: Ungültiges Content-Format

**Request:**
```json
{
  "space_name": "My Space",
  "content": "Test",
  "content_format": "html",
  "page_title": "Test",
  "user": "deine-email@example.com",
  "site_url": "https://deine-domain.atlassian.net"
}
```

**Response (400):**
```json
{
  "detail": "content_format muss 'markdown' oder 'storage' sein"
}
```

---

## Postman Collection Import (JSON)

Falls du eine Postman Collection importieren möchtest, hier ist die Collection-Definition:

```json
{
  "info": {
    "name": "Confluence Page Creation",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Create Page with Markdown",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"space_name\": \"My Space\",\n  \"parent_page_title\": \"Parent Page\",\n  \"content\": \"# Überschrift\\n\\nDies ist ein **fetter** Text.\",\n  \"content_format\": \"markdown\",\n  \"page_title\": \"Neue Test-Seite\",\n  \"user\": \"deine-email@example.com\",\n  \"site_url\": \"https://deine-domain.atlassian.net\"\n}"
        },
        "url": {
          "raw": "http://localhost:8300/create-confluence-page",
          "protocol": "http",
          "host": ["localhost"],
          "port": "8300",
          "path": ["create-confluence-page"]
        }
      }
    },
    {
      "name": "Create Page with Storage Format",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"space_name\": \"My Space\",\n  \"content\": \"<p>Test Content</p>\",\n  \"content_format\": \"storage\",\n  \"page_title\": \"Storage Format Test\",\n  \"user\": \"deine-email@example.com\",\n  \"site_url\": \"https://deine-domain.atlassian.net\"\n}"
        },
        "url": {
          "raw": "http://localhost:8300/create-confluence-page",
          "protocol": "http",
          "host": ["localhost"],
          "port": "8300",
          "path": ["create-confluence-page"]
        }
      }
    }
  ]
}
```

---

## Wichtige Hinweise

1. **API Key**: Stelle sicher, dass `CONFLUENCE_API_KEY` in der `.env`-Datei gesetzt ist
2. **Email**: Die `user`-Email muss mit dem Confluence-Account übereinstimmen, der den API Key erstellt hat
3. **Site URL**: Verwende die vollständige URL deiner Confluence-Instanz (ohne `/wiki` am Ende)
4. **Space Name**: Der Space-Name muss exakt übereinstimmen (case-insensitive)
5. **Parent Page**: Wenn die Parent Page nicht gefunden wird, wird die Seite auf Root-Level erstellt (kein Fehler)

## Test-Reihenfolge

1. Starte mit **Beispiel 4** (minimaler Request) um die Grundfunktionalität zu testen
2. Teste dann **Beispiel 1** (Markdown) um die Konvertierung zu prüfen
3. Teste **Beispiel 3** (ohne Parent) um Root-Level-Erstellung zu testen
4. Teste **Beispiel 5** (erweitertes Markdown) für komplexere Inhalte
