# app/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, current_app, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from bson import ObjectId
from .models import User

auth = Blueprint("auth", __name__)

@auth.get("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("web.home"))
    return render_template("login.html")

@auth.post("/login")
def login_post():
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    doc = current_app.db.users.find_one({"email": email})
    if not doc or not check_password_hash(doc.get("password_hash", ""), password):
        flash("Ongeldige inloggegevens.", "danger")
        return redirect(url_for("auth.login"))

    login_user(User.from_doc(doc), remember=False)
    flash("Ingelogd.", "success")
    next_url = request.args.get("next")
    return redirect(next_url or url_for("web.home"))

@auth.get("/register")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("web.home"))
    return render_template("register.html")

@auth.post("/register")
def register_post():
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    confirm  = request.form.get("confirm") or ""

    if not name or not email or not password:
        flash("Vul naam, e-mail en wachtwoord in.", "danger")
        return redirect(url_for("auth.register"))
    if password != confirm:
        flash("Wachtwoorden komen niet overeen.", "danger")
        return redirect(url_for("auth.register"))

    if current_app.db.users.find_one({"email": email}):
        flash("E-mail bestaat al.", "danger")
        return redirect(url_for("auth.register"))

    role = "admin" if current_app.db.users.count_documents({}) == 0 else "viewer"
    doc = {
        "name": name,
        "email": email,
        "password_hash": generate_password_hash(password),
        "role": role,
    }
    res = current_app.db.users.insert_one(doc)
    doc["_id"] = res.inserted_id

    login_user(User.from_doc(doc))
    flash("Account aangemaakt.", "success")
    return redirect(url_for("web.home"))

@auth.get("/logout")
@login_required
def logout():
    logout_user()
    flash("Uitgelogd.", "info")
    return redirect(url_for("web.home"))
