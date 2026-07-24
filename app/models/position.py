"""Position model — a contested office within an election."""
from app.extensions import db


class Position(db.Model):
    __tablename__ = "positions"

    position_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    election_id = db.Column(
        db.Integer, db.ForeignKey("elections.election_id"), nullable=False
    )
    title = db.Column(db.String(100), nullable=False)
    display_order = db.Column(db.Integer, default=0)

    # ── Relationships ─────────────────────────────────────────────────────
    election = db.relationship("Election", back_populates="positions")
    candidates = db.relationship(
        "Candidate",
        back_populates="position",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Position '{self.title}' (election #{self.election_id})>"
