"""
Unit tests for AuthService.
Covers: registration gating, password policy, bcrypt, login, RBAC guards.
"""
import pytest
from app.services.auth_service import AuthService, AuthError
from app.models.user import User, Role


class TestPasswordValidation:
    def test_too_short_raises(self, app):
        with app.app_context():
            with pytest.raises(AuthError, match="8 characters"):
                AuthService._validate_password("Ab1")

    def test_no_digit_raises(self, app):
        with app.app_context():
            with pytest.raises(AuthError, match="digit"):
                AuthService._validate_password("Abcdefgh")

    def test_no_letter_raises(self, app):
        with app.app_context():
            with pytest.raises(AuthError, match="letter"):
                AuthService._validate_password("12345678")

    def test_valid_password_passes(self, app):
        with app.app_context():
            AuthService._validate_password("Valid@123")  # Must not raise

    def test_exactly_8_chars_passes(self, app):
        with app.app_context():
            AuthService._validate_password("Valid123")  # Exactly 8

    def test_7_chars_raises(self, app):
        with app.app_context():
            with pytest.raises(AuthError, match="8 characters"):
                AuthService._validate_password("Val123x")


class TestAuthentication:
    def test_login_with_correct_credentials(self, client, voter_user):
        resp = client.post("/auth/login", data={
            "matric_number": voter_user.matric_number,
            "password": "Voter@1234",
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_login_with_wrong_password_shows_error(self, client, voter_user):
        resp = client.post("/auth/login", data={
            "matric_number": voter_user.matric_number,
            "password": "WrongPass99",
        }, follow_redirects=True)
        assert b"Invalid" in resp.data

    def test_login_nonexistent_user_shows_error(self, client):
        resp = client.post("/auth/login", data={
            "matric_number": "NOBODY999",
            "password": "SomePass1",
        }, follow_redirects=True)
        assert b"Invalid" in resp.data


class TestRBACGuard:
    def test_require_role_passes_for_correct_role(self, app, admin_user):
        with app.app_context():
            AuthService.require_role(admin_user, Role.ADMIN)  # No exception

    def test_require_role_raises_for_wrong_role(self, app, voter_user):
        with app.app_context():
            with pytest.raises(PermissionError):
                AuthService.require_role(voter_user, Role.ADMIN)

    def test_require_role_accepts_multiple_roles(self, app, voter_user):
        with app.app_context():
            # voter matches 'voter', so this should pass
            AuthService.require_role(voter_user, Role.ADMIN, Role.VOTER)

    def test_admin_route_blocked_for_voter(self, client, voter_user):
        client.post("/auth/login", data={
            "matric_number": voter_user.matric_number,
            "password": "Voter@1234",
        })
        resp = client.get("/admin/", follow_redirects=False)
        assert resp.status_code in (302, 403)
