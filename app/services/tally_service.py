"""
TallyService — decrypt ballots, verify integrity, count votes, publish results.
Only runs after the election reaches CLOSED status.
"""
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional
from flask import current_app
from app.extensions import db
from app.models.election import Election, ElectionStatus
from app.models.ballot import Ballot
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService
from app.services.crypto_service import CryptoService
from app.services.election_service import ElectionService, ElectionError


class TallyService:
    @staticmethod
    def run_tally(
        election: Election,
        private_pem: str,
        passphrase: str = "",
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
    ) -> dict:
        """
        Decrypt every ballot, re-verify its SHA-256 hash, and count votes.

        Returns a results dict:
        {
          position_id: {
            "title": str,
            "candidates": {candidate_id: {"name": str, "votes": int}},
            "total_votes": int,
          },
          ...
          "_summary": {
            "total_ballots": int,
            "valid_ballots": int,
            "invalid_ballots": int,
            "turnout_pct": float,
          }
        }
        Mismatched-hash ballots are excluded and flagged in the audit trail.
        """
        if election.status != ElectionStatus.CLOSED:
            raise ElectionError(
                "Tally can only be run on CLOSED elections."
            )

        AuditService.log(
            action=AuditAction.TALLY_STARTED,
            user_id=user_id,
            metadata={"election_id": election.election_id},
            ip_address=ip_address,
        )

        # Build candidate lookup: {position_id: {candidate_id: name}}
        candidate_map: dict = {}
        position_titles: dict = {}
        for position in election.positions:
            position_titles[position.position_id] = position.title
            candidate_map[position.position_id] = {
                c.candidate_id: c.full_name for c in position.candidates
            }

        # Initialise tally counters
        vote_counts: dict = defaultdict(lambda: defaultdict(int))
        total_ballots = 0
        valid_ballots = 0
        invalid_ballots = 0

        salt = current_app.config.get("SECRET_KEY", "")

        for ballot in election.ballots:
            total_ballots += 1

            # Re-verify integrity hash (use normalised timestamp, same as cast time)
            submitted_at = ballot.submitted_at.replace(microsecond=0)
            if submitted_at.tzinfo is None:
                submitted_at = submitted_at.replace(tzinfo=timezone.utc)
            timestamp_iso = submitted_at.isoformat()

            hash_ok = CryptoService.verify_ballot_hash(
                ballot.anonymised_voter_ref,
                election.election_id,
                timestamp_iso,
                ballot.encrypted_vote_data,
                ballot.ballot_hash_sha256,
            )

            if not hash_ok:
                ballot.integrity_verified = False
                invalid_ballots += 1
                AuditService.log(
                    action=AuditAction.HASH_MISMATCH,
                    user_id=user_id,
                    metadata={
                        "election_id": election.election_id,
                        "receipt_id": ballot.receipt_id,
                    },
                    ip_address=ip_address,
                )
                continue

            # Decrypt
            try:
                selections = CryptoService.decrypt_ballot(
                    ballot.encrypted_vote_data, private_pem, passphrase
                )
            except Exception:
                ballot.integrity_verified = False
                invalid_ballots += 1
                continue

            ballot.integrity_verified = True
            valid_ballots += 1

            # Count votes (selections keys are string position_ids from JSON)
            for pos_id_str, cand_id in selections.items():
                vote_counts[int(pos_id_str)][int(cand_id)] += 1

        # Build results structure
        results: dict = {}
        for pos_id, title in position_titles.items():
            pos_candidates = {}
            pos_total = 0
            for cand_id, cand_name in candidate_map.get(pos_id, {}).items():
                votes = vote_counts[pos_id].get(cand_id, 0)
                pos_candidates[cand_id] = {"name": cand_name, "votes": votes}
                pos_total += votes
            results[pos_id] = {
                "title": title,
                "candidates": pos_candidates,
                "total_votes": pos_total,
            }

        results["_summary"] = {
            "total_ballots": total_ballots,
            "valid_ballots": valid_ballots,
            "invalid_ballots": invalid_ballots,
            "turnout_pct": election.turnout_pct,
            "registered_voters": election.voter_count,
        }

        # Transition election → TALLIED
        ElectionService.transition(
            election,
            ElectionStatus.TALLIED,
            user_id=user_id,
            ip_address=ip_address,
        )

        AuditService.log(
            action=AuditAction.TALLY_COMPLETED,
            user_id=user_id,
            metadata={
                "election_id": election.election_id,
                "valid": valid_ballots,
                "invalid": invalid_ballots,
            },
            ip_address=ip_address,
        )
        db.session.commit()
        return results
