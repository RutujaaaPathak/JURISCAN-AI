from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User

DbSession = Annotated[Session, Depends(get_db)]

# Authentication is not implemented yet, so uploads are attributed to a single
# default workspace user. This is created on demand.
DEFAULT_USER_EMAIL = "demo@juriscan.ai"
DEFAULT_USER_USERNAME = "demo-reviewer"
DEFAULT_USER_FULL_NAME = "Demo Reviewer"


def get_current_user(db: DbSession) -> User:
    user = db.scalar(select(User).where(User.email == DEFAULT_USER_EMAIL))
    if user is None:
        user = User(
            email=DEFAULT_USER_EMAIL,
            username=DEFAULT_USER_USERNAME,
            full_name=DEFAULT_USER_FULL_NAME,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]

__all__ = ["CurrentUser", "DbSession", "get_current_user"]
