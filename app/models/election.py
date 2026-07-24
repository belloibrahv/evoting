"""
Election model — core entity that drives the entire lifecycle.
"""
from datetime import datetime, timezone
from app.extensions import db


class ElectionStatus:
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    OPEN = "open"
    CLOSED = "closed"
    TALLIED = "tallied"
    PUBLISHED = "published"

    # Valid forward transitions only
    TRANSITIONS = {
        DRAFT: {SCHEDULED},
        SCHEDULED: {OPEN, DRAFT},
        OPEN: {CLOSED},
        CLOSED: {TALLIED},
        TALLIED: {PUBLISHED},
        PUBLISHED: set(),
    }

    @classmethod
    def can_transition(cls, from_status: str, to_status: str) -> bool:
        return to_status in cls.TRANSITIONS.get(from_status, set())


class Election(db.Model):
    __tablename__ = "elections"

    election_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(
        db.String(20), nullable=False, default=ElectionStatus.DRAFT, index=True
    )
    start_at = db.Column(db.DateTime, nullable=False)
    end_at = db.Column(db.DateTime, nullable=False)
    public_key_pem = db.Column(db.Text, nullable=False, default="")
    created_by = db.Column(
        db.Integer, db.ForeignKey("users.user_id"), nullable=True
    )
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # ── Relationships ─────────────────────────────────────────────────────
    positions = db.relationship(
        "Position",
        back_populates="election",
        cascade="all, delete-orphan",
        order_by="Position.display_order",
        lazy="select",
    )
    eligible_voters = db.relationship(
        "EligibleVoter",
        back_populates="election",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    ballots = db.relationship(
        "Ballot",
        back_populates="election",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    creator = db.relationship("User", foreign_keys=[created_by], lazy="select")

    # ── Helpers ───────────────────────────────────────────────────────────
    @property
    def is_open(self) -> bool:
        return self.status == ElectionStatus.OPEN

    @property
    def is_published(self) -> bool:
        return self.status == ElectionStatus.PUBLISHED

    @property
    def is_editable(self) -> bool:
        return self.status == ElectionStatus.DRAFT

    @property
    def voter_count(self) -> int:
        return self.eligible_voters.count()

    @property
    def voted_count(self) -> int:
        return self.eligible_voters.filter_by(has_voted=True).count()

    @property
    def turnout_pct(self) -> float:
        total = self.voter_count
        if total == 0:
            return 0.0
        return round(self.voted_count / total * 100, 1)

    def __repr__(self) -> str:
        return f"<Election #{self.election_id} '{self.title}' [{self.status}]>"
