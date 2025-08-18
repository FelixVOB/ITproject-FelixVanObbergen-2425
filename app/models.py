# app/models.py
from typing import Optional, Dict, Any
from flask_login import UserMixin

class User(UserMixin):
    """
    Tiny wrapper around a Mongo 'users' document so Flask-Login works.
    """
    def __init__(self, doc: Optional[Dict[str, Any]] = None):
        self.doc = doc or {}
        # Flask-Login expects an 'id' attribute that is a string
        self.id = str(self.doc.get("_id")) if self.doc.get("_id") else None

    @property
    def email(self) -> str:
        return self.doc.get("email", "")

    @property
    def name(self) -> str:
        return self.doc.get("name", "")

    @property
    def role(self) -> str:
        # viewer | admin | logger (future use)
        return self.doc.get("role", "viewer")

    @staticmethod
    def from_doc(doc: Optional[Dict[str, Any]]):
        return User(doc) if doc else None
