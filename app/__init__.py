"""
Application factory for TASFUED EVS.
"""
import os
import logging

from flask import Flask, render_template
from pythonjsonlogger import jsonlogger

from app.config import get_config
from app.extensions import db, login_manager, csrf, bcrypt, limiter, migrate


def create_app(config_class=None) -> Flask:
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    # ── Config ────────────────────────────────────────────────────────────
    if config_class is None:
        config_class = get_config()
    app.config.from_object(config_class)

    # ── Extensions ────────────────────────────────────────────────────────
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    bcrypt.init_app(app)
    limiter.init_app(app)
    migrate.init_app(app, db)

    # ── Login manager user loader ─────────────────────────────────────────
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    # ── Blueprints ────────────────────────────────────────────────────────
    _register_blueprints(app)

    # ── Error handlers ────────────────────────────────────────────────────
    _register_error_handlers(app)

    # ── Jinja globals ─────────────────────────────────────────────────────
    _register_jinja_globals(app)

    # ── Logging ───────────────────────────────────────────────────────────
    _configure_logging(app)

    # ── DB setup: tests only (production uses scripts/init_db.py) ─────────
    # In production/staging Gunicorn forks multiple workers — running
    # create_all() or bootstrap inside the factory causes N concurrent
    # workers to race on the same DB. The pre-start script handles this once.
    if app.config.get("TESTING"):
        with app.app_context():
            db.create_all()
            _bootstrap_admin(app)

    # ── Background scheduler (skip during testing) ────────────────────────
    if not app.config.get("TESTING"):
        from app.scheduler import init_scheduler
        init_scheduler(app)

    return app


def _register_blueprints(app: Flask) -> None:
    from app.routes.public import public_bp
    from app.routes.auth import auth_bp
    from app.routes.voter import voter_bp
    from app.routes.admin import admin_bp
    from app.routes.results import results_bp
    from app.routes.api import api_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(voter_bp, url_prefix="/voter")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(results_bp, url_prefix="/results")
    app.register_blueprint(api_bp, url_prefix="/api")


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(429)
    def too_many_requests(e):
        return render_template("errors/429.html"), 429

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return render_template("errors/500.html"), 500


def _register_jinja_globals(app: Flask) -> None:
    from app.utils.helpers import format_datetime
    from datetime import datetime, timezone

    app.jinja_env.globals["app_name"] = app.config.get("APP_NAME", "TASFUED EVS")
    app.jinja_env.globals["institution_name"] = app.config.get(
        "INSTITUTION_NAME", "Tai Solarin Federal University of Education"
    )
    app.jinja_env.filters["format_datetime"] = format_datetime
    app.jinja_env.globals["now"] = lambda: datetime.now(timezone.utc)


def _configure_logging(app: Flask) -> None:
    log_level = getattr(logging, app.config.get("LOG_LEVEL", "INFO").upper(), logging.INFO)

    if app.config.get("JSON_LOGGING"):
        handler = logging.StreamHandler()
        formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(name)s %(levelname)s %(message)s"
        )
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)
    else:
        logging.basicConfig(level=log_level)

    app.logger.setLevel(log_level)


def _bootstrap_admin(app: Flask) -> None:
    """Create the default admin account if it doesn't exist yet."""
    from app.models.user import User, Role

    admin_matric = app.config.get("ADMIN_MATRIC", "ADMIN001")
    if User.query.filter_by(matric_number=admin_matric).first():
        return

    default_password = os.environ.get("ADMIN_DEFAULT_PASSWORD", "Admin@1234")
    hashed = bcrypt.generate_password_hash(
        default_password,
        rounds=app.config.get("BCRYPT_LOG_ROUNDS", 12),
    ).decode("utf-8")

    admin = User(
        matric_number=admin_matric,
        password_hash=hashed,
        full_name="EC Administrator",
        role=Role.ADMIN,
    )
    db.session.add(admin)
    db.session.commit()
    app.logger.info(
        "Default admin created — matric: %s. Change the password immediately.",
        admin_matric,
    )
