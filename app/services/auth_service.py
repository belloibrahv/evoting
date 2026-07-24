"""
AuthService — registration, login, password management, RBAC guards.
"""
import hashlib
from typing import Optional, Tuple
from flask import current_app
from flask_login import login_user, logout_user
from app.extensions import db, bcrypt
from app.models.user import User, Role
from app.models.eligible_voter import EligibleVoter
from app.models.password_reset import PasswordResetToken
from app.services.audit_service import AuditService
from app.models.audit_log import AuditAction


class AuthError(Exception):
    """Raised for handled auth failures (safe to surface to the user)."""
    pass


class AuthService:
    # ── Registration ──────────────────────────────────────────────────────

    @staticmethod
    def register_voter(
        matric_number: str,
        password: str,
        full_name: str,
        email: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> User:
        """
        Register a new voter.
        Requires the matric number to exist in at least one election's
        eligible_voters roster (pre-loaded by the EC Admin).
        Raises AuthError on any validation failure.
        """
        matric_number = matric_number.strip().upper()

        # 1. Check roster — voter must be pre-registered by admin
        roster_entry = EligibleVoter.query.filter_by(
            matric_number=matric_number
        ).first()
        if not roster_entry:
            raise AuthError(
                "Your matriculation number is not on the eligible voter roster. "
                "Please contact the Electoral Commission."
            )

        # 2. Check for duplicate account
        if User.query.filter_by(matric_number=matric_number).first():
            raise AuthError(
                "An account with this matriculation number already exists. "
                "Please log in instead."
            )

        # 3. Password policy (min 8 chars, ≥1 letter, ≥1 digit)
        AuthService._validate_password(password)

        # 4. Create user
        password_hash = bcrypt.generate_password_hash(
            password, rounds=current_app.config.get("BCRYPT_LOG_ROUNDS", 12)
        ).decode("utf-8")

        user = User(
            matric_number=matric_number,
            password_hash=password_hash,
            full_name=full_name.strip(),
            email=email.strip().lower() if email else None,
            role=Role.VOTER,
        )
        db.session.add(user)

        AuditService.log(
            action=AuditAction.REGISTER,
            metadata={"matric": matric_number},
            ip_address=ip_address,
        )
        db.session.commit()
        return user

    # ── Login ─────────────────────────────────────────────────────────────

    @staticmethod
    def authenticate(
        matric_number: str,
        password: str,
        remember: bool = False,
        ip_address: Optional[str] = None,
    ) -> User:
        """
        Authenticate and start a session via Flask-Login.
        Raises AuthError on failure (always generic to avoid enumeration).
        """
        matric_number = matric_number.strip().upper()
        user = User.query.filter_by(
            matric_number=matric_number, is_active=True
        ).first()

        if user is None or not bcrypt.check_password_hash(
            user.password_hash, password
        ):
            AuditService.log(
                action=AuditAction.LOGIN_FAILURE,
                metadata={"matric": matric_number},
                ip_address=ip_address,
            )
            db.session.commit()
            raise AuthError("Invalid matriculation number or password.")

        login_user(user, remember=remember)
        AuditService.log(
            action=AuditAction.LOGIN_SUCCESS,
            user_id=user.user_id,
            ip_address=ip_address,
        )
        db.session.commit()
        return user

    # ── Logout ────────────────────────────────────────────────────────────

    @staticmethod
    def logout(user_id: int, ip_address: Optional[str] = None) -> None:
        logout_user()
        AuditService.log(
            action=AuditAction.LOGOUT,
            user_id=user_id,
            ip_address=ip_address,
        )
        db.session.commit()

    # ── Password Reset ────────────────────────────────────────────────────

    @staticmethod
    def request_password_reset(
        matric_number: str, ip_address: Optional[str] = None
    ) -> Optional[str]:
        """
        Issue a reset token if the matric number has an account.
        Returns the raw token string (to be emailed/displayed).
        Returns None silently if no account found (prevents enumeration).
        """
        matric_number = matric_number.strip().upper()
        user = User.query.filter_by(matric_number=matric_number).first()
        if not user:
            return None

        token_obj, raw_token = PasswordResetToken.generate(user.user_id)
        db.session.add(token_obj)
        AuditService.log(
            action=AuditAction.PASSWORD_RESET_REQUEST,
            user_id=user.user_id,
            ip_address=ip_address,
        )
        db.session.commit()
        return raw_token

    @staticmethod
    def complete_password_reset(
        raw_token: str,
        new_password: str,
        ip_address: Optional[str] = None,
    ) -> bool:
        """
        Validate the token and update the password.
        Returns True on success, False if the token is invalid/expired/used.
        """
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        token_obj = PasswordResetToken.query.filter_by(
            token_hash=token_hash
        ).first()

        if not token_obj or not token_obj.is_valid:
            return False

        AuthService._validate_password(new_password)

        user = token_obj.user
        user.password_hash = bcrypt.generate_password_hash(
            new_password,
            rounds=current_app.config.get("BCRYPT_LOG_ROUNDS", 12),
        ).decode("utf-8")

        token_obj.used = True

        AuditService.log(
            action=AuditAction.PASSWORD_RESET_COMPLETE,
            user_id=user.user_id,
            ip_address=ip_address,
        )
        db.session.commit()
        return True

    # ── RBAC Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def require_role(user: User, *roles: str) -> None:
        """Raise PermissionError if user doesn't hold one of the required roles."""
        if user.role not in roles:
            raise PermissionError(
                f"Access denied. Required role(s): {', '.join(roles)}."
            )

    # ── Private ───────────────────────────────────────────────────────────

    @staticmethod
    def _validate_password(password: str) -> None:
        """Enforce minimum password complexity."""
        if len(password) < 8:
            raise AuthError("Password must be at least 8 characters long.")
        if not any(c.isdigit() for c in password):
            raise AuthError("Password must contain at least one digit.")
        if not any(c.isalpha() for c in password):
            raise AuthError("Password must contain at least one letter.")
