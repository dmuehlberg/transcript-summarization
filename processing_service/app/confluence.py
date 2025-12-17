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
        site_url: Base URL der Confluence-Instanz (z.B. https://domain.atlassian.net)
        space_name: Name des Spaces
        auth_header: Authorization Header (Basic Auth)
    
    Returns:
        Space ID als String
    
    Raises:
        requests.exceptions.HTTPError: Wenn Space nicht gefunden wird oder API-Fehler auftritt
    """
    # Stelle sicher, dass site_url kein trailing slash hat
    site_url = site_url.rstrip('/')
    url = f"{site_url}/wiki/api/v2/spaces"
    headers = {
        "Authorization": auth_header,
        "Accept": "application/json"
    }
    
    all_spaces = []
    next_url = url
    
    # Pagination: Alle Spaces abrufen
    while next_url:
        params = {"limit": 100}
        response = requests.get(next_url, headers=headers, params=params)
        
        # Detailliertes Error Handling
        if response.status_code == 404:
            # Prüfe ob es ein Problem mit der URL oder der API-Version ist
            error_detail = f"Endpoint nicht gefunden. URL: {next_url}, Status: {response.status_code}"
            try:
                error_body = response.text
                if error_body:
                    error_detail += f", Response: {error_body}"
            except:
                pass
            raise requests.exceptions.HTTPError(error_detail, response=response)
        elif response.status_code == 401:
            raise requests.exceptions.HTTPError(
                "Authentifizierung fehlgeschlagen. Bitte prüfe API Key und Email.",
                response=response
            )
        elif response.status_code == 403:
            raise requests.exceptions.HTTPError(
                "Keine Berechtigung für diese Aktion.",
                response=response
            )
        
        response.raise_for_status()
        
        data = response.json()
        all_spaces.extend(data.get("results", []))
        
        # Prüfe ob es weitere Seiten gibt
        links = data.get("_links", {})
        next_url = links.get("next")
        if next_url:
            # next ist ein relativer Pfad, muss mit base_url kombiniert werden
            if not next_url.startswith("http"):
                next_url = f"{site_url}{next_url}"
    
    # Filter nach Name (case-insensitive)
    for space in all_spaces:
        if space.get("name", "").lower() == space_name.lower():
            return space["id"]
    
    # Space nicht gefunden - ValueError werfen, wird in main.py behandelt
    raise ValueError(f"Space '{space_name}' nicht gefunden")


def get_parent_page_id(site_url: str, space_id: str, parent_title: str, auth_header: str) -> Optional[str]:
    """
    Sucht Parent Page ID anhand des Titels.
    
    Args:
        site_url: Base URL der Confluence-Instanz (z.B. https://domain.atlassian.net)
        space_id: ID des Spaces
        parent_title: Titel der Parent Page
        auth_header: Authorization Header
    
    Returns:
        Parent Page ID oder None wenn nicht gefunden
    
    Raises:
        requests.exceptions.HTTPError: Bei API-Fehlern
    """
    # Stelle sicher, dass site_url kein trailing slash hat
    site_url = site_url.rstrip('/')
    url = f"{site_url}/wiki/api/v2/pages"
    headers = {
        "Authorization": auth_header,
        "Accept": "application/json"
    }
    
    # URL-Encoding wird automatisch von requests durchgeführt
    params = {
        "spaceId": space_id,
        "title": parent_title
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        data = response.json()
        results = data.get("results", [])
        
        if results:
            # Erste passende Page zurückgeben
            return results[0].get("id")
        else:
            return None
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return None
        raise


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
        site_url: Base URL der Confluence-Instanz (z.B. https://domain.atlassian.net)
        space_id: ID des Spaces
        page_title: Titel der neuen Seite
        content: Content im Confluence Storage Format
        parent_id: ID der Parent Page (optional)
        auth_header: Authorization Header
    
    Returns:
        Response-Dict mit Page-Informationen
    
    Raises:
        requests.exceptions.HTTPError: Bei API-Fehlern
    """
    # Stelle sicher, dass site_url kein trailing slash hat
    site_url = site_url.rstrip('/')
    url = f"{site_url}/wiki/api/v2/pages"
    headers = {
        "Authorization": auth_header,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    body = {
        "spaceId": space_id,
        "status": "current",
        "title": page_title,
        "body": {
            "representation": "storage",
            "value": content
        }
    }
    
    # Parent ID hinzufügen, falls angegeben
    if parent_id:
        body["parentId"] = parent_id
    
    response = requests.post(url, headers=headers, json=body)
    response.raise_for_status()
    
    return response.json()
