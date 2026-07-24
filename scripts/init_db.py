"""
Database initialisation script — safe to run on every deploy.
Uses db.create_all() which is idempotent (only creates missing tables).
Bootstraps the default admin account if not present.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    db.create_all()
    print("Database tables ready.")
