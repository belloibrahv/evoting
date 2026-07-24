"""ElectionRepository — queries for Election, Position, Candidate, EligibleVoter."""
from typing import Optional, List
from app.models.election import Election, ElectionStatus
from app.models.position import Position
from app.models.candidate import Candidate
from app.models.eligible_voter import EligibleVoter
from app.extensions import db


class ElectionRepository:
    @staticmethod
    def get_by_id(election_id: int) -> Optional[Election]:
        return db.session.get(Election, election_id)

    @staticmethod
    def all_ordered() -> List[Election]:
        return Election.query.order_by(Election.created_at.desc()).all()

    @staticmethod
    def open_elections() -> List[Election]:
        return Election.query.filter_by(status=ElectionStatus.OPEN).all()

    @staticmethod
    def published_elections() -> List[Election]:
        return Election.query.filter_by(
            status=ElectionStatus.PUBLISHED
        ).order_by(Election.end_at.desc()).all()

    @staticmethod
    def get_eligible_voter(
        election_id: int, matric_number: str
    ) -> Optional[EligibleVoter]:
        return EligibleVoter.query.filter_by(
            election_id=election_id,
            matric_number=matric_number.strip().upper(),
        ).first()

    @staticmethod
    def get_candidate(candidate_id: int) -> Optional[Candidate]:
        return db.session.get(Candidate, candidate_id)

    @staticmethod
    def get_position(position_id: int) -> Optional[Position]:
        return db.session.get(Position, position_id)
