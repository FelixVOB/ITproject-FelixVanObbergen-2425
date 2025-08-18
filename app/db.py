# app/db.py
from pymongo import ASCENDING

def ensure_indexes(db):
    # users
    db.users.create_index([("email", ASCENDING)], unique=True)

    # students
    db.students.create_index([("studentnummer", ASCENDING)], unique=True)

    # opleidingen
    db.opleidingen.create_index([("naam", ASCENDING)], unique=True)

    # OPO's
    db.opos.create_index([("afkorting", ASCENDING)], unique=True)
    db.opos.create_index([("code", ASCENDING)], unique=True)

    # categorieën
    db.categorien.create_index([("afkorting", ASCENDING)], unique=True)

    # academiejaren
    db.academiejaren.create_index([("academiejaar", ASCENDING)], unique=True)

    # resultaten: 1 resultaat per (student, opo, jaar, kans)
    db.resultaten.create_index(
        [("student_id", ASCENDING),
         ("opo_id", ASCENDING),
         ("academiejaar", ASCENDING),
         ("kans", ASCENDING)],
        unique=True
    )

    # student_logs: handige query-indexen
    db.student_logs.create_index([("student_id", ASCENDING)])
    db.student_logs.create_index([("registratiedatum", ASCENDING)])
