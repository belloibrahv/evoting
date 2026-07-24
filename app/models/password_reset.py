"""Password reset token — time-limited, single-use."""
from datetime import datetime, timezone, timedelta
import secrets
from app.extensions import db


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    token_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id"), nullable=False
    )
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # ── Relationships ─────────────────────────────────────────────────────
    user = db.relationship("User", back_populates="reset_tokens")

    # ── Helpers ───────────────────────────────────────────────────────────
    @property
    def is_valid(self) -> bool:
        return (
            not self.used
            and datetime.now(timezone.utc) < self.expires_at.replace(tzinfo=timezone.utc)
        )

    @staticmethod
    def generate(user_id: int, ttl_minutes: int = 30) -> tuple["PasswordResetToken", str]:
        """
        Create a new token. Returns (model_instance, raw_token).
        The raw_token is shown to the user once; only the hash is stored.
        """
        import hashlib

        raw = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
        instance = PasswordResetToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        return instance, raw

    def __repr__(self) -> str:
        return f"<PasswordResetToken user={self.user_id} used={self.used}>"
