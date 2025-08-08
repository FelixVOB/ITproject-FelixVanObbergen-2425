from pymongo import ASCENDING

def ensure_indexes(db):
    # unique studentnummer
    db.students.create_index([("studentnummer", ASCENDING)], unique=True)

    # OPO constraints
    db.opos.create_index([("afkorting", ASCENDING)], unique=True)
    db.opos.create_index([("code", ASCENDING)], unique=True)

    # Resultaten: prevent duplicates per (student, opo, academiejaar, kans)
    db.resultaten.create_index(
        [("student_id", ASCENDING), ("opo_id", ASCENDING),
         ("academiejaar", ASCENDING), ("kans", ASCENDING)],
        unique=True
    )

    # Categorieën: afkorting uniek
    db.categorien.create_index([("afkorting", ASCENDING)], unique=True)
