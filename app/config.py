"""
Application configuration.
Reads from environment variables (set via .env in development).
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class BaseConfig:
    # ── Core ──────────────────────────────────────────────────────────────
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-insecure-key-change-in-prod")
    APP_NAME: str = os.environ.get("APP_NAME", "TASFUED EVS")
    INSTITUTION_NAME: str = os.environ.get(
        "INSTITUTION_NAME", "Tai Solarin Federal University of Education"
    )

    # ── Database ──────────────────────────────────────────────────────────
    _db_url = os.environ.get("DATABASE_URL", "sqlite:///evoting.db")
    # Render (and Heroku) provide postgres:// URLs; SQLAlchemy 2.x needs postgresql+psycopg2://
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif _db_url.startswith("postgresql://"):
        _db_url = _db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    SQLALCHEMY_DATABASE_URI: str = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # ── Session / Cookies ─────────────────────────────────────────────────
    PERMANENT_SESSION_LIFETIME: timedelta = timedelta(
        seconds=int(os.environ.get("SESSION_IDLE_TIMEOUT", 1800))
    )
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"
    SESSION_COOKIE_SECURE: bool = False  # Overridden to True in ProductionConfig

    # ── CSRF ──────────────────────────────────────────────────────────────
    WTF_CSRF_ENABLED: bool = True
    WTF_CSRF_TIME_LIMIT: int = 3600  # 1 hour

    # ── Bcrypt ────────────────────────────────────────────────────────────
    BCRYPT_LOG_ROUNDS: int = int(os.environ.get("BCRYPT_LOG_ROUNDS", 12))

    # ── Rate limiting ─────────────────────────────────────────────────────
    RATELIMIT_STORAGE_URL: str = os.environ.get("RATELIMIT_STORAGE_URL", "memory://")
    RATELIMIT_DEFAULT: str = "200 per day;50 per hour"
    RATELIMIT_HEADERS_ENABLED: bool = True

    # ── Admin bootstrap ───────────────────────────────────────────────────
    ADMIN_MATRIC: str = os.environ.get("ADMIN_MATRIC", "ADMIN001")

    # ── Upload paths ──────────────────────────────────────────────────────
    UPLOAD_FOLDER: str = os.path.join(os.path.dirname(__file__), "static", "uploads")
    MAX_CONTENT_LENGTH: int = 5 * 1024 * 1024  # 5 MB

    # ── Keys storage (prototype: local PEM; prod: KMS) ────────────────────
    KEYS_FOLDER: str = os.path.join(os.path.dirname(__file__), "..", "keys")

    # ── Logging ───────────────────────────────────────────────────────────
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
    JSON_LOGGING: bool = False  # Overridden in ProductionConfig


class DevelopmentConfig(BaseConfig):
    DEBUG: bool = True
    TESTING: bool = False


class TestingConfig(BaseConfig):
    TESTING: bool = True
    DEBUG: bool = True
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///:memory:"
    WTF_CSRF_ENABLED: bool = False  # Disable CSRF for test client
    BCRYPT_LOG_ROUNDS: int = 4      # Faster hashing in tests
    RATELIMIT_ENABLED: bool = False


class ProductionConfig(BaseConfig):
    DEBUG: bool = False
    TESTING: bool = False
    SESSION_COOKIE_SECURE: bool = True
    JSON_LOGGING: bool = True
    WTF_CSRF_SSL_STRICT: bool = True


config_map: dict = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config():
    env = os.environ.get("FLASK_ENV", "development")
    return config_map.get(env, DevelopmentConfig)
