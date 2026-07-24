"""
Development entry point.
Production: gunicorn is started via scripts/start.sh which calls init_db.py first.
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    # In dev, initialise DB before running (single process, safe)
    from app.extensions import db
    from app import _bootstrap_admin
    
    with app.app_context():
        db.create_all()
        _bootstrap_admin(app)
    
    app.run(
        host="0.0.0.0",
        port=5001,
        debug=True,
        use_reloader=False,  # Reloader would double-init; disable for simplicity in dev
    )
