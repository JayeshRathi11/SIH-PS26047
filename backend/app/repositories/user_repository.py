"""
Step 17: UserRepository — minimal CRUD for AppUser.

Only retrieves users by email or ID. Does NOT expose password_hash in any return
type other than the ORM model itself (which the schema layer then strips).
"""
from typing import Optional
from sqlalchemy.orm import Session
from app.models.app_user import AppUser


class UserRepository:
    def get_by_email(self, db: Session, email: str) -> Optional[AppUser]:
        """Case-insensitive email lookup."""
        return db.query(AppUser).filter(AppUser.email == email.lower().strip()).first()

    def get_by_id(self, db: Session, user_id: int) -> Optional[AppUser]:
        return db.query(AppUser).filter(AppUser.id == user_id).first()

    def create(self, db: Session, user: AppUser) -> AppUser:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def list_users(self, db: Session) -> list[AppUser]:
        return db.query(AppUser).order_by(AppUser.id).all()


user_repository = UserRepository()
