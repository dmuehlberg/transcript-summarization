from pydantic import BaseModel, Field
from typing import Optional
from fastapi import Form

class CalendarExtractionParams(BaseModel):
    format: str = Field(
        "csv", 
        description="Format der extrahierten Dateien: 'csv' oder 'native'"
    )
    target_folder: Optional[str] = Field(
        None, 
        description="Zielordner für die Extraktion (optional)"
    )
    
    # Form-Dependency für FastAPI
    @classmethod
    def as_form(cls, 
                format: str = Form("csv"),
                target_folder: Optional[str] = Form(None)
               ):
        return cls(format=format, target_folder=target_folder)