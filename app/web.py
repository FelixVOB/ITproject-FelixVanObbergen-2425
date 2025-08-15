# app/web.py
from flask import Blueprint, render_template, request, redirect, url_for, current_app
from bson import ObjectId

web = Blueprint("web", __name__)

@web.get("/")
def home():
    db = current_app.db
    counts = {
        "students": db.students.count_documents({}),
        "opos": db.opos.count_documents({}),
        "resultaten": db.resultaten.count_documents({}),
    }
    return render_template("home.html", counts=counts)

@web.get("/students")
def students_page():
    db = current_app.db
    students = list(db.students.find().sort("studentnummer", 1).limit(200))
    for s in students:
        s["_id"] = str(s["_id"])
        if isinstance(s.get("opleiding_id"), ObjectId):
            s["opleiding_id"] = str(s["opleiding_id"])
    opleidingen = list(db.opleidingen.find().sort("naam", 1))
    # map id -> naam for display
    opleidings_map = {str(o["_id"]): o["naam"] for o in opleidingen}
    return render_template(
        "students.html",
        students=students,
        opleidingen=opleidingen,
        opleidings_map=opleidings_map,
    )

@web.post("/students")
def students_create():
    db = current_app.db
    doc = {
        "studentnummer": (request.form.get("studentnummer") or "").strip(),
        "voornaam": (request.form.get("voornaam") or "").strip(),
        "achternaam": (request.form.get("achternaam") or "").strip(),
        "inschrijfdatum": (request.form.get("inschrijfdatum") or "").strip() or None,
    }
    opleiding_id = request.form.get("opleiding_id") or None
    if opleiding_id:
        doc["opleiding_id"] = ObjectId(opleiding_id)
    else:
        doc["opleiding_id"] = None
    db.students.insert_one(doc)
    return redirect(url_for("web.students_page"))
