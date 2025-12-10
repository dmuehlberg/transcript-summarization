"""
Abstrakte Basisklasse für LLM-Provider.
"""

from abc import ABC, abstractmethod
from typing import Tuple


class BaseLLMProvider(ABC):
    """
    Abstrakte Basisklasse für LLM-Provider-Implementierungen.
    
    Alle Provider müssen diese Schnittstelle implementieren, um mit LLMService
    kompatibel zu sein.
    """
    
    @abstractmethod
    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """
        Ruft den LLM-Provider auf und gibt die Response zurück.
        
        Args:
            system_prompt: System-Prompt für das LLM
            user_prompt: User-Prompt mit den Eingabedaten
        
        Returns:
            Response-Text vom LLM (sollte JSON-String sein)
        """
        pass
    
    @abstractmethod
    async def check_availability(self) -> Tuple[bool, str]:
        """
        Prüft, ob der Provider erreichbar ist und konfiguriert ist.
        
        Returns:
            Tuple (erfolgreich: bool, nachricht: str)
        """
        pass
