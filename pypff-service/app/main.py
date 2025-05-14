from fastapi import FastAPI
from pydantic import BaseModel
import os
from extractor import extract_attendees

app = FastAPI()

class FilePath(BaseModel):
    filename: str

@app.post("/extract/attendees/by-path")
def get_attendees(file: FilePath):
    file_path = os.path.join("/data/ost", file.filename)
    attendees = extract_attendees(file_path)
    return {"attendees": attendees}