from sqlalchemy import select

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models import User


def seed_user():
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == 'researcher@example.com'))
        if existing:
            return
        user = User(email='researcher@example.com', password_hash=get_password_hash('researcher123'))
        db.add(user)
        db.commit()


if __name__ == '__main__':
    seed_user()
