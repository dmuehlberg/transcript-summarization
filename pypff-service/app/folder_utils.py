# folder_utils.py

def find_folder_by_path(root_folder, target_path):
    """
    Findet einen Ordner anhand seines Pfades.
    
    Args:
        root_folder: Der Root-Ordner
        target_path: Der Pfad zum gesuchten Ordner
        
    Returns:
        Der gefundene Ordner oder None
    """
    if not target_path or target_path == "/" or target_path == "":
        return root_folder
        
    # Pfadteile extrahieren
    parts = [p for p in target_path.split("/") if p]
    current = root_folder
    
    for part in parts:
        found = False
        # Unterordner durchsuchen
        for i in range(current.number_of_sub_folders):
            sub_folder = current.get_sub_folder(i)
            sub_name = sub_folder.name or "Unnamed"
            
            if sub_name.lower() == part.lower():
                current = sub_folder
                found = True
                break
        
        if not found:
            return None
    
    return current



def find_calendar_folders(folder, path="", results=None):
    """
    Findet alle Kalenderordner in der PST-Datei.
    
    Args:
        folder: Der aktuelle Ordner
        path: Der Pfad zum aktuellen Ordner
        results: Liste der gefundenen Kalenderordner
        
    Returns:
        Liste der gefundenen Kalenderordner mit Pfaden
    """
    if results is None:
        results = []
        
    folder_name = folder.name or "Unnamed"
    current_path = f"{path}/{folder_name}" if path else f"/{folder_name}"
    
    # Prüfen, ob es ein Kalenderordner ist
    is_calendar_folder = (
        "Calendar" in folder_name or 
        "Kalender" in folder_name or
        "calendar" in folder_name.lower()
    )
    
    if is_calendar_folder:
        results.append({
            "name": folder_name,
            "path": current_path,
            "folder": folder,
            "message_count": folder.number_of_sub_messages
        })
    
    # Rekursiv Unterordner durchsuchen
    for i in range(folder.number_of_sub_folders):
        try:
            sub_folder = folder.get_sub_folder(i)
            find_calendar_folders(sub_folder, current_path, results)
        except Exception as e:
            print(f"Fehler beim Durchsuchen von Unterordner {i} in {current_path}: {str(e)}")
    
    return results
pass