"""
Unit tests for BallotService.
Covers: vote casting, one-vote enforcement, closed-election rejection,
atomic has_voted flag, ballot hash verifiability.
"""
import pytest
from app.services.ballot_service import BallotService, BallotError
from app.models.election import ElectionStatus
from app.models.eligible_voter import EligibleVoter


class TestBallotCasting:
    def _selections(self, election):
        pos_id = str(election.positions[0].position_id)
        cand_id = election.positions[0].candidates[0].candidate_id
        return {pos_id: cand_id}

    def test_cast_vote_succeeds(self, voter_user, sample_election, eligible_voter_entry):
        ballot = BallotService.cast_vote(
            user_id=voter_user.user_id,
            election=sample_election,
            selections=self._selections(sample_election),
            ip_address="127.0.0.1",
        )
        assert ballot.receipt_id and len(ballot.receipt_id) == 40
        assert ballot.ballot_hash_sha256 and len(ballot.ballot_hash_sha256) == 64
        assert ballot.encrypted_vote_data

    def test_duplicate_vote_raises_ballot_error(
        self, voter_user, sample_election, eligible_voter_entry
    ):
        BallotService.cast_vote(
            user_id=voter_user.user_id,
            election=sample_election,
            selections=self._selections(sample_election),
            ip_address="127.0.0.1",
        )
        with pytest.raises(BallotError, match="already voted"):
            BallotService.cast_vote(
                user_id=voter_user.user_id,
                election=sample_election,
                selections=self._selections(sample_election),
                ip_address="127.0.0.1",
            )

    def test_has_voted_flag_set_atomically(
        self, db, voter_user, sample_election, eligible_voter_entry
    ):
        BallotService.cast_vote(
            user_id=voter_user.user_id,
            election=sample_election,
            selections=self._selections(sample_election),
            ip_address="127.0.0.1",
        )
        entry = EligibleVoter.query.filter_by(
            election_id=sample_election.election_id,
            matric_number=voter_user.matric_number,
        ).first()
        assert entry.has_voted is True

    def test_vote_on_closed_election_raises(
        self, db, voter_user, sample_election, eligible_voter_entry
    ):
        sample_election.status = ElectionStatus.CLOSED
        db.session.commit()
        with pytest.raises(BallotError, match="not currently accepting"):
            BallotService.cast_vote(
                user_id=voter_user.user_id,
                election=sample_election,
                selections=self._selections(sample_election),
                ip_address="127.0.0.1",
            )

    def test_vote_without_roster_entry_raises(self, voter_user, sample_election):
        # eligible_voter_entry fixture NOT used here — voter not on roster
        with pytest.raises(BallotError, match="not on the eligible voter"):
            BallotService.cast_vote(
                user_id=voter_user.user_id,
                election=sample_election,
                selections=self._selections(sample_election),
                ip_address="127.0.0.1",
            )

    def test_ballot_hash_verifiable(
        self, app, voter_user, sample_election, eligible_voter_entry
    ):
        from app.services.crypto_service import CryptoService
        ballot = BallotService.cast_vote(
            user_id=voter_user.user_id,
            election=sample_election,
            selections=self._selections(sample_election),
            ip_address="127.0.0.1",
        )
        salt = app.config["SECRET_KEY"]
        anon_ref = CryptoService.anonymise_voter(
            voter_user.user_id, sample_election.election_id, salt
        )
        # submitted_at is stored without microseconds; normalise the same way
        submitted = ballot.submitted_at.replace(microsecond=0)
        if submitted.tzinfo is None:
            from datetime import timezone as _tz
            submitted = submitted.replace(tzinfo=_tz.utc)
        assert CryptoService.verify_ballot_hash(
            anon_ref,
            sample_election.election_id,
            submitted.isoformat(),
            ballot.encrypted_vote_data,
            ballot.ballot_hash_sha256,
        )

    def test_different_voters_can_each_vote_once(
        self, db, voter_user, sample_election, eligible_voter_entry
    ):
        """Two distinct eligible voters can each cast one vote."""
        from app.models.user import User, Role
        from app.extensions import bcrypt
        import uuid

        # Create a second voter
        voter2 = User(
            matric_number=f"V2-{uuid.uuid4().hex[:6].upper()}",
            password_hash=bcrypt.generate_password_hash("Voter@1234", rounds=4).decode(),
            full_name="Second Voter",
            role=Role.VOTER,
        )
        db.session.add(voter2)
        db.session.flush()
        db.session.add(EligibleVoter(
            election_id=sample_election.election_id,
            matric_number=voter2.matric_number,
        ))
        db.session.commit()

        s = self._selections(sample_election)
        b1 = BallotService.cast_vote(voter_user.user_id, sample_election, s, "1.1.1.1")
        b2 = BallotService.cast_vote(voter2.user_id, sample_election, s, "2.2.2.2")

        assert b1.receipt_id != b2.receipt_id
        assert b1.ballot_hash_sha256 != b2.ballot_hash_sha256
