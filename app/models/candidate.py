"""Candidate model — a person standing for a position in an election."""
from app.extensions import db


class Candidate(db.Model):
    __tablename__ = "candidates"

    candidate_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    position_id = db.Column(
        db.Integer, db.ForeignKey("positions.position_id"), nullable=False
    )
    full_name = db.Column(db.String(100), nullable=False)
    matric_number = db.Column(db.String(20), nullable=True)
    photo_url = db.Column(db.String(255), nullable=True)
    manifesto = db.Column(db.Text, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────
    position = db.relationship("Position", back_populates="candidates")

    def __repr__(self) -> str:
        return f"<Candidate '{self.full_name}' (position #{self.position_id})>"
