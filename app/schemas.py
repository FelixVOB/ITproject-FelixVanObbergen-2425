from pydantic import BaseModel, Field
from typing import Optional
from datetime import date

class StudentIn(BaseModel):
    studentnummer: str = Field(min_length=3, max_length=15)
    voornaam: str
    achternaam: str
    inschrijfdatum: Optional[date] = None
    opleiding_id: Optional[str] = None