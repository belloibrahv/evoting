"""
Development entry point — single process, safe to call create_all here.
Production: gunicorn is started via scripts/start.sh which calls init_db.py first.
"""
from app import create_app, _bootstrap_admin
from app.extensions import db

app = create_app()

# In dev (single process) we initialise the DB right here
with app.app_context():
    db.create_all()
    _bootstrap_admin(app)

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5001,
        debug=True,
        use_reloader=False,  # Reloader would double-init; disable for simplicity in dev
    )
