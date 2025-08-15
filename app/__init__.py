# app/__init__.py
import os
from flask import Flask
from pymongo import MongoClient

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")

    mongo_url = os.getenv("MONGO_URL", "mongodb://127.0.0.1:27017/itproject")
    client = MongoClient(mongo_url)
    app.db = client.get_default_database()

    from .db import ensure_indexes
    ensure_indexes(app.db)

    # API
    from .routes import bp
    app.register_blueprint(bp, url_prefix="/api")

    # WEB
    from .web import web
    app.register_blueprint(web)

    return app
