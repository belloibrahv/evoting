"""
Ballot model — stores ONLY the RSA-OAEP ciphertext + SHA-256 hash.
Plaintext votes are NEVER persisted.
"""
from datetime import datetime, timezone
from app.extensions import db


class Ballot(db.Model):
    __tablename__ = "ballots"

    ballot_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    election_id = db.Column(
        db.Integer, db.ForeignKey("elections.election_id"), nullable=False
    )
    # One-way salted hash of (user_id || election_id) — not a direct FK to users
    anonymised_voter_ref = db.Column(db.String(64), nullable=False, index=True)
    # RSA-OAEP-2048 ciphertext, base64-encoded
    encrypted_vote_data = db.Column(db.Text, nullable=False)
    # SHA-256 over anonymised_voter_ref || election_id || timestamp || ciphertext
    ballot_hash_sha256 = db.Column(db.String(64), nullable=False, unique=True)
    # User-facing receipt identifier (40-char hex / UUID-based)
    receipt_id = db.Column(db.String(40), nullable=False, unique=True)
    submitted_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    # Integrity check result set during tally
    integrity_verified = db.Column(db.Boolean, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────
    election = db.relationship("Election", back_populates="ballots")

    def __repr__(self) -> str:
        return f"<Ballot #{self.ballot_id} receipt={self.receipt_id}>"
