"""
Database initialisation script — runs ONCE before Gunicorn starts.
Safe to run on every deploy: create_all() only creates missing tables,
and bootstrap_admin() is a no-op if the admin already exists.

Called by scripts/start.sh before gunicorn forks any workers.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, _bootstrap_admin
from app.extensions import db, bcrypt
from app.models.user import User, Role
from app.models.election import Election, ElectionStatus
from app.models.position import Position
from app.models.candidate import Candidate
from app.models.eligible_voter import EligibleVoter
from app.services.crypto_service import CryptoService


def _seed_demo_voters():
    """Idempotently seed demo voter accounts and eligible roster entries."""

    from datetime import datetime, timezone, timedelta

    admin = User.query.filter_by(role=Role.ADMIN).first()
    if not admin:
        print("  [SKIP] No admin found — skipping demo seed.")
        return

    demo_voters_data = [
        ("20220204221", "Test Voter 1", "voter1@tasfued.edu.ng"),
        ("20220204222", "Test Voter 2", "voter2@tasfued.edu.ng"),
        ("20220204223", "Test Voter 3", "voter3@tasfued.edu.ng"),
        ("20220204224", "Test Voter 4", "voter4@tasfued.edu.ng"),
        ("20220204225", "Test Voter 5", "voter5@tasfued.edu.ng"),
        ("20220204226", "Test Voter 6", "voter6@tasfued.edu.ng"),
        ("20220204227", "Test Voter 7", "voter7@tasfued.edu.ng"),
        ("20220204228", "Test Voter 8", "voter8@tasfued.edu.ng"),
        ("20220204229", "Test Voter 9", "voter9@tasfued.edu.ng"),
        ("202202042210", "Test Voter 10", "voter10@tasfued.edu.ng"),
    ]

    # Create or find an open election for roster linking
    election = Election.query.filter_by(status=ElectionStatus.OPEN).first()
    if not election:
        now = datetime.now(timezone.utc)
        public_pem, private_pem = CryptoService.generate_rsa_keypair()
        election = Election(
            title="2024/2025 TASFUED Student Union Election",
            description="Annual student union government elections for TASFUED.",
            status=ElectionStatus.OPEN,
            start_at=now - timedelta(hours=1),
            end_at=now + timedelta(hours=5),
            public_key_pem=public_pem,
            created_by=admin.user_id,
        )
        db.session.add(election)
        db.session.flush()

        os.makedirs("keys", exist_ok=True)
        with open(f"keys/election_{election.election_id}_private.pem", "w") as f:
            f.write(private_pem)

        positions_data = {
            "President": ["Adewale Biodun", "Chiamaka Okafor"],
            "Vice President": ["Musa Ibrahim", "Fatima Suleiman"],
            "Financial Secretary": ["Emeka Nwosu", "Blessing Adesanya"],
            "PRO": ["Tunde Adeola", "Grace Okwu"],
        }
        for order, (pos_title, cand_names) in enumerate(positions_data.items()):
            pos = Position(
                election_id=election.election_id,
                title=pos_title,
                display_order=order,
            )
            db.session.add(pos)
            db.session.flush()
            for name in cand_names:
                db.session.add(Candidate(
                    position_id=pos.position_id,
                    full_name=name,
                    manifesto=f"{name} stands for transparent and accountable leadership.",
                ))
        print("  Created demo election with positions and candidates.")

    password = os.environ.get("DEMO_VOTER_PASSWORD", "Voter@1234")
    created_count = 0
    for matric, full_name, email in demo_voters_data:
        if User.query.filter_by(matric_number=matric).first():
            continue
        password_hash = bcrypt.generate_password_hash(
            password, rounds=app.config.get("BCRYPT_LOG_ROUNDS", 12)
        ).decode("utf-8")
        user = User(
            matric_number=matric,
            password_hash=password_hash,
            full_name=full_name,
            email=email,
            role=Role.VOTER,
        )
        db.session.add(user)
        db.session.flush()
        created_count += 1

        if not EligibleVoter.query.filter_by(
            election_id=election.election_id, matric_number=matric
        ).first():
            db.session.add(EligibleVoter(
                election_id=election.election_id,
                matric_number=matric,
            ))

    db.session.commit()
    if created_count:
        print(f"  Created {created_count} demo voter account(s).")
    else:
        print("  All demo voters already exist — nothing to do.")


app = create_app()

with app.app_context():
    # Create all tables that don't yet exist (idempotent)
    db.create_all()
    print("==> Database tables ready.")

    # Create default admin account if not present (idempotent)
    _bootstrap_admin(app)
    print("==> Admin bootstrap complete.")

    # Seed demo voter accounts and eligible roster (idempotent — skips if already present)
    _seed_demo_voters()
    print("==> Demo voter seed complete.")
