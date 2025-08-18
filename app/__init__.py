# app/__init__.py
import os
from flask import Flask
from pymongo import MongoClient
from bson import ObjectId
from flask_login import LoginManager
from .db import ensure_indexes
from .models import User

def create_app():
    app = Flask(__name__)

    # --- Config ---
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    mongo_db = os.getenv("MONGO_DB", "studentopvolging")

    # --- DB ---
    client = MongoClient(mongo_uri)
    app.db = client[mongo_db]
    ensure_indexes(app.db)

    # --- Login ---
    login_manager = LoginManager()
    login_manager.login_view = "auth.login"   # where to redirect if not logged in
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        doc = app.db.users.find_one({"_id": ObjectId(user_id)})
        return User.from_doc(doc)

    # --- Blueprints ---
    from .web import web
    from .auth import auth
    app.register_blueprint(web)
    app.register_blueprint(auth)

    return app
