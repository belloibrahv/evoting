"""BallotRepository — queries for Ballot."""
from typing import Optional
from app.models.ballot import Ballot
from app.extensions import db


class BallotRepository:
    @staticmethod
    def get_by_receipt(receipt_id: str) -> Optional[Ballot]:
        return Ballot.query.filter_by(receipt_id=receipt_id).first()

    @staticmethod
    def get_by_anon_ref(anonymised_voter_ref: str, election_id: int) -> Optional[Ballot]:
        return Ballot.query.filter_by(
            anonymised_voter_ref=anonymised_voter_ref,
            election_id=election_id,
        ).first()

    @staticmethod
    def count_for_election(election_id: int) -> int:
        return Ballot.query.filter_by(election_id=election_id).count()
