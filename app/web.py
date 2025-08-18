# app/web.py
from flask import Blueprint, render_template, request, redirect, url_for, current_app, flash, abort, Response
import csv, io
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, current_app, flash, abort
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from flask_login import login_required, current_user  # <-- NEW

web = Blueprint("web", __name__)

# ---------- helpers ----------
def oid(x):
    return ObjectId(x) if isinstance(x, str) else x

def _str_id(doc):
    if not doc:
        return doc
    d = dict(doc)
    if isinstance(d.get("_id"), ObjectId):
        d["_id"] = str(d["_id"])
    return d

def _map_by_id(cursor, *fields):
    """
    Returns (list, map) where list has stringified _id docs and map maps string_id -> doc/label.
    If fields given (e.g. ("naam", "afkorting")), builds a 'label' field combining them.
    """
    docs = []
    mapping = {}
    for raw in cursor:
        d = _str_id(raw)
        if fields:
            parts = []
            for f in fields:
                val = d.get(f)
                if val:
                    parts.append(val)
            d["label"] = " — ".join(parts) if parts else d.get("naam") or d.get("afkorting") or ""
        mapping[d["_id"]] = d
        docs.append(d)
    return docs, mapping

# ---------- Home (Dashboard) ----------
@web.get("/")
def home():
    db = current_app.db
    counts = {
        "students": db.students.count_documents({}),
        "opos": db.opos.count_documents({}),
        "resultaten": db.resultaten.count_documents({}),
    }
    return render_template("home.html", counts=counts, can_edit=current_user.is_authenticated)

# ---------- Students list + create ----------
@web.get("/students")
def students_page():
    db = current_app.db

    # simple search on naam/studentnummer
    qtext = (request.args.get("q") or "").strip()
    q = {}
    if qtext:
        q = {
            "$or": [
                {"studentnummer": {"$regex": qtext, "$options": "i"}},
                {"voornaam": {"$regex": qtext, "$options": "i"}},
                {"achternaam": {"$regex": qtext, "$options": "i"}},
            ]
        }

    students = []
    for s in db.students.find(q).sort([("achternaam", 1), ("voornaam", 1)]):
        s = _str_id(s)
        if isinstance(s.get("opleiding_id"), ObjectId):
            s["opleiding_id"] = str(s["opleiding_id"])
        students.append(s)

    # opleidingen -> lijst + id->label map for table
    opleidingen_list, opleidingen_map_full = _map_by_id(
        db.opleidingen.find().sort("naam", 1), "naam", "dag_avond"
    )
    opleidings_map = {k: v.get("label", "") for k, v in opleidingen_map_full.items()}

    return render_template(
        "students.html",
        students=students,
        opleidingen=opleidingen_list,
        opleidings_map=opleidings_map,
        q=qtext,
        can_edit=current_user.is_authenticated,  # <-- use in template to hide create/delete if anon
    )

@web.post("/students")
@login_required
def students_create():
    db = current_app.db
    payload = {
        "studentnummer": (request.form.get("studentnummer") or "").strip(),
        "voornaam": (request.form.get("voornaam") or "").strip(),
        "achternaam": (request.form.get("achternaam") or "").strip(),
        "inschrijfdatum": (request.form.get("inschrijfdatum") or "").strip(),  # keep ISO string
    }
    if oid_str := request.form.get("opleiding_id"):
        try:
            payload["opleiding_id"] = oid(oid_str)
        except Exception:
            pass

    if not payload["studentnummer"] or not payload["voornaam"] or not payload["achternaam"]:
        flash("Vul studentnummer, voornaam en achternaam in.", "danger")
        return redirect(url_for("web.students_page"))

    try:
        db.students.insert_one(payload)
        flash("Student toegevoegd.", "success")
    except DuplicateKeyError:
        flash("Studentnummer bestaat al.", "danger")

    return redirect(url_for("web.students_page"))

@web.post("/students/<id>/delete")
@login_required
def students_delete(id):
    current_app.db.students.delete_one({"_id": oid(id)})
    flash("Student verwijderd.", "info")
    return redirect(url_for("web.students_page"))

# ---------- Student detail (edit + results + logs) ----------
@web.get("/students/<id>")
def student_detail(id):
    db = current_app.db
    stu = db.students.find_one({"_id": oid(id)})
    if not stu:
        abort(404)

    stu = _str_id(stu)
    if isinstance(stu.get("opleiding_id"), ObjectId):
        stu["opleiding_id"] = str(stu["opleiding_id"])

    # dropdown data
    opleidingen_list, opleidingen_map = _map_by_id(db.opleidingen.find().sort("naam", 1), "naam", "dag_avond")
    opos_list, opos_map = _map_by_id(db.opos.find().sort("afkorting", 1), "afkorting", "naam")
    cats_list, cats_map = _map_by_id(db.categorien.find().sort("afkorting", 1), "afkorting", "omschrijving")
    ajs = [d.get("academiejaar") for d in db.academiejaren.find().sort("academiejaar", 1)]

    # results for student
    results = []
    for r in db.resultaten.find({"student_id": oid(id)}).sort([("academiejaar", 1), ("opo_id", 1), ("kans", 1)]):
        r = _str_id(r)
        if isinstance(r.get("opo_id"), ObjectId):
            r["opo_id"] = str(r["opo_id"])
        r["opo_label"] = opos_map.get(r.get("opo_id"), {}).get("label", "—")
        r["cijfer_display"] = "NA" if r.get("cijfer") is None else r.get("cijfer")
        results.append(r)

    # log filters
    f_cat = (request.args.get("cat") or "").strip()
    f_opo = (request.args.get("opo") or "").strip()
    log_q = {"student_id": oid(id)}
    if f_cat:
        try:
            log_q["categorie_id"] = oid(f_cat)
        except Exception:
            pass
    if f_opo:
        try:
            log_q["opo_id"] = oid(f_opo)
        except Exception:
            pass

    logs = []
    for lg in db.student_logs.find(log_q).sort("registratiedatum", -1):
        lg = _str_id(lg)
        for k in ("categorie_id", "opo_id"):
            if isinstance(lg.get(k), ObjectId):
                lg[k] = str(lg[k])
        lg["cat_label"] = cats_map.get(lg.get("categorie_id"), {}).get("label", "")
        lg["opo_label"] = opos_map.get(lg.get("opo_id"), {}).get("label", "")
        dt = lg.get("registratiedatum")
        if isinstance(dt, datetime):
            lg["registratiedatum_str"] = dt.strftime("%Y-%m-%d %H:%M")
        else:
            lg["registratiedatum_str"] = str(dt or "")
        logs.append(lg)

    return render_template(
        "student_detail.html",
        s=stu,
        opleidingen=opleidingen_list,
        opos=opos_list,
        categories=cats_list,
        academiejaren=ajs,
        results=results,
        logs=logs,
        f_cat=f_cat,
        f_opo=f_opo,
        can_edit=current_user.is_authenticated,
    )

@web.post("/students/<id>/edit")
@login_required
def student_update(id):
    db = current_app.db
    doc = {
        "studentnummer": (request.form.get("studentnummer") or "").strip(),
        "voornaam": (request.form.get("voornaam") or "").strip(),
        "achternaam": (request.form.get("achternaam") or "").strip(),
        "inschrijfdatum": (request.form.get("inschrijfdatum") or "").strip(),
    }
    if opid := request.form.get("opleiding_id"):
        try:
            doc["opleiding_id"] = oid(opid)
        except Exception:
            doc["opleiding_id"] = None

    if not doc["studentnummer"] or not doc["voornaam"] or not doc["achternaam"]:
        flash("Vul studentnummer, voornaam en achternaam in.", "danger")
        return redirect(url_for("web.student_detail", id=id, tab="gegevens"))

    clash = current_app.db.students.find_one(
        {"studentnummer": doc["studentnummer"], "_id": {"$ne": oid(id)}}
    )
    if clash:
        flash("Studentnummer is al in gebruik.", "danger")
        return redirect(url_for("web.student_detail", id=id, tab="gegevens"))

    current_app.db.students.update_one({"_id": oid(id)}, {"$set": doc})
    flash("Student bijgewerkt.", "success")
    return redirect(url_for("web.student_detail", id=id, tab="gegevens"))

# ---------- results (per student) ----------
@web.post("/students/<id>/results")
@login_required
def student_add_result(id):
    db = current_app.db
    try:
        opo_id = oid(request.form.get("opo_id"))
    except Exception:
        flash("Kies een geldige OPO.", "danger")
        return redirect(url_for("web.student_detail", id=id, tab="resultaten"))

    aj = (request.form.get("academiejaar") or "").strip()
    kans = int(request.form.get("kans") or "1")
    is_na = request.form.get("is_na") == "on"
    cijfer_raw = (request.form.get("cijfer") or "").strip()
    cijfer = None if is_na or cijfer_raw == "" else float(cijfer_raw)

    filt = {"student_id": oid(id), "opo_id": opo_id, "academiejaar": aj, "kans": kans}
    db.resultaten.update_one(filt, {"$set": {"cijfer": cijfer}}, upsert=True)

    flash("Resultaat opgeslagen.", "success")
    return redirect(url_for("web.student_detail", id=id, tab="resultaten"))

@web.post("/results/<res_id>/delete")
@login_required
def result_delete(res_id):
    db = current_app.db
    res = db.resultaten.find_one({"_id": oid(res_id)})
    sid = str(res["student_id"]) if res else None

    db.resultaten.delete_one({"_id": oid(res_id)})
    flash("Resultaat verwijderd.", "info")

    if sid:
        return redirect(url_for("web.student_detail", id=sid, tab="resultaten"))
    return redirect(url_for("web.home"))


# ---------- logs (per student) ----------
@web.post("/students/<id>/logs")
@login_required
def student_add_log(id):
    db = current_app.db
    payload = {
        "student_id": oid(id),
        "beschrijving": (request.form.get("beschrijving") or "").strip(),
        "registratiedatum": datetime.utcnow(),
    }
    if cat := request.form.get("categorie_id"):
        try:
            payload["categorie_id"] = oid(cat)
        except Exception:
            pass
    if opo := request.form.get("opo_id"):
        try:
            payload["opo_id"] = oid(opo)
        except Exception:
            pass

    if not payload["beschrijving"]:
        flash("Beschrijf de logregel.", "danger")
        return redirect(url_for("web.student_detail", id=id, tab="logboek"))

    db.student_logs.insert_one(payload)
    flash("Logregel toegevoegd.", "success")
    return redirect(url_for("web.student_detail", id=id, tab="logboek"))

@web.post("/logs/<log_id>/delete")
@login_required
def log_delete(log_id):
    db = current_app.db
    lg = db.student_logs.find_one({"_id": oid(log_id)})
    sid = str(lg["student_id"]) if lg else None

    db.student_logs.delete_one({"_id": oid(log_id)})
    flash("Logregel verwijderd.", "info")

    if sid:
        return redirect(url_for("web.student_detail", id=sid, tab="logboek"))
    return redirect(url_for("web.home"))


# ---------- OPO's (vakken) ----------
@web.get("/opos")
def opos_page():
    db = current_app.db
    opos = [_str_id(o) for o in db.opos.find().sort("afkorting", 1)]
    return render_template("opos.html", opos=opos, can_edit=current_user.is_authenticated)

@web.post("/opos")
@login_required
def opos_create():
    db = current_app.db
    doc = {
        "afkorting": (request.form.get("afkorting") or "").strip().upper(),
        "naam": (request.form.get("naam") or "").strip(),
        "code": (request.form.get("code") or "").strip().upper(),
    }
    if not doc["afkorting"] or not doc["naam"] or not doc["code"]:
        flash("Vul afkorting, naam en code in.", "danger")
        return redirect(url_for("web.opos_page"))
    try:
        db.opos.insert_one(doc)
        flash("OPO toegevoegd.", "success")
    except DuplicateKeyError:
        flash("Afkorting of code bestaat al.", "danger")
    return redirect(url_for("web.opos_page"))

@web.post("/opos/<id>/delete")
@login_required
def opos_delete(id):
    current_app.db.opos.delete_one({"_id": oid(id)})
    flash("OPO verwijderd.", "info")
    return redirect(url_for("web.opos_page"))

# ---------- Opleidingen ----------
@web.get("/opleidingen")
def opleidingen_page():
    db = current_app.db
    opleidingen = [_str_id(o) for o in db.opleidingen.find().sort("naam", 1)]
    return render_template("opleidingen.html", opleidingen=opleidingen, can_edit=current_user.is_authenticated)

@web.post("/opleidingen")
@login_required
def opleidingen_create():
    db = current_app.db
    doc = {
        "naam": (request.form.get("naam") or "").strip(),
        "dag_avond": (request.form.get("dag_avond") or "").strip(),
    }
    if not doc["naam"] or not doc["dag_avond"]:
        flash("Vul naam en dag/avond in.", "danger")
        return redirect(url_for("web.opleidingen_page"))
    try:
        db.opleidingen.insert_one(doc)
        flash("Opleiding toegevoegd.", "success")
    except DuplicateKeyError:
        flash("Opleiding bestaat al.", "danger")
    return redirect(url_for("web.opleidingen_page"))

@web.post("/opleidingen/<id>/delete")
@login_required
def opleidingen_delete(id):
    current_app.db.opleidingen.delete_one({"_id": oid(id)})
    flash("Opleiding verwijderd.", "info")
    return redirect(url_for("web.opleidingen_page"))

# ---------- Academiejaren ----------
@web.get("/academiejaren")
def ajs_page():
    db = current_app.db
    ajs = [_str_id(d) for d in db.academiejaren.find().sort("academiejaar", 1)]
    return render_template("academiejaren.html", academiejaren=ajs, can_edit=current_user.is_authenticated)

@web.post("/academiejaren")
@login_required
def ajs_create():
    aj = (request.form.get("academiejaar") or "").strip()
    if not aj:
        flash("Vul academiejaar in.", "danger")
        return redirect(url_for("web.ajs_page"))
    try:
        current_app.db.academiejaren.insert_one({"academiejaar": aj})
        flash("Academiejaar toegevoegd.", "success")
    except DuplicateKeyError:
        flash("Academiejaar bestaat al.", "danger")
    return redirect(url_for("web.ajs_page"))

@web.post("/academiejaren/<id>/delete")
@login_required
def ajs_delete(id):
    current_app.db.academiejaren.delete_one({"_id": oid(id)})
    flash("Academiejaar verwijderd.", "info")
    return redirect(url_for("web.ajs_page"))

# ---------- Categorieën ----------
@web.get("/categorien")
def cats_page():
    db = current_app.db
    cats = [_str_id(c) for c in db.categorien.find().sort("afkorting", 1)]
    return render_template("categorien.html", categorien=cats, can_edit=current_user.is_authenticated)

@web.post("/categorien")
@login_required
def cats_create():
    db = current_app.db
    doc = {
        "afkorting": (request.form.get("afkorting") or "").strip().upper(),
        "omschrijving": (request.form.get("omschrijving") or "").strip(),
    }
    if not doc["afkorting"] or not doc["omschrijving"]:
        flash("Vul afkorting en omschrijving in.", "danger")
        return redirect(url_for("web.cats_page"))
    try:
        db.categorien.insert_one(doc)
        flash("Categorie toegevoegd.", "success")
    except DuplicateKeyError:
        flash("Categorie bestaat al.", "danger")
    return redirect(url_for("web.cats_page"))

@web.post("/categorien/<id>/delete")
@login_required
def cats_delete(id):
    current_app.db.categorien.delete_one({"_id": oid(id)})
    flash("Categorie verwijderd.", "info")
    return redirect(url_for("web.cats_page"))

# ---------- Collectief rapport ----------
@web.get("/rapport")
def rapport_page():
    db = current_app.db

    # filters
    academiejaren = [d.get("academiejaar") for d in db.academiejaren.find().sort("academiejaar", 1)]
    sel_aj = request.args.get("aj") or (academiejaren[-1] if academiejaren else "")

    opleidingen, _ = _map_by_id(db.opleidingen.find().sort("naam", 1), "naam", "dag_avond")
    sel_opl = request.args.get("opl") or ""

    all_opos, opos_map = _map_by_id(db.opos.find().sort("afkorting", 1), "afkorting", "naam")
    sel_opo_ids = request.args.getlist("opos")
    shown_opos = [opos_map[i] for i in sel_opo_ids if i in opos_map]

    # fetch students in opleiding (optional)
    stu_q = {}
    if sel_opl:
        try:
            stu_q["opleiding_id"] = oid(sel_opl)
        except Exception:
            pass
    students = list(db.students.find(stu_q))
    stu_map = {str(s["_id"]): _str_id(s) for s in students}

    # for each student, gather best (max) cijfer per selected OPO in selected AJ
    rows = []
    if students:
        res_q = {"academiejaar": sel_aj}
        if sel_opo_ids:
            res_q["opo_id"] = {"$in": [oid(x) for x in sel_opo_ids]}
        if sel_opl:
            res_q["student_id"] = {"$in": [s["_id"] for s in students]}
        else:
            res_q["student_id"] = {"$in": [s["_id"] for s in students]}

        cursor = db.resultaten.find(res_q)
        # build best per (student, opo)
        by_stu = {sid: {"student": _str_id(s), "cells": {}} for sid, s in stu_map.items()}
        for r in cursor:
            sid = str(r["student_id"])
            oid_str = str(r["opo_id"])
            best = by_stu.setdefault(sid, {"student": stu_map.get(sid, {}), "cells": {}})["cells"].get(oid_str)
            val = None if r.get("cijfer") is None else float(r["cijfer"])
            if best is None or (val is not None and (best["best"] is None or val > best["best"])):
                by_stu[sid]["cells"][oid_str] = {"best": val, "kans": r.get("kans")}
        rows = list(by_stu.values())
    
        # ---- Per-OPO samenvatting (tellen + %) ----
    opo_stats = []
    if sel_opo_ids and rows:
        # init counters in selection order
        stats = {oid: {"total": 0, "passed": 0, "failed": 0, "na": 0} for oid in sel_opo_ids}

        for r in rows:
            cells = r.get("cells", {})
            for oid_str in sel_opo_ids:
                c = cells.get(oid_str)
                if not c:
                    continue  # student deed dit OPO niet in dit AJ
                stats[oid_str]["total"] += 1
                val = c.get("best")
                if val is None:
                    stats[oid_str]["na"] += 1
                elif val >= 10:
                    stats[oid_str]["passed"] += 1
                else:
                    stats[oid_str]["failed"] += 1

        # build list (keep same order as selectie)
        for oid_str in sel_opo_ids:
            d = stats[oid_str]
            tot = d["total"] or 0

            def pct(n):  # None if no denominator
                return round((n * 100.0) / tot, 1) if tot else None

            opo_stats.append({
                "id": oid_str,
                "opo": opos_map.get(oid_str),   # {afkorting, naam, ...}
                "total": tot,
                "passed": d["passed"], "pct_passed": pct(d["passed"]),
                "failed": d["failed"], "pct_failed": pct(d["failed"]),
                "na": d["na"],         "pct_na":     pct(d["na"]),
            })

    return render_template(
        "rapport.html",
        academiejaren=academiejaren,
        sel_aj=sel_aj,
        opleidingen=opleidingen,
        sel_opl=sel_opl,
        all_opos=all_opos,
        sel_opo_ids=sel_opo_ids,
        shown_opos=shown_opos,
        rows=rows,
        opo_stats=opo_stats,
        can_edit=current_user.is_authenticated,
    )
@web.get("/rapport.csv")
@login_required
def rapport_csv():
    db = current_app.db

    # same filters as HTML view
    academiejaren = [d.get("academiejaar") for d in db.academiejaren.find().sort("academiejaar", 1)]
    sel_aj = request.args.get("aj") or (academiejaren[-1] if academiejaren else "")

    opleidingen, _ = _map_by_id(db.opleidingen.find().sort("naam", 1), "naam", "dag_avond")
    sel_opl = request.args.get("opl") or ""

    all_opos, opos_map = _map_by_id(db.opos.find().sort("afkorting", 1), "afkorting", "naam")
    sel_opo_ids = request.args.getlist("opos")
    shown_opos = [opos_map[i] for i in sel_opo_ids if i in opos_map]

    # students in (optional) opleiding
    stu_q = {}
    if sel_opl:
        try:
            stu_q["opleiding_id"] = oid(sel_opl)
        except Exception:
            pass
    students = list(db.students.find(stu_q))
    stu_map = {str(s["_id"]): _str_id(s) for s in students}

    # best grade per (student, opo) for selected AJ
    rows = []
    if students:
        res_q = {"academiejaar": sel_aj, "student_id": {"$in": [s["_id"] for s in students]}}
        if sel_opo_ids:
            res_q["opo_id"] = {"$in": [oid(x) for x in sel_opo_ids]}
        by_stu = {sid: {"student": _str_id(s), "cells": {}} for sid, s in stu_map.items()}
        for r in db.resultaten.find(res_q):
            sid = str(r["student_id"])
            oid_str = str(r["opo_id"])
            best = by_stu[sid]["cells"].get(oid_str)
            val = None if r.get("cijfer") is None else float(r["cijfer"])
            if best is None or (val is not None and (best["best"] is None or val > best["best"])):
                by_stu[sid]["cells"][oid_str] = {"best": val, "kans": r.get("kans")}
        rows = list(by_stu.values())

    # Build CSV
    sio = io.StringIO()
    w = csv.writer(sio)

    # Header
    header = ["studentnummer", "achternaam", "voornaam"]
    header += [f"{o['afkorting']} — {o['naam']}" for o in shown_opos] or ["— geen OPO’s gekozen —"]
    w.writerow(header)

    # Rows
    for r in rows:
        stu = r.get("student", {})
        line = [stu.get("studentnummer", ""), stu.get("achternaam", ""), stu.get("voornaam", "")]
        if shown_opos:
            for o in shown_opos:
                cell = r.get("cells", {}).get(o["_id"])
                if not cell:
                    line.append("")
                else:
                    line.append("NA" if cell["best"] is None else f"{cell['best']:.1f}")
        else:
            line.append("")
        w.writerow(line)

    out = sio.getvalue()
    fname = f"rapport_{sel_aj or 'onbekend'}.csv"
    return Response(out, mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={fname}"})

@web.post("/students/import")
@login_required
def students_import():
    db = current_app.db
    f = request.files.get("file")
    if not f or f.filename == "":
        flash("Kies een CSV-bestand.", "danger")
        return redirect(url_for("web.students_page"))

    # Lees het hele bestand als bytes en decodeer naar tekst (UTF-8 met BOM tolerant)
    try:
        raw = f.read()
        text = raw.decode("utf-8-sig") if isinstance(raw, (bytes, bytearray)) else str(raw)
    except Exception as e:
        flash(f"Kon CSV niet lezen: {e}", "danger")
        return redirect(url_for("web.students_page"))

    reader = csv.DictReader(io.StringIO(text))

    # Build label -> opleiding_id map: "Naam — dag_avond"
    opl_map = {}
    for o in db.opleidingen.find():
        label = f"{o.get('naam','').strip()} — {o.get('dag_avond','').strip()}".strip()
        opl_map[label] = o["_id"]

    created = 0
    updated = 0
    skipped = 0
    errors = []

    for i, row in enumerate(reader, start=2):  # header is regel 1
        try:
            snr = (row.get("studentnummer") or "").strip()
            vn  = (row.get("voornaam") or "").strip()
            an  = (row.get("achternaam") or "").strip()
            ins = (row.get("inschrijfdatum") or "").strip()
            opl_label = (row.get("opleiding_label") or "").strip()

            if not snr or not vn or not an:
                skipped += 1
                errors.append(f"Rij {i}: ontbrekende verplichte velden (studentnummer/voornaam/achternaam).")
                continue

            doc = {
                "studentnummer": snr,
                "voornaam": vn,
                "achternaam": an,
                "inschrijfdatum": ins,
            }

            if opl_label:
                opl_id = opl_map.get(opl_label)
                if opl_id:
                    doc["opleiding_id"] = opl_id
                else:
                    # onbekende opleiding is oké; laten we gewoon melden
                    errors.append(f"Rij {i}: opleiding niet gevonden: '{opl_label}'. Student aangemaakt zonder opleiding.")

            # upsert op studentnummer
            res = db.students.update_one(
                {"studentnummer": snr},
                {"$set": doc},
                upsert=True,
            )
            if res.upserted_id:
                created += 1
            elif res.modified_count:
                updated += 1
            else:
                # bestond al en geen wijzigingen
                skipped += 1

        except Exception as e:
            skipped += 1
            errors.append(f"Rij {i}: {e}")

    msg = f"Import klaar. Nieuw: {created}, Bijgewerkt: {updated}, Overgeslagen: {skipped}."
    if errors:
        # laat max ~5 fouten zien om flash kort te houden
        sample = " | ".join(errors[:5])
        extra = f" (+{len(errors)-5} meer)" if len(errors) > 5 else ""
        flash(msg + " Fouten: " + sample + extra, "warning")
    else:
        flash(msg, "success")

    return redirect(url_for("web.students_page"))

@web.get("/students/import/sample.csv")
@login_required
def students_import_sample():
    sio = io.StringIO()
    w = csv.writer(sio)
    w.writerow(["studentnummer", "voornaam", "achternaam", "inschrijfdatum", "opleiding_label"])
    w.writerow(["2025-0001", "Tom", "Janssens", "2025-07-01", "Graduaat Programmeren — dag"])
    w.writerow(["r0882849", "Felix", "Van Obbergen", "", "Graduaat Programmeren — dag"])
    return Response(sio.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=students_sample.csv"})

@web.get("/students.csv")
@login_required
def students_csv():
    db = current_app.db
    _, opl_map = _map_by_id(db.opleidingen.find().sort("naam", 1), "naam", "dag_avond")

    sio = io.StringIO()
    w = csv.writer(sio)
    w.writerow(["studentnummer", "voornaam", "achternaam", "inschrijfdatum", "opleiding_label", "opleiding_id"])

    for s in db.students.find().sort([("achternaam", 1), ("voornaam", 1)]):
        s = _str_id(s)
        opl_id = s.get("opleiding_id")
        label = opl_map.get(opl_id, {}).get("label", "") if opl_id else ""
        w.writerow([
            s.get("studentnummer",""),
            s.get("voornaam",""),
            s.get("achternaam",""),
            s.get("inschrijfdatum",""),
            label,
            opl_id or "",
        ])

    return Response(sio.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=students.csv"})
