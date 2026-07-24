"""
Development entry point.
Run with: python run.py
Production: use Gunicorn — gunicorn "app:create_app()" -w 4
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5001,
        debug=True,
        use_reloader=True,
    )
