from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime

class StudentIn(BaseModel):
    studentnummer: str = Field(min_length=3, max_length=15)
    voornaam: str
    achternaam: str
    inschrijfdatum: Optional[date] = None
    opleiding_id: Optional[str] = None

class OpleidingIn(BaseModel):
    naam: str
    dag_avond: str = Field(pattern="^(dag|avond)$")

class OPOIn(BaseModel):
    afkorting: str
    naam: str
    code: str

class CategorieIn(BaseModel):
    afkorting: str
    omschrijving: Optional[str] = None

class AcademiejaarIn(BaseModel):
    academiejaar: str = Field(pattern=r"^\d{4}-\d{4}$")

class ResultaatIn(BaseModel):
    student_id: str
    opo_id: str
    academiejaar: str
    cijfer: Optional[float] = None   # None = NA
    kans: int = Field(ge=1, le=2)

class StudentLogIn(BaseModel):
    student_id: str
    categorie_id: Optional[str] = None
    beschrijving: str
    registratiedatum: Optional[datetime] = None
