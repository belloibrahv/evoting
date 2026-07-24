"""
Database initialisation script — runs ONCE before Gunicorn starts.
Safe to run on every deploy: create_all() only creates missing tables,
and bootstrap_admin() is a no-op if the admin already exists.

Called by scripts/start.sh before gunicorn forks any workers.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, _bootstrap_admin
from app.extensions import db

app = create_app()

with app.app_context():
    # Create all tables that don't yet exist (idempotent)
    db.create_all()
    print("==> Database tables ready.")

    # Create default admin account if not present (idempotent)
    _bootstrap_admin(app)
    print("==> Admin bootstrap complete.")
