# Implementierungskonzept: Confluence Page Creation Endpoint
## Übersicht
Implementierung eines neuen Endpoints im `processing_service`, der über die Confluence V2 API eine neue Seite in Confluence anlegt.
## Anforderungen
### Input-Parameter
- `space_name` (string): Name des Confluence Spaces (wird in Space ID umgewandelt)
- `parent_page_title` (string, optional): Titel der Parent Page (wird in parentId umgewandelt)
- `content` (string): Page Content (kann Markdown oder Confluence Storage Format sein)
- `content_format` (string, optional): Format des Contents - `"markdown"` oder `"storage"` (Standard: `"storage"`)
- `page_title` (string): Titel der neuen Seite
- `user` (string): Email-Adresse des Users, mit dem die Seite angelegt wird
- `site_url` (string): Base URL der Confluence-Instanz (z.B. `https://your-domain.atlassian.net`)
### Authentifizierung
- Confluence API Key aus `.env`-Datei (`CONFLUENCE_API_KEY`)
- Optional: `CONFLUENCE_EMAIL` in `.env` (falls nicht als Parameter übergeben)
- Basic Authentication: Base64-encoded `email:api_key`
## Technische Details
### 1. API-Endpunkte der Confluence V2 API
#### 1.1 Space ID Lookup
- **Endpoint**: `GET {site_url}/wiki/api/v2/spaces`
- **Zweck**: Alle Spaces abrufen und nach Name filtern
- **Pagination**: Unterstützung für paginierte Ergebnisse (max 100 pro Request)
- **Response**: Liste von Spaces mit `id`, `key`, `name`
- **Filterung**: Client-seitig nach `name` (case-insensitive)
#### 1.2 Parent Page ID Lookup
- **Endpoint**: `GET {site_url}/wiki/api/v2/pages?spaceId={space_id}&title={parent_page_title}`
- **Zweck**: Page anhand von Titel und Space ID finden
- **Response**: Page-Objekt mit `id` (wird als `parentId` verwendet)
- **Hinweis**: Wenn keine Parent Page angegeben, wird `parentId: null` verwendet (Root-Level)
#### 1.3 Page Creation
- **Endpoint**: `POST {site_url}/wiki/api/v2/pages`
- **Zweck**: Neue Seite erstellen
- **Request Body**:
  ```json
  {
    "spaceId": "string",
    "status": "current",
    "title": "string",
    "parentId": "string | null",
    "body": {
      "representation": "storage",
      "value": "string"
    }
  }
  ```
- **Response**: Erstellte Page mit `id`, `title`, `_links` etc.
### 2. Authentifizierung
#### 2.1 API Key Setup
- **Umgebungsvariable**: `CONFLUENCE_API_KEY` in `.env`
- **Optional**: `CONFLUENCE_EMAIL` in `.env` (falls nicht als Parameter übergeben)
- **Format**: Base64-encoded `{email}:{api_key}` für Basic Auth Header
#### 2.2 HTTP Header
```
Authorization: Basic {base64_encoded_credentials}
Content-Type: application/json
Accept: application/json
```
### 3. Implementierungsstruktur
#### 3.1 Neue Datei: `confluence.py`
- **Pfad**: `processing_service/app/confluence.py`
- **Funktionen**:
  - `get_space_id(site_url: str, space_name: str, auth_header: str) -> str`
  - `get_parent_page_id(site_url: str, space_id: str, parent_title: str, auth_header: str) -> Optional[str]`
  - `create_confluence_page(site_url: str, space_id: str, page_title: str, content: str, parent_id: Optional[str], auth_header: str) -> dict`
  - `build_auth_header(email: str, api_key: str) -> str`
  - `convert_markdown_to_storage_format(markdown_content: str) -> str`
#### 3.2 Erweiterung: `main.py`
- **Neuer Endpoint**: `POST /create-confluence-page`
- **Request Model**: `ConfluencePageRequest` (Pydantic)
- **Error Handling**: 
  - Space nicht gefunden
  - Parent Page nicht gefunden
  - API-Authentifizierungsfehler
  - Netzwerkfehler
#### 3.3 Erweiterung: `requirements.txt`
- **Neue Dependencies**: 
  - `requests` (falls noch nicht vorhanden)
  - `md2cf` (für Markdown-zu-Confluence-Storage-Format-Konvertierung)
  - `mistune` (Markdown-Parser, wird von md2cf verwendet)
  - `base64` (Standard-Library, kein zusätzliches Package)
### 4. Ablaufdiagramm
```
1. Request empfangen mit Parametern
   ↓
2. CONFLUENCE_API_KEY aus .env laden
   ↓
3. Auth Header erstellen (email:api_key, Base64)
   ↓
4. Content Format prüfen:
   - Wenn content_format == "markdown":
     → Markdown zu Confluence Storage Format konvertieren
   - Wenn content_format == "storage" oder nicht angegeben:
     → Content direkt verwenden
   ↓
5. Space ID Lookup:
   - GET /wiki/api/v2/spaces
   - Filter nach space_name
   - Space ID extrahieren
   ↓
6. Parent Page ID Lookup (falls parent_page_title angegeben):
   - GET /wiki/api/v2/pages?spaceId={space_id}&title={parent_title}
   - parentId extrahieren (oder null)
   ↓
7. Page Creation:
   - POST /wiki/api/v2/pages
   - Body: spaceId, title, parentId, body (storage format)
   ↓
8. Response zurückgeben:
   - Status: success/error
   - Page ID, URL, Titel
```
### 5. Error Handling
#### 5.1 Mögliche Fehlerfälle
- **401 Unauthorized**: API Key ungültig oder fehlt
- **403 Forbidden**: Keine Berechtigung für Space/Page
- **404 Not Found**: Space oder Parent Page nicht gefunden
- **400 Bad Request**: Ungültige Request-Parameter
- **500 Internal Server Error**: Netzwerkfehler, API-Fehler
#### 5.2 Error Response Format
```json
{
  "status": "error",
  "error_type": "space_not_found | parent_page_not_found | authentication_error | api_error",
  "detail": "Beschreibung des Fehlers",
  "confluence_response": {} // Optional: Original API Response
}
```
### 6. Request/Response Models
#### 6.1 Request Model
```python
class ConfluencePageRequest(BaseModel):
    space_name: str
    parent_page_title: Optional[str] = None
    content: str  # Content (Markdown oder Confluence Storage Format)
    content_format: Optional[str] = "storage"  # "markdown" oder "storage"
    page_title: str
    user: str  # Email-Adresse
    site_url: str  # z.B. "https://your-domain.atlassian.net"
```
#### 6.2 Success Response
```python
{
    "status": "success",
    "page_id": "123456",
    "page_title": "Titel der Seite",
    "page_url": "https://your-domain.atlassian.net/wiki/spaces/SPACE/pages/123456/Page+Title",
    "space_id": "65758",
    "parent_id": "654321" | null
}
```
### 7. Code-Struktur
#### 7.1 `confluence.py` - Funktionen
```python
import requests
import base64
from typing import Optional
import mistune
from md2cf.confluence_renderer import ConfluenceRenderer

def build_auth_header(email: str, api_key: str) -> str:
    """Erstellt Basic Auth Header für Confluence API"""
    credentials = f"{email}:{api_key}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"

def convert_markdown_to_storage_format(markdown_content: str) -> str:
    """
    Konvertiert Markdown-Content zu Confluence Storage Format.
    
    Args:
        markdown_content: Markdown-Text als String
    
    Returns:
        Content im Confluence Storage Format
    
    Raises:
        ValueError: Wenn Konvertierung fehlschlägt
    """
    try:
        renderer = ConfluenceRenderer(use_xhtml=True)
        confluence_mistune = mistune.Markdown(renderer=renderer)
        storage_format = confluence_mistune(markdown_content)
        return storage_format
    except Exception as e:
        raise ValueError(f"Fehler bei Markdown-Konvertierung: {str(e)}")
def get_space_id(site_url: str, space_name: str, auth_header: str) -> str:
    """
    Sucht Space ID anhand des Space-Namens.
    
    Args:
        site_url: Base URL der Confluence-Instanz
        space_name: Name des Spaces
        auth_header: Authorization Header (Basic Auth)
    
    Returns:
        Space ID als String
    
    Raises:
        HTTPException: Wenn Space nicht gefunden wird
    """
    # GET /wiki/api/v2/spaces mit Pagination
    # Filter nach name (case-insensitive)
    # Return space['id']
def get_parent_page_id(site_url: str, space_id: str, parent_title: str, auth_header: str) -> Optional[str]:
    """
    Sucht Parent Page ID anhand des Titels.
    
    Args:
        site_url: Base URL der Confluence-Instanz
        space_id: ID des Spaces
        parent_title: Titel der Parent Page
        auth_header: Authorization Header
    
    Returns:
        Parent Page ID oder None wenn nicht gefunden
    """
    # GET /wiki/api/v2/pages?spaceId={space_id}&title={parent_title}
    # Return page['id'] oder None
def create_confluence_page(
    site_url: str,
    space_id: str,
    page_title: str,
    content: str,
    parent_id: Optional[str],
    auth_header: str
) -> dict:
    """
    Erstellt eine neue Confluence-Seite.
    
    Args:
        site_url: Base URL der Confluence-Instanz
        space_id: ID des Spaces
        page_title: Titel der neuen Seite
        content: Content im Confluence Storage Format
        parent_id: ID der Parent Page (optional)
        auth_header: Authorization Header
    
    Returns:
        Response-Dict mit Page-Informationen
    """
    # POST /wiki/api/v2/pages
    # Body: spaceId, status: "current", title, parentId, body
    # Return response.json()
```
#### 7.2 `main.py` - Endpoint
```python
from .confluence import (
    build_auth_header,
    get_space_id,
    get_parent_page_id,
    create_confluence_page,
    convert_markdown_to_storage_format
)

class ConfluencePageRequest(BaseModel):
    space_name: str
    parent_page_title: Optional[str] = None
    content: str
    content_format: Optional[str] = "storage"  # "markdown" oder "storage"
    page_title: str
    user: str
    site_url: str

@app.post("/create-confluence-page")
async def create_confluence_page_endpoint(request: ConfluencePageRequest):
    """
    Erstellt eine neue Seite in Confluence über die V2 API.
    
    Steps:
    1. API Key aus .env laden
    2. Auth Header erstellen
    3. Content Format prüfen und ggf. konvertieren
    4. Space ID lookup
    5. Parent Page ID lookup (optional)
    6. Page erstellen
    7. Response zurückgeben
    """
    try:
        # 1. API Key laden
        api_key = os.getenv("CONFLUENCE_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="CONFLUENCE_API_KEY nicht in .env gefunden"
            )
        
        # 2. Email bestimmen (Parameter oder .env)
        email = request.user or os.getenv("CONFLUENCE_EMAIL")
        if not email:
            raise HTTPException(
                status_code=400,
                detail="User (Email) muss angegeben werden"
            )
        
        # 3. Auth Header erstellen
        auth_header = build_auth_header(email, api_key)
        
        # 4. Content Format prüfen und ggf. konvertieren
        content_format = request.content_format.lower() if request.content_format else "storage"
        if content_format not in ["markdown", "storage"]:
            raise HTTPException(
                status_code=400,
                detail="content_format muss 'markdown' oder 'storage' sein"
            )
        
        if content_format == "markdown":
            try:
                confluence_content = convert_markdown_to_storage_format(request.content)
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Fehler bei Markdown-Konvertierung: {str(e)}"
                )
        else:
            confluence_content = request.content
        
        # 5. Space ID lookup
        space_id = get_space_id(request.site_url, request.space_name, auth_header)
        
        # 6. Parent Page ID lookup (optional)
        parent_id = None
        if request.parent_page_title:
            parent_id = get_parent_page_id(
                request.site_url,
                space_id,
                request.parent_page_title,
                auth_header
            )
        
        # 7. Page erstellen
        page_response = create_confluence_page(
            request.site_url,
            space_id,
            request.page_title,
            confluence_content,
            parent_id,
            auth_header
        )
        
        # 8. Response formatieren
        return {
            "status": "success",
            "page_id": page_response.get("id"),
            "page_title": page_response.get("title"),
            "page_url": page_response.get("_links", {}).get("webui"),
            "space_id": space_id,
            "parent_id": parent_id,
            "content_format_used": content_format
        }
        
    except requests.exceptions.HTTPError as e:
        # Confluence API Fehler
        if e.response.status_code == 401:
            raise HTTPException(status_code=401, detail="Confluence API Authentifizierung fehlgeschlagen")
        elif e.response.status_code == 403:
            raise HTTPException(status_code=403, detail="Keine Berechtigung für diese Aktion")
        elif e.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Space oder Parent Page nicht gefunden")
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Confluence API Fehler: {e.response.text}"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```
### 8. .env Erweiterung
```env
# Confluence API Konfiguration
CONFLUENCE_API_KEY=your_api_key_here
CONFLUENCE_EMAIL=user@example.com  # Optional, kann auch als Parameter übergeben werden
```
### 10. Dependencies
#### 10.1 Neue Dependencies
- `requests` (falls noch nicht in requirements.txt)
- `md2cf` (für Markdown-zu-Confluence-Storage-Format-Konvertierung)
- `mistune` (Markdown-Parser, Dependency von md2cf)
#### 10.2 Prüfung
```bash
# Prüfen ob requests bereits vorhanden
grep -i requests processing_service/requirements.txt
```
### 11. Implementierungsreihenfolge
1. **Schritt 1**: `.env` erweitern (CONFLUENCE_API_KEY, optional CONFLUENCE_EMAIL)
2. **Schritt 2**: `requirements.txt` prüfen/erweitern (requests, md2cf, mistune)
3. **Schritt 3**: `confluence.py` erstellen mit Helper-Funktionen (inkl. Markdown-Konvertierung)
4. **Schritt 4**: `main.py` erweitern mit Endpoint und Request Model (inkl. content_format)
5. **Schritt 5**: Error Handling implementieren (inkl. Markdown-Konvertierungsfehler)
### 12. API-Dokumentation
#### 12.1 OpenAPI/Swagger
- Endpoint wird automatisch in FastAPI Docs verfügbar sein
- Request/Response Models werden dokumentiert
#### 12.2 Beispiel-Request

**Mit Confluence Storage Format:**
```json
POST /create-confluence-page
{
  "space_name": "My Space",
  "parent_page_title": "Parent Page",
  "content": "<p>This is the page content</p>",
  "content_format": "storage",
  "page_title": "New Page Title",
  "user": "user@example.com",
  "site_url": "https://your-domain.atlassian.net"
}
```

**Mit Markdown (wird automatisch konvertiert):**
```json
POST /create-confluence-page
{
  "space_name": "My Space",
  "parent_page_title": "Parent Page",
  "content": "# Heading\n\nThis is **bold** and *italic* text.",
  "content_format": "markdown",
  "page_title": "New Page Title",
  "user": "user@example.com",
  "site_url": "https://your-domain.atlassian.net"
}
```
### 13. Hinweise
#### 13.1 Content Format
- Content kann im **Confluence Storage Format** oder **Markdown** übergeben werden
- Storage Format verwendet HTML-ähnliche Tags (z.B. `<p>`, `<h1>`, `<ac:structured-macro>`)
- Markdown wird automatisch zu Confluence Storage Format konvertiert (via `md2cf` Library)
- Standard-Format ist `"storage"` (wenn `content_format` nicht angegeben)
- Unterstützte Markdown-Features: Überschriften, Fettdruck, Kursiv, Listen, Code-Blöcke, Links, etc.
- Komplexe Confluence-Macros müssen weiterhin im Storage Format übergeben werden
#### 13.2 Pagination
- Space Lookup kann viele Spaces zurückgeben
- Pagination beachten: `_links.next` in Response prüfen
- Max 100 Spaces pro Request (Standard)
#### 13.3 Performance
- Space Lookup kann bei vielen Spaces langsam sein
- Optional: Caching der Space IDs (nicht Teil der initialen Implementierung)
#### 13.4 URL-Encoding
- Parent Page Title muss URL-encoded werden für GET Request
- Python `urllib.parse.quote()` verwenden
#### 13.5 Markdown-Konvertierung Details
- **Library**: `md2cf` mit `mistune` Markdown-Parser
- **Renderer**: `ConfluenceRenderer(use_xhtml=True)` für XHTML-kompatible Ausgabe
- **Unterstützte Markdown-Features**:
  - Überschriften (`# H1`, `## H2`, etc.)
  - Textformatierung (`**bold**`, `*italic*`, `~~strikethrough~~`)
  - Listen (geordnet und ungeordnet)
  - Code-Blöcke (mit Syntax-Highlighting)
  - Inline-Code (Backticks)
  - Links (`[text](url)`)
  - Bilder (`![alt](url)`)
  - Tabellen (Markdown-Tabellen-Syntax)
- **Nicht unterstützt** (müssen im Storage Format übergeben werden):
  - Confluence-spezifische Macros (z.B. `<ac:structured-macro>`)
  - Erweiterte Formatierungen (Farben, spezielle Layouts)
  - Confluence-Inline-Macros
- **Fehlerbehandlung**: Bei Konvertierungsfehlern wird ein 400 Bad Request mit Fehlerdetails zurückgegeben
## Zusammenfassung
Dieses Konzept beschreibt die vollständige Implementierung eines Endpoints zur Erstellung von Confluence-Seiten über die V2 API. Der Endpoint:
- Konvertiert Space Name → Space ID
- Konvertiert Parent Page Title → Parent ID (optional)
- Unterstützt Content in Markdown oder Confluence Storage Format (automatische Konvertierung)
- Erstellt die Seite mit angegebenem Content
- Verwendet API Key Authentication aus .env
- Bietet umfassendes Error Handling
Die Implementierung folgt den bestehenden Patterns im `processing_service` (FastAPI, Pydantic Models, Error Handling).

### Markdown-Konvertierung
- Verwendet `md2cf` Library mit `mistune` Parser
- Automatische Konvertierung von Markdown zu Confluence Storage Format
- Unterstützt gängige Markdown-Features (Überschriften, Formatierung, Listen, Code-Blöcke)
- Fehlerbehandlung bei Konvertierungsproblemen

