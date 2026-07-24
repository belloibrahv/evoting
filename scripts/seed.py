"""
Seed script — creates demo data for development/testing.
Run with: python scripts/seed.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime, timezone, timedelta
from app import create_app
from app.extensions import db, bcrypt
from app.models.user import User, Role
from app.models.election import Election, ElectionStatus
from app.models.position import Position
from app.models.candidate import Candidate
from app.models.eligible_voter import EligibleVoter
from app.services.crypto_service import CryptoService

app = create_app()

with app.app_context():
    db.drop_all()
    db.create_all()

    print("Seeding users...")
    admin = User(
        matric_number="ADMIN001",
        password_hash=bcrypt.generate_password_hash("Admin@1234", rounds=4).decode(),
        full_name="EC Administrator",
        role=Role.ADMIN,
    )
    voters = []
    for i in range(1, 11):
        v = User(
            matric_number=f"2022020422{i}",
            password_hash=bcrypt.generate_password_hash("Voter@1234", rounds=4).decode(),
            full_name=f"Test Voter {i}",
            email=f"voter{i}@tasfued.edu.ng",
            role=Role.VOTER,
        )
        voters.append(v)

    db.session.add(admin)
    db.session.add_all(voters)
    db.session.flush()

    print("Seeding election...")
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

    # Save private key
    os.makedirs("keys", exist_ok=True)
    with open(f"keys/election_{election.election_id}_private.pem", "w") as f:
        f.write(private_pem)

    print("Seeding positions and candidates...")
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

    print("Seeding eligible voters roster...")
    for voter in voters:
        db.session.add(EligibleVoter(
            election_id=election.election_id,
            matric_number=voter.matric_number,
        ))

    db.session.commit()
    print("Seed complete.")
    print("Admin login: ADMIN001 / Admin@1234")
    print("Voter login: 20220204221 / Voter@1234")
