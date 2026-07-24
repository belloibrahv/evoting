"""
AuditLog — append-only event record.
No UPDATE or DELETE routes exist for this table at the application layer.
"""
from datetime import datetime, timezone
from app.extensions import db


class AuditAction:
    """Canonical action-type constants (add more as needed)."""
    # Auth
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILURE = "LOGIN_FAILURE"
    LOGOUT = "LOGOUT"
    REGISTER = "REGISTER"
    PASSWORD_RESET_REQUEST = "PASSWORD_RESET_REQUEST"
    PASSWORD_RESET_COMPLETE = "PASSWORD_RESET_COMPLETE"
    # Voting
    VOTE_CAST = "VOTE_CAST"
    VOTE_ATTEMPT_DUPLICATE = "VOTE_ATTEMPT_DUPLICATE"
    # Election lifecycle
    ELECTION_CREATED = "ELECTION_CREATED"
    ELECTION_UPDATED = "ELECTION_UPDATED"
    ELECTION_TRANSITIONED = "ELECTION_TRANSITIONED"
    ELECTION_VOTERS_IMPORTED = "ELECTION_VOTERS_IMPORTED"
    # Tally & results
    TALLY_STARTED = "TALLY_STARTED"
    TALLY_COMPLETED = "TALLY_COMPLETED"
    HASH_MISMATCH = "HASH_MISMATCH"
    RESULTS_PUBLISHED = "RESULTS_PUBLISHED"
    # Key management
    KEY_GENERATED = "KEY_GENERATED"


class AuditLog(db.Model):
    __tablename__ = "audit_log"

    log_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id"), nullable=True
    )
    action_performed = db.Column(db.String(255), nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=False)
    metadata_json = db.Column(db.Text, nullable=True)  # JSON string, no PII
    timestamp = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )

    # ── Relationships ─────────────────────────────────────────────────────
    user = db.relationship("User", back_populates="audit_entries")

    def __repr__(self) -> str:
        return f"<AuditLog #{self.log_id} {self.action_performed} user={self.user_id}>"
