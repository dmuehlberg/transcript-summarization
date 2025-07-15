import os
import logging

logger = logging.getLogger(__name__)

def list_app_files():
    """
    Listet alle Dateien im Anwendungsverzeichnis auf.
    
    Returns:
        Dict mit einer Liste aller Dateien im Anwendungsverzeichnis
    """
    app_dir = "/app"
    file_list = []
    
    for root, dirs, files in os.walk(app_dir):
        for file in files:
            file_path = os.path.join(root, file)
            file_list.append(file_path)
    
    return {"files": file_list}

def list_data_directory_files():
    """
    Listet alle Dateien im Datenverzeichnis auf.
    
    Returns:
        Dict mit einer Liste aller Dateien im Datenverzeichnis,
        einschließlich Metadaten wie Dateigröße
    """
    data_dir = "/data/ost"
    file_list = []
    
    if os.path.exists(data_dir):
        for file in os.listdir(data_dir):
            file_path = os.path.join(data_dir, file)
            if os.path.isfile(file_path):
                file_size = os.path.getsize(file_path)
                file_list.append({
                    "name": file,
                    "path": file_path,
                    "size": file_size,
                    "size_mb": round(file_size / (1024 * 1024), 2)
                })
    else:
        logger.warning(f"Verzeichnis {data_dir} existiert nicht")
    
    return {"files": file_list, "directory": data_dir}