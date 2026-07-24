"""UserRepository — all DB queries for the User model in one place."""
from typing import Optional
from app.models.user import User
from app.extensions import db


class UserRepository:
    @staticmethod
    def get_by_id(user_id: int) -> Optional[User]:
        return db.session.get(User, user_id)

    @staticmethod
    def get_by_matric(matric_number: str) -> Optional[User]:
        return User.query.filter_by(
            matric_number=matric_number.strip().upper()
        ).first()

    @staticmethod
    def get_by_email(email: str) -> Optional[User]:
        return User.query.filter_by(email=email.strip().lower()).first()

    @staticmethod
    def exists(matric_number: str) -> bool:
        return db.session.query(
            User.query.filter_by(
                matric_number=matric_number.strip().upper()
            ).exists()
        ).scalar()

    @staticmethod
    def create(user: User) -> User:
        db.session.add(user)
        return user

    @staticmethod
    def all_voters() -> list[User]:
        from app.models.user import Role
        return User.query.filter_by(role=Role.VOTER, is_active=True).all()
