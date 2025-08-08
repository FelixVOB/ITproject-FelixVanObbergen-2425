from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from bson import ObjectId

bp = Blueprint("api", __name__)

def _ser(doc):
    if not doc:
        return doc
    out = dict(doc)
    for k in ("_id", "student_id", "opo_id", "opleiding_id"):
        if k in out and isinstance(out[k], ObjectId):
            out[k] = str(out[k])
    return out

@bp.get("/ping")
def ping():
    return {"ok": True, "db": current_app.db.name}

@bp.get("/students")
def list_students():
    docs = list(current_app.db.students.find().sort("studentnummer", 1).limit(200))
    return jsonify([_ser(d) for d in docs])

@bp.post("/students")
def create_student():
    data = request.get_json(force=True) or {}
    # very light validation
    for f in ("studentnummer", "voornaam", "achternaam"):
        if not data.get(f):
            return {"error": f"Missing field: {f}"}, 400
    doc = {
        "studentnummer": str(data["studentnummer"]).strip(),
        "voornaam": data["voornaam"].strip(),
        "achternaam": data["achternaam"].strip(),
        "inschrijfdatum": data.get("inschrijfdatum") or datetime.utcnow().date().isoformat(),
        "opleiding_id": ObjectId(data["opleiding_id"]) if data.get("opleiding_id") else None,
    }
    res = current_app.db.students.insert_one(doc)
    doc["_id"] = res.inserted_id
    return _ser(doc), 201