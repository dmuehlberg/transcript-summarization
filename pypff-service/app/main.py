from fastapi import FastAPI
from pydantic import BaseModel
import os
from extractor import dump_calendar_properties, extract_all_calendar_entries, extract_attendees, extract_calendar_entries, list_calendar_entries, list_folders

app = FastAPI()

class FilePath(BaseModel):
    filename: str

@app.post("/extract/attendees/by-path")
def get_attendees(file: FilePath):
    file_path = os.path.join("/data/ost", file.filename)
    attendees = extract_attendees(file_path)
    return {"attendees": attendees}

@app.post("/extract/calendar/by-path")
def get_calendar(file: FilePath):
    file_path = os.path.join("/data/ost", file.filename)
    entries = extract_calendar_entries(file_path)
    return {"calendar": entries}


@app.post("/debug/folders")
def debug_folders(file: FilePath):
    file_path = os.path.join("/data/ost", file.filename)
    return list_folders(file_path)

@app.post("/extract/calendar/all")
def get_all_calendar(file: FilePath):
    path = os.path.join("/data/ost", file.filename)
    return {"calendar": extract_all_calendar_entries(path)}

@app.post("/debug/calendar/properties")
def debug_cal_props(file: FilePath, limit: int = 5):
    """
    Liefert alle Properties der ersten `limit` Kalender-Einträge.
    """
    path = os.path.join("/data/ost", file.filename)
    return dump_calendar_properties(path, max_items=limit)

@app.post("/extract/calendar/clean")
def get_clean_calendar(file: FilePath):
    path = os.path.join("/data/ost", file.filename)
    return {"calendar": list_calendar_entries(path)}