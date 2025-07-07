import os
import shutil
from typing import Optional
import logging

logger = logging.getLogger(__name__)

def cleanup_temp_dir(dir_path: str, ignore_errors: bool = True) -> None:
    """
    Räumt ein temporäres Verzeichnis auf und entfernt es.
    
    Args:
        dir_path: Pfad zum Verzeichnis
        ignore_errors: Ob Fehler ignoriert werden sollen
    """
    try:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path, ignore_errors=ignore_errors)
            logger.debug(f"Cleaned up temporary directory: {dir_path}")
    except Exception as e:
        logger.error(f"Error during cleanup of directory {dir_path}: {str(e)}")
        if not ignore_errors:
            raise