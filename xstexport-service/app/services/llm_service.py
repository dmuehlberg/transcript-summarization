import json
import logging
import httpx
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import pytz
from pathlib import Path

from app.services.llm_providers.base_provider import BaseLLMProvider

logger = logging.getLogger(__name__)


def create_llm_provider(config: Dict[str, Any]) -> BaseLLMProvider:
    """
    Factory-Funktion zum Erstellen eines LLM-Provider basierend auf der Konfiguration.
    
    Args:
        config: Dictionary mit LLM-Konfiguration (von get_llm_config())
    
    Returns:
        BaseLLMProvider Instanz (OllamaProvider oder OpenAIProvider)
    
    Raises:
        ValueError: Wenn der Provider nicht unterstützt wird
    """
    provider_name = config.get("provider", "ollama").lower()
    
    if provider_name == "ollama":
        from app.services.llm_providers.ollama_provider import OllamaProvider
        ollama_config = config.get("ollama", {})
        return OllamaProvider(
            base_url=ollama_config["base_url"],
            model=ollama_config["model"],
            timeout=ollama_config.get("timeout", 30.0),
            num_ctx=ollama_config.get("num_ctx")
        )
    elif provider_name == "openai":
        from app.services.llm_providers.openai_provider import OpenAIProvider
        openai_config = config.get("openai", {})
        api_key = openai_config.get("api_key", "")
        if not api_key:
            raise ValueError("OPENAI_API_KEY muss in .env gesetzt sein für OpenAI Provider")
        return OpenAIProvider(
            api_key=api_key,
            model=openai_config.get("model", "gpt-4"),
            timeout=openai_config.get("timeout", 30.0),
            use_structured_outputs=openai_config.get("use_structured_outputs", True)
        )
    else:
        raise ValueError(f"Unbekannter LLM-Provider: {provider_name}. Unterstützt: 'ollama', 'openai'")


class LLMService:
    """Service für LLM-basierte Konvertierung von Meeting-Series-Beschreibungen in RRULE-Felder."""
    
    def __init__(self, provider: BaseLLMProvider):
        """
        Initialisiert den LLMService.
        
        Args:
            provider: LLM-Provider-Instanz (OllamaProvider oder OpenAIProvider)
        """
        self.provider = provider
        logger.info(f"LLMService initialisiert mit Provider: {type(provider).__name__}")
    
    async def parse_meeting_series(
        self, 
        rhythm: str, 
        start_date: str, 
        end_date: str
    ) -> Dict[str, Any]:
        """
        Konvertiert eine Meeting-Series-Beschreibung in strukturierte RRULE-Felder.
        
        Args:
            rhythm: Textuelle Beschreibung des Rhythmus (z.B. "every Monday, Wednesday, and Friday")
            start_date: Startdatum im ISO 8601 Format
            end_date: Enddatum im ISO 8601 Format
        
        Returns:
            Dictionary mit RRULE-Feldern
        """
        logger.info(f"[TIMEZONE] parse_meeting_series: Input - rhythm = '{rhythm}', start_date = '{start_date}', end_date = '{end_date}'")
        
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(rhythm, start_date, end_date)
        
        # Max. 3 Retry-Versuche bei Netzwerkfehlern
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                response_text = await self._call_llm(system_prompt, user_prompt)
                
                rrule_data = self._parse_json_response(response_text)
                
                validated_data = self._validate_rrule_fields(rrule_data)
                logger.info(f"[TIMEZONE] parse_meeting_series: meeting_series_start_time (final) = {validated_data.get('meeting_series_start_time')}, Typ = {type(validated_data.get('meeting_series_start_time'))}")
                
                return validated_data
            except httpx.TimeoutException as e:
                last_error = e
                if attempt < max_retries - 1:
                    logger.warning(f"Timeout bei LLM-Request (Versuch {attempt + 1}/{max_retries}), retry...")
                else:
                    logger.error(f"LLM-Request Timeout nach {max_retries} Versuchen: {str(e)}")
                    raise
            except httpx.RequestError as e:
                last_error = e
                if attempt < max_retries - 1:
                    logger.warning(f"Netzwerkfehler bei LLM-Request (Versuch {attempt + 1}/{max_retries}), retry...")
                else:
                    logger.error(f"LLM-Request Netzwerkfehler nach {max_retries} Versuchen: {str(e)}")
                    raise
            except Exception as e:
                logger.error(f"Unerwarteter Fehler bei LLM-Request: {str(e)}")
                raise
        
        # Sollte nie erreicht werden, aber für Type-Checking
        raise Exception(f"LLM-Request fehlgeschlagen: {str(last_error)}")
    
    def _build_system_prompt(self) -> str:
        """Lädt den System-Prompt für das LLM aus einer externen Datei."""
        # Pfad zur Prompt-Datei relativ zum aktuellen Modul
        current_dir = Path(__file__).parent.parent  # app/services -> app
        prompt_file = current_dir / "config" / "llm_system_prompt.txt"
        
        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError:
            logger.error(f"System-Prompt-Datei nicht gefunden: {prompt_file}")
            raise FileNotFoundError(
                f"System-Prompt-Datei nicht gefunden: {prompt_file}. "
                "Bitte erstellen Sie die Datei app/config/llm_system_prompt.txt"
            )
        except Exception as e:
            logger.error(f"Fehler beim Laden des System-Prompts: {str(e)}")
            raise
    
    def _build_user_prompt(self, rhythm: str, start_date: str, end_date: str) -> str:
        """Erstellt den User-Prompt mit den Eingabedaten."""
        return f"""Input: "{rhythm}"
Start Date: {start_date}
End Date: {end_date}"""
    
    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """
        Ruft den konfigurierten LLM-Provider auf.
        
        Args:
            system_prompt: System-Prompt für das LLM
            user_prompt: User-Prompt mit den Eingabedaten
        
        Returns:
            Response-Text vom LLM
        """
        return await self.provider.generate(system_prompt, user_prompt)
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        Parst die JSON-Response vom LLM.
        
        Args:
            response: Roher Response-Text vom LLM
        
        Returns:
            Geparstes JSON als Dictionary
        """
        try:
            # Entferne mögliche Markdown-Code-Blöcke
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            
            return json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"JSON-Parsing-Fehler: {str(e)}, Response: {response[:200]}")
            # Fallback auf leere Werte
            return {
                "meeting_series_start_time": None,
                "meeting_series_end_time": None,
                "meeting_series_frequency": None,
                "meeting_series_interval": None,
                "meeting_series_weekdays": None,
                "meeting_series_monthday": None,
                "meeting_series_weekday_nth": None,
                "meeting_series_months": None,
                "meeting_series_exceptions": ""
            }
    
    def _validate_rrule_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validiert und korrigiert die RRULE-Felder.
        
        Args:
            data: Rohe Daten vom LLM
        
        Returns:
            Validierte und korrigierte Daten
        """
        validated = {}
        
        # meeting_series_start_time
        validated["meeting_series_start_time"] = self._convert_to_timestamp(
            data.get("meeting_series_start_time")
        )
        
        # meeting_series_end_time
        validated["meeting_series_end_time"] = self._convert_to_timestamp(
            data.get("meeting_series_end_time")
        )
        
        # meeting_series_frequency
        frequency = data.get("meeting_series_frequency", "").upper()
        if frequency in ["DAILY", "WEEKLY", "MONTHLY", "YEARLY"]:
            validated["meeting_series_frequency"] = frequency
        else:
            logger.warning(f"Ungültige frequency: {frequency}, setze auf null")
            validated["meeting_series_frequency"] = None
        
        # meeting_series_interval
        validated["meeting_series_interval"] = self._convert_to_int(
            data.get("meeting_series_interval"), default=1, min_value=1
        )
        
        # meeting_series_weekdays
        weekdays = data.get("meeting_series_weekdays")
        if weekdays:
            # Validiere und normalisiere Wochentage
            valid_days = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
            days_list = [d.strip().upper() for d in str(weekdays).split(",")]
            valid_days_list = [d for d in days_list if d in valid_days]
            validated["meeting_series_weekdays"] = ",".join(valid_days_list) if valid_days_list else None
        else:
            validated["meeting_series_weekdays"] = None
        
        # meeting_series_monthday
        validated["meeting_series_monthday"] = self._convert_to_int(
            data.get("meeting_series_monthday"), min_value=1, max_value=31
        )
        
        # meeting_series_weekday_nth
        validated["meeting_series_weekday_nth"] = self._convert_to_int(
            data.get("meeting_series_weekday_nth"), min_value=-5, max_value=5
        )
        
        # meeting_series_months
        months = data.get("meeting_series_months")
        if months:
            # Validiere Monate (1-12)
            months_list = [int(m.strip()) for m in str(months).split(",") if m.strip().isdigit()]
            valid_months = [m for m in months_list if 1 <= m <= 12]
            validated["meeting_series_months"] = ",".join(map(str, valid_months)) if valid_months else None
        else:
            validated["meeting_series_months"] = None
        
        # meeting_series_exceptions
        validated["meeting_series_exceptions"] = self._convert_to_text(
            data.get("meeting_series_exceptions", "")
        )
        
        return validated
    
    def _convert_to_timestamp(
        self, 
        value: Optional[str], 
        default_tz: str = "Europe/Berlin"
    ) -> Optional[datetime]:
        """
        Konvertiert einen ISO 8601 String zu einem datetime-Objekt in UTC.
        
        Args:
            value: ISO 8601 String oder None
            default_tz: Standard-Zeitzone falls keine angegeben ist
        
        Returns:
            datetime-Objekt in UTC oder None
        """
        if not value:
            return None
        
        try:
            # Ersetze 'Z' durch '+00:00' für UTC
            value_normalized = value.replace('Z', '+00:00')
            
            # Versuche ISO-Format zu parsen
            dt = datetime.fromisoformat(value_normalized)
            
            # Wenn keine Zeitzone vorhanden, füge Standard-Zeitzone hinzu
            if dt.tzinfo is None:
                tz = pytz.timezone(default_tz)
                dt = tz.localize(dt)
            
            # WICHTIG: Konvertiere zu UTC, da die Datenbank UTC erwartet
            if dt.tzinfo != pytz.UTC:
                dt = dt.astimezone(pytz.UTC)
            
            logger.info(f"[TIMEZONE] _convert_to_timestamp: Finaler Wert (UTC) = {dt}")
            return dt
        except Exception as e:
            logger.error(f"[TIMEZONE] Fehler bei Timestamp-Konvertierung '{value}': {str(e)}")
            return None
    
    def _convert_to_int(
        self, 
        value: Any, 
        default: Optional[int] = None,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None
    ) -> Optional[int]:
        """
        Konvertiert einen Wert zu einem Integer.
        
        Args:
            value: Zu konvertierender Wert
            default: Standardwert falls Konvertierung fehlschlägt
            min_value: Minimaler Wert (optional)
            max_value: Maximaler Wert (optional)
        
        Returns:
            Integer oder None
        """
        if value is None or value == "":
            return default
        
        try:
            int_value = int(value)
            
            if min_value is not None and int_value < min_value:
                logger.warning(f"Wert {int_value} ist kleiner als Minimum {min_value}, setze auf {min_value}")
                return min_value
            
            if max_value is not None and int_value > max_value:
                logger.warning(f"Wert {int_value} ist größer als Maximum {max_value}, setze auf {max_value}")
                return max_value
            
            return int_value
        except (ValueError, TypeError):
            logger.warning(f"Konnte '{value}' nicht zu Integer konvertieren, verwende default: {default}")
            return default
    
    def _convert_to_text(self, value: Any) -> str:
        """
        Konvertiert einen Wert zu einem Text-String.
        
        Args:
            value: Zu konvertierender Wert
        
        Returns:
            Text-String (leer wenn None)
        """
        if value is None or value == "":
            return ""
        return str(value).strip()
    
    async def check_availability(self) -> Tuple[bool, str]:
        """
        Prüft, ob der konfigurierte LLM-Provider erreichbar ist.
        
        Returns:
            Tuple (erfolgreich: bool, nachricht: str)
        """
        return await self.provider.check_availability()

