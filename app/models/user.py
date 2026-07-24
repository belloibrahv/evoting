"""
User model — voters, admins, auditors.
Implements Flask-Login's UserMixin interface.
"""
from datetime import datetime, timezone
from flask_login import UserMixin
from app.extensions import db


class Role:
    VOTER = "voter"
    ADMIN = "admin"
    AUDITOR = "auditor"  # Results Viewer / read-only auditor

    ALL = {VOTER, ADMIN, AUDITOR}


class User(UserMixin, db.Model):
    __tablename__ = "users"

    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    matric_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=True, index=True)
    photo_url = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(20), nullable=False, default=Role.VOTER)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # ── Relationships ─────────────────────────────────────────────────────
    audit_entries = db.relationship(
        "AuditLog", back_populates="user", lazy="dynamic"
    )
    reset_tokens = db.relationship(
        "PasswordResetToken", back_populates="user", lazy="dynamic"
    )

    # ── Flask-Login interface ─────────────────────────────────────────────
    def get_id(self) -> str:
        """Flask-Login requires a string identifier."""
        return str(self.user_id)

    # ── Helper properties ─────────────────────────────────────────────────
    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN

    @property
    def is_voter(self) -> bool:
        return self.role == Role.VOTER

    @property
    def is_auditor(self) -> bool:
        return self.role == Role.AUDITOR

    def __repr__(self) -> str:
        return f"<User {self.matric_number} [{self.role}]>"
