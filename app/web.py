# app/web.py
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    current_app, flash, abort
)
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from datetime import datetime

web = Blueprint("web", __name__)

# ---------- Home (dashboard) ----------
@web.get("/")
def home():
    db = current_app.db
    counts = {
        "students": db.students.count_documents({}),
        "opos": db.opos.count_documents({}),
        "resultaten": db.resultaten.count_documents({}),
    }
    return render_template("home.html", counts=counts)

# ---------- Students ----------
@web.get("/students")
def students_page():
    db = current_app.db
    students = list(db.students.find().sort([("achternaam", 1), ("voornaam", 1)]))
    for s in students:
        s["_id"] = str(s["_id"])
        if s.get("opleiding_id") and isinstance(s["opleiding_id"], ObjectId):
            s["opleiding_id"] = str(s["opleiding_id"])

    opleidingen = list(db.opleidingen.find().sort("naam", 1))
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
        "inschrijfdatum": (request.form.get("inschrijfdatum") or "").strip(),
    }
    if oid := (request.form.get("opleiding_id") or "").strip():
        try:
            doc["opleiding_id"] = ObjectId(oid)
        except Exception:
            pass

    try:
        db.students.insert_one(doc)
        flash("Student toegevoegd.", "success")
    except DuplicateKeyError:
        flash("Studentnummer bestaat al.", "danger")

    return redirect(url_for("web.students_page"))

@web.post("/students/<id>/delete")
def students_delete(id):
    current_app.db.students.delete_one({"_id": ObjectId(id)})
    flash("Student verwijderd.", "info")
    return redirect(url_for("web.students_page"))

# ----- Student detail: profile + resultaten + logs -----
@web.get("/students/<id>")
def student_detail(id):
    db = current_app.db
    s = db.students.find_one({"_id": ObjectId(id)})
    if not s:
        abort(404)
    s["_id"] = str(s["_id"])
    if s.get("opleiding_id") and isinstance(s["opleiding_id"], ObjectId):
        s["opleiding_id"] = str(s["opleiding_id"])

    # dropdown data
    opleidingen = list(db.opleidingen.find().sort("naam", 1))
    opos = list(db.opos.find().sort("afkorting", 1))
    jaren = list(db.academiejaren.find().sort("academiejaar", 1))
    categories = list(db.categorien.find().sort("afkorting", 1))

    # results for this student
    results = list(
        db.resultaten.find({"student_id": ObjectId(id)}).sort(
            [("academiejaar", 1), ("opo_id", 1), ("kans", 1)]
        )
    )
    for r in results:
        r["_id"] = str(r["_id"])
        r["student_id"] = str(r["student_id"])
        r["opo_id"] = str(r["opo_id"])

    # pretty map for OPO display
    opo_map = {
        str(o["_id"]): (o.get("afkorting") or "") + (" " + o.get("naam") if o.get("naam") else "")
        for o in opos
    }

    # logs for this student
    logs = list(
        db.student_logs.find({"student_id": ObjectId(id)}).sort("registratiedatum", -1)
    )
    for l in logs:
        l["_id"] = str(l["_id"])
        if l.get("categorie_id") and isinstance(l["categorie_id"], ObjectId):
            l["categorie_id"] = str(l["categorie_id"])

    return render_template(
        "student_detail.html",
        student=s,
        opleidingen=opleidingen,
        opos=opos,
        jaren=jaren,
        categories=categories,
        results=results,
        opo_map=opo_map,
        logs=logs,
    )

@web.post("/students/<id>/results")
def add_result(id):
    data = {
        "student_id": ObjectId(id),
        "academiejaar": (request.form.get("academiejaar") or "").strip(),
        "kans": int(request.form.get("kans") or 1),
        "cijfer": None
            if (request.form.get("cijfer") or "").strip() == ""
            else float(request.form.get("cijfer")),
    }
    # foreign keys
    try:
        data["opo_id"] = ObjectId(request.form.get("opo_id"))
    except Exception:
        flash("OPO is verplicht.", "danger")
        return redirect(url_for("web.student_detail", id=id))

    try:
        current_app.db.resultaten.insert_one(data)
        flash("Resultaat toegevoegd.", "success")
    except DuplicateKeyError:
        flash("Dit resultaat bestaat al voor deze kans.", "warning")

    return redirect(url_for("web.student_detail", id=id))

@web.post("/results/<rid>/delete")
def delete_result(rid):
    db = current_app.db
    res = db.resultaten.find_one({"_id": ObjectId(rid)})
    db.resultaten.delete_one({"_id": ObjectId(rid)})
    flash("Resultaat verwijderd.", "info")
    if res and res.get("student_id"):
        return redirect(url_for("web.student_detail", id=str(res["student_id"])))
    return redirect(url_for("web.students_page"))

@web.post("/students/<id>/logs")
def add_log(id):
    payload = {
        "student_id": ObjectId(id),
        "beschrijving": (request.form.get("beschrijving") or "").strip(),
        "registratiedatum": datetime.utcnow(),
    }
    if cid := (request.form.get("categorie_id") or "").strip():
        try:
            payload["categorie_id"] = ObjectId(cid)
        except Exception:
            pass
    current_app.db.student_logs.insert_one(payload)
    flash("Log toegevoegd.", "success")
    return redirect(url_for("web.student_detail", id=id))

@web.post("/student-logs/<lid>/delete")
def delete_log(lid):
    db = current_app.db
    log = db.student_logs.find_one({"_id": ObjectId(lid)})
    db.student_logs.delete_one({"_id": ObjectId(lid)})
    flash("Log verwijderd.", "info")
    if log and log.get("student_id"):
        return redirect(url_for("web.student_detail", id=str(log["student_id"])))
    return redirect(url_for("web.students_page"))

# ---------- OPO's (vakken) ----------
@web.get("/opos")
def opos_page():
    db = current_app.db
    opos = list(db.opos.find().sort("afkorting", 1))
    for o in opos:
        o["_id"] = str(o["_id"])
    return render_template("opos.html", opos=opos)

@web.post("/opos")
def opos_create():
    db = current_app.db
    doc = {
        "afkorting": (request.form.get("afkorting") or "").strip().upper(),
        "naam": (request.form.get("naam") or "").strip(),
        "code": (request.form.get("code") or "").strip().upper(),
    }
    try:
        db.opos.insert_one(doc)
        flash("OPO toegevoegd.", "success")
    except DuplicateKeyError:
        flash("Afkorting of code bestaat al.", "danger")
    return redirect(url_for("web.opos_page"))

@web.post("/opos/<id>/delete")
def opos_delete(id):
    current_app.db.opos.delete_one({"_id": ObjectId(id)})
    flash("OPO verwijderd.", "info")
    return redirect(url_for("web.opos_page"))

# ---------- Opleidingen ----------
@web.get("/opleidingen")
def opleidingen_page():
    db = current_app.db
    opleidingen = list(db.opleidingen.find().sort("naam", 1))
    for o in opleidingen:
        o["_id"] = str(o["_id"])
    return render_template("opleidingen.html", opleidingen=opleidingen)

@web.post("/opleidingen")
def opleidingen_create():
    db = current_app.db
    doc = {
        "naam": (request.form.get("naam") or "").strip(),
        "dag_avond": (request.form.get("dag_avond") or "").strip().lower(),
    }
    try:
        db.opleidingen.insert_one(doc)
        flash("Opleiding toegevoegd.", "success")
    except DuplicateKeyError:
        flash("Opleiding bestaat al.", "danger")
    return redirect(url_for("web.opleidingen_page"))

@web.post("/opleidingen/<id>/delete")
def opleidingen_delete(id):
    current_app.db.opleidingen.delete_one({"_id": ObjectId(id)})
    flash("Opleiding verwijderd.", "info")
    return redirect(url_for("web.opleidingen_page"))

# ---------- Academiejaren ----------
@web.get("/academiejaren")
def academiejaren_page():
    db = current_app.db
    jaren = list(db.academiejaren.find().sort("academiejaar", 1))
    for aj in jaren:
        aj["_id"] = str(aj["_id"])
    return render_template("academiejaren.html", academiejaren=jaren)

@web.post("/academiejaren")
def academiejaren_create():
    db = current_app.db
    doc = {"academiejaar": (request.form.get("academiejaar") or "").strip()}
    try:
        db.academiejaren.insert_one(doc)
        flash("Academiejaar toegevoegd.", "success")
    except DuplicateKeyError:
        flash("Academiejaar bestaat al.", "danger")
    return redirect(url_for("web.academiejaren_page"))

@web.post("/academiejaren/<id>/delete")
def academiejaren_delete(id):
    current_app.db.academiejaren.delete_one({"_id": ObjectId(id)})
    flash("Academiejaar verwijderd.", "info")
    return redirect(url_for("web.academiejaren_page"))
