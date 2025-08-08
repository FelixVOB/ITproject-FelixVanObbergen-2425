from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from bson import ObjectId
from .schemas import (
    StudentIn, OpleidingIn, OPOIn, CategorieIn, AcademiejaarIn, ResultaatIn, StudentLogIn
)

bp = Blueprint("api", __name__)

def OID(x): 
    return ObjectId(x) if isinstance(x, str) else x

def ser(doc):
    if not doc:
        return doc
    out = dict(doc)
    for k in ("_id", "student_id", "opo_id", "opleiding_id", "categorie_id"):
        if k in out and isinstance(out[k], ObjectId):
            out[k] = str(out[k])
    return out

# ---- Ping ----
@bp.get("/ping")
def ping():
    return {"ok": True, "db": current_app.db.name}

# ---- Students ----
@bp.get("/students")
def list_students():
    docs = current_app.db.students.find().sort("studentnummer", 1).limit(200)
    return jsonify([ser(d) for d in docs])

@bp.post("/students")
def create_student():
    data = StudentIn(**(request.get_json(force=True) or {})).model_dump()
    # trim & normalize
    data["studentnummer"] = str(data["studentnummer"]).strip()
    data["voornaam"] = data["voornaam"].strip()
    data["achternaam"] = data["achternaam"].strip()
    if data.get("opleiding_id"):
        data["opleiding_id"] = OID(data["opleiding_id"])
    res = current_app.db.students.insert_one(data)
    data["_id"] = res.inserted_id
    return ser(data), 201

# ----- Opleidingen -----
@bp.get("/opleidingen")
def list_opleidingen():
    docs = current_app.db.opleidingen.find().sort("naam", 1)
    return jsonify([ser(d) for d in docs])

@bp.post("/opleidingen")
def create_opleiding():
    data = OpleidingIn(**(request.get_json(force=True) or {})).model_dump()
    res = current_app.db.opleidingen.insert_one(data)
    data["_id"] = res.inserted_id
    return ser(data), 201

# ----- OPO's (vakken) -----
@bp.get("/opos")
def list_opos():
    docs = current_app.db.opos.find().sort("afkorting", 1)
    return jsonify([ser(d) for d in docs])

@bp.post("/opos")
def create_opo():
    data = OPOIn(**(request.get_json(force=True) or {})).model_dump()
    res = current_app.db.opos.insert_one(data)
    data["_id"] = res.inserted_id
    return ser(data), 201

# ----- Categorieën -----
@bp.get("/categorien")
def list_categorien():
    docs = current_app.db.categorien.find().sort("afkorting", 1)
    return jsonify([ser(d) for d in docs])

@bp.post("/categorien")
def create_categorie():
    data = CategorieIn(**(request.get_json(force=True) or {})).model_dump()
    res = current_app.db.categorien.insert_one(data)
    data["_id"] = res.inserted_id
    return ser(data), 201

# ----- Academiejaren -----
@bp.get("/academiejaren")
def list_academiejaren():
    docs = current_app.db.academiejaren.find().sort("academiejaar", 1)
    return jsonify([ser(d) for d in docs])

@bp.post("/academiejaren")
def create_academiejaar():
    data = AcademiejaarIn(**(request.get_json(force=True) or {})).model_dump()
    res = current_app.db.academiejaren.insert_one(data)
    data["_id"] = res.inserted_id
    return ser(data), 201

# ----- Resultaten -----
@bp.get("/results")
def list_results():
    q = {}
    if sid := request.args.get("student_id"): q["student_id"] = OID(sid)
    if oid := request.args.get("opo_id"):     q["opo_id"] = OID(oid)
    if aj := request.args.get("academiejaar"): q["academiejaar"] = aj
    if kans := request.args.get("kans"):       q["kans"] = int(kans)
    if status := request.args.get("status"):   # "na" | "geslaagd" | "niet"
        if status == "na": q["cijfer"] = None
        elif status == "geslaagd": q["cijfer"] = {"$gte": 10}
        elif status == "niet": q["cijfer"] = {"$lt": 10}
    docs = current_app.db.resultaten.find(q).limit(500)
    return jsonify([ser(d) for d in docs])

@bp.post("/results")
def create_result():
    data = ResultaatIn(**(request.get_json(force=True) or {})).model_dump()
    data["student_id"] = OID(data["student_id"])
    data["opo_id"] = OID(data["opo_id"])
    res = current_app.db.resultaten.insert_one(data)  # unique index voorkomt dubbels
    data["_id"] = res.inserted_id
    return ser(data), 201

# ----- Student logs -----
@bp.get("/student-logs")
def list_logs():
    q = {}
    if sid := request.args.get("student_id"): q["student_id"] = OID(sid)
    docs = current_app.db.student_logs.find(q).sort("registratiedatum", -1).limit(500)
    return jsonify([ser(d) for d in docs])

@bp.post("/student-logs")
def create_log():
    payload = StudentLogIn(**(request.get_json(force=True) or {})).model_dump()
    payload["student_id"] = OID(payload["student_id"])
    if payload.get("categorie_id"):
        payload["categorie_id"] = OID(payload["categorie_id"])
    if not payload.get("registratiedatum"):
        payload["registratiedatum"] = datetime.utcnow()
    res = current_app.db.student_logs.insert_one(payload)
    payload["_id"] = res.inserted_id
    return ser(payload), 201
