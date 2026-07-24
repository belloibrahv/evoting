"""
BallotService — encrypt, persist, and idempotency-guard ballot submissions.
The ONLY place in the codebase that creates Ballot rows.
"""
from datetime import datetime, timezone
from typing import Optional
from flask import current_app
from app.extensions import db
from app.models.ballot import Ballot
from app.models.eligible_voter import EligibleVoter
from app.models.election import Election, ElectionStatus
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService
from app.services.crypto_service import CryptoService


class BallotError(Exception):
    pass


class BallotService:
    @staticmethod
    def cast_vote(
        user_id: int,
        election: Election,
        selections: dict,          # {str(position_id): candidate_id, ...}
        ip_address: Optional[str] = None,
    ) -> Ballot:
        """
        Encrypt and persist a ballot.

        Steps (all inside a single DB transaction):
          1. Validate election is OPEN.
          2. Check voter is on the eligible roster.
          3. Check has_voted == False (duplicate guard).
          4. Encrypt selections with the election's RSA public key.
          5. Compute SHA-256 integrity hash.
          6. Persist Ballot row.
          7. Set eligible_voters.has_voted = True.
          8. Write audit log entry.
          9. Commit — all or nothing.
        """
        # 1. Election must be open
        if election.status != ElectionStatus.OPEN:
            raise BallotError("This election is not currently accepting votes.")

        matric_number = BallotService._get_matric(user_id)

        # 2. Voter must be on roster
        roster_entry: Optional[EligibleVoter] = EligibleVoter.query.filter_by(
            election_id=election.election_id,
            matric_number=matric_number,
        ).with_for_update().first()  # Lock row for this transaction

        if roster_entry is None:
            raise BallotError(
                "You are not on the eligible voter list for this election."
            )

        # 3. Duplicate vote check
        if roster_entry.has_voted:
            AuditService.log(
                action=AuditAction.VOTE_ATTEMPT_DUPLICATE,
                user_id=user_id,
                metadata={"election_id": election.election_id},
                ip_address=ip_address,
            )
            db.session.commit()
            raise BallotError("You have already voted in this election.")

        # 4. Encrypt ballot
        encrypted_data = CryptoService.encrypt_ballot(
            selections, election.public_key_pem
        )

        # 5. Integrity hash
        salt = current_app.config.get("SECRET_KEY", "")
        anon_ref = CryptoService.anonymise_voter(user_id, election.election_id, salt)
        now = datetime.now(timezone.utc)
        # Strip microseconds for a stable, reproducible timestamp string
        timestamp_iso = now.replace(microsecond=0).isoformat()

        ballot_hash = CryptoService.compute_ballot_hash(
            anon_ref, election.election_id, timestamp_iso, encrypted_data
        )
        receipt_id = CryptoService.generate_receipt_id()

        # 6. Persist ballot
        ballot = Ballot(
            election_id=election.election_id,
            anonymised_voter_ref=anon_ref,
            encrypted_vote_data=encrypted_data,
            ballot_hash_sha256=ballot_hash,
            receipt_id=receipt_id,
            submitted_at=now,
        )
        db.session.add(ballot)

        # 7. Mark as voted (atomic with ballot insert)
        roster_entry.has_voted = True

        # 8. Audit log
        AuditService.log(
            action=AuditAction.VOTE_CAST,
            user_id=user_id,
            metadata={
                "election_id": election.election_id,
                "receipt_id": receipt_id,
            },
            ip_address=ip_address,
        )

        # 9. Commit — atomically writes ballot + has_voted + audit entry
        db.session.commit()
        return ballot

    @staticmethod
    def _get_matric(user_id: int) -> str:
        from app.models.user import User
        user = db.session.get(User, user_id)
        if not user:
            raise BallotError("User not found.")
        return user.matric_number
