"""
Pytest fixtures shared across the test suite.
Uses an in-memory SQLite database per test function for isolation.
"""
import uuid
import pytest
from app import create_app
from app.config import TestingConfig
from app.extensions import db as _db
from app.models.user import User, Role
from app.models.election import Election, ElectionStatus
from app.models.position import Position
from app.models.candidate import Candidate
from app.models.eligible_voter import EligibleVoter
from app.extensions import bcrypt
from datetime import datetime, timezone, timedelta


@pytest.fixture()
def app():
    """Fresh application + in-memory DB per test function."""
    application = create_app(TestingConfig)
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture()
def db(app):
    """Yield the db extension; the app fixture handles setup/teardown."""
    with app.app_context():
        yield _db


def _uid():
    """Short unique suffix so matric numbers never collide across tests."""
    return uuid.uuid4().hex[:6].upper()


@pytest.fixture()
def admin_user(db):
    user = User(
        matric_number=f"ADMIN-{_uid()}",
        password_hash=bcrypt.generate_password_hash("Admin@1234", rounds=4).decode(),
        full_name="Test Admin",
        role=Role.ADMIN,
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def voter_user(db):
    user = User(
        matric_number=f"VOTER-{_uid()}",
        password_hash=bcrypt.generate_password_hash("Voter@1234", rounds=4).decode(),
        full_name="Test Voter",
        role=Role.VOTER,
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def sample_election(db, admin_user):
    from app.services.crypto_service import CryptoService
    public_pem, _ = CryptoService.generate_rsa_keypair()
    now = datetime.now(timezone.utc)

    election = Election(
        title="Test Election",
        status=ElectionStatus.OPEN,
        start_at=now - timedelta(hours=1),
        end_at=now + timedelta(hours=5),
        public_key_pem=public_pem,
        created_by=admin_user.user_id,
    )
    db.session.add(election)
    db.session.flush()

    position = Position(
        election_id=election.election_id,
        title="President",
        display_order=0,
    )
    db.session.add(position)
    db.session.flush()

    for name in ["Alice Okafor", "Bob Adewale"]:
        db.session.add(Candidate(
            position_id=position.position_id,
            full_name=name,
        ))

    db.session.commit()

    # Reload so relationships are accessible
    db.session.refresh(election)
    return election


@pytest.fixture()
def eligible_voter_entry(db, voter_user, sample_election):
    entry = EligibleVoter(
        election_id=sample_election.election_id,
        matric_number=voter_user.matric_number,
    )
    db.session.add(entry)
    db.session.commit()
    return entry
