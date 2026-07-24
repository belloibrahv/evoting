"""
EligibleVoter — the roster entry linking a matric number to an election.
`has_voted` is set atomically in the same transaction as the ballot insert.
"""
from app.extensions import db


class EligibleVoter(db.Model):
    __tablename__ = "eligible_voters"
    __table_args__ = (
        db.UniqueConstraint("election_id", "matric_number", name="uq_election_voter"),
    )

    eligibility_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    election_id = db.Column(
        db.Integer, db.ForeignKey("elections.election_id"), nullable=False
    )
    matric_number = db.Column(db.String(20), nullable=False, index=True)
    has_voted = db.Column(db.Boolean, nullable=False, default=False)

    # ── Relationships ─────────────────────────────────────────────────────
    election = db.relationship("Election", back_populates="eligible_voters")

    def __repr__(self) -> str:
        return (
            f"<EligibleVoter {self.matric_number} "
            f"election=#{self.election_id} voted={self.has_voted}>"
        )
