from pydantic import EmailStr, Field

from app.schemas.common import ORMModel, Timestamped


class UserBase(ORMModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=64)
    full_name: str | None = Field(default=None, max_length=255)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRead(UserBase, Timestamped):
    id: int
    is_active: bool