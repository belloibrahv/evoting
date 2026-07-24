"""
ElectionService — election CRUD, lifecycle transitions, CSV voter import,
candidate management, RSA key generation per election.
"""
import csv
import io
import os
from datetime import datetime, timezone
from typing import List, Optional

from flask import current_app
from app.extensions import db
from app.models.election import Election, ElectionStatus
from app.models.position import Position
from app.models.candidate import Candidate
from app.models.eligible_voter import EligibleVoter
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService
from app.services.crypto_service import CryptoService


class ElectionError(Exception):
    pass


class ElectionService:
    # ── Create ────────────────────────────────────────────────────────────

    @staticmethod
    def create_election(
        title: str,
        description: str,
        start_at: datetime,
        end_at: datetime,
        created_by: int,
        positions: List[str],          # ordered list of position titles
        ip_address: Optional[str] = None,
    ) -> tuple[Election, str]:
        """
        Create a new election in DRAFT status + generate its RSA-2048 key pair.

        Returns:
            (election, private_pem) — the private PEM is returned ONCE;
            it is NOT stored in the database.
        """
        if end_at <= start_at:
            raise ElectionError("End date must be after start date.")

        public_pem, private_pem = CryptoService.generate_rsa_keypair()

        election = Election(
            title=title.strip(),
            description=description.strip() if description else "",
            start_at=start_at,
            end_at=end_at,
            public_key_pem=public_pem,
            created_by=created_by,
            status=ElectionStatus.DRAFT,
        )
        db.session.add(election)
        db.session.flush()  # Get election_id before adding positions

        for idx, pos_title in enumerate(positions):
            pos = Position(
                election_id=election.election_id,
                title=pos_title.strip(),
                display_order=idx,
            )
            db.session.add(pos)

        AuditService.log(
            action=AuditAction.ELECTION_CREATED,
            user_id=created_by,
            metadata={"election_id": election.election_id, "title": title},
            ip_address=ip_address,
        )
        db.session.commit()

        # Optionally persist private key to keys/ folder (dev prototype only)
        ElectionService._save_private_key_file(election.election_id, private_pem)

        return election, private_pem

    # ── Update (DRAFT only) ───────────────────────────────────────────────

    @staticmethod
    def update_election(
        election: Election,
        title: Optional[str] = None,
        description: Optional[str] = None,
        start_at: Optional[datetime] = None,
        end_at: Optional[datetime] = None,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
    ) -> Election:
        if not election.is_editable:
            raise ElectionError(
                "Only elections in DRAFT status can be edited."
            )

        if title:
            election.title = title.strip()
        if description is not None:
            election.description = description.strip()
        if start_at:
            election.start_at = start_at
        if end_at:
            election.end_at = end_at
        if election.end_at <= election.start_at:
            raise ElectionError("End date must be after start date.")

        AuditService.log(
            action=AuditAction.ELECTION_UPDATED,
            user_id=user_id,
            metadata={"election_id": election.election_id},
            ip_address=ip_address,
        )
        db.session.commit()
        return election

    # ── Lifecycle Transition ──────────────────────────────────────────────

    @staticmethod
    def transition(
        election: Election,
        to_status: str,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
    ) -> Election:
        if not ElectionStatus.can_transition(election.status, to_status):
            raise ElectionError(
                f"Cannot transition from '{election.status}' to '{to_status}'."
            )

        from_status = election.status
        election.status = to_status

        AuditService.log(
            action=AuditAction.ELECTION_TRANSITIONED,
            user_id=user_id,
            metadata={
                "election_id": election.election_id,
                "from": from_status,
                "to": to_status,
            },
            ip_address=ip_address,
        )
        db.session.commit()
        return election

    # ── Candidate Management ──────────────────────────────────────────────

    @staticmethod
    def add_candidate(
        position: Position,
        full_name: str,
        matric_number: Optional[str] = None,
        photo_url: Optional[str] = None,
        manifesto: Optional[str] = None,
    ) -> Candidate:
        if not position.election.is_editable:
            raise ElectionError(
                "Candidates can only be added while the election is in DRAFT."
            )
        candidate = Candidate(
            position_id=position.position_id,
            full_name=full_name.strip(),
            matric_number=matric_number.strip().upper() if matric_number else None,
            photo_url=photo_url,
            manifesto=manifesto,
        )
        db.session.add(candidate)
        db.session.commit()
        return candidate

    @staticmethod
    def remove_candidate(candidate: Candidate) -> None:
        if not candidate.position.election.is_editable:
            raise ElectionError(
                "Candidates can only be removed while the election is in DRAFT."
            )
        db.session.delete(candidate)
        db.session.commit()

    # ── Voter Roster Import ───────────────────────────────────────────────

    @staticmethod
    def import_voters_csv(
        election: Election,
        csv_content: str,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
    ) -> dict:
        """
        Bulk-import eligible voter matric numbers from a CSV string.
        Expected format: one matric number per row (first column used).
        Existing entries are skipped (upsert-style: no duplicates).
        Returns {"added": N, "skipped": N, "errors": [...]}.
        """
        reader = csv.reader(io.StringIO(csv_content))
        added = 0
        skipped = 0
        errors = []

        for row_num, row in enumerate(reader, start=1):
            if not row:
                continue
            raw = row[0].strip()
            if not raw or raw.lower() in ("matric_number", "matric", "matriculation"):
                continue  # skip header or empty rows
            matric = raw.upper()
            if len(matric) > 20:
                errors.append(f"Row {row_num}: '{matric}' too long (max 20 chars)")
                continue

            exists = EligibleVoter.query.filter_by(
                election_id=election.election_id, matric_number=matric
            ).first()
            if exists:
                skipped += 1
                continue

            db.session.add(
                EligibleVoter(
                    election_id=election.election_id,
                    matric_number=matric,
                )
            )
            added += 1

        AuditService.log(
            action=AuditAction.ELECTION_VOTERS_IMPORTED,
            user_id=user_id,
            metadata={
                "election_id": election.election_id,
                "added": added,
                "skipped": skipped,
            },
            ip_address=ip_address,
        )
        db.session.commit()
        return {"added": added, "skipped": skipped, "errors": errors}

    # ── Private ───────────────────────────────────────────────────────────

    @staticmethod
    def _save_private_key_file(election_id: int, private_pem: str) -> None:
        """
        Persist the private key to the local keys/ directory.
        In production, this would go to KMS instead.
        """
        try:
            keys_dir = current_app.config.get("KEYS_FOLDER", "keys")
            os.makedirs(keys_dir, exist_ok=True)
            key_path = os.path.join(keys_dir, f"election_{election_id}_private.pem")
            with open(key_path, "w") as f:
                f.write(private_pem)
        except Exception:
            # Non-fatal in dev; in prod, failure to store the key IS fatal.
            pass
