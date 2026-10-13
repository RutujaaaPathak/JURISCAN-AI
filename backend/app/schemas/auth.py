"""Authentication request/response schemas.

Only the three self-service roles can be registered through the public API.
``admin`` accounts are deliberately excluded here: administrator provisioning is
an operational concern, not a public sign-up path.
"""

from typing import Literal

from pydantic import EmailStr, Field, model_validator

from app.schemas.common import ORMModel, Timestamped

PUBLIC_ROLES = ("individual", "company", "lawyer")
PublicRole = Literal["individual", "company", "lawyer"]


class RegisterRequest(ORMModel):
    role: PublicRole
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)

    # Company accounts
    organization_name: str | None = Field(default=None, max_length=255)

    # Lawyer professional details (required for the lawyer role)
    bar_registration_number: str | None = Field(default=None, max_length=64)
    jurisdiction: str | None = Field(default=None, max_length=128)
    years_experience: int | None = Field(default=None, ge=0, le=80)
    practice_areas: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    location: str | None = Field(default=None, max_length=255)
    bio: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_role_fields(self) -> "RegisterRequest":
        if self.role == "company" and not (self.organization_name or "").strip():
            raise ValueError("Organization name is required for company accounts.")
        if self.role == "lawyer":
            missing = [
                field
                for field, present in (
                    ("bar_registration_number", bool((self.bar_registration_number or "").strip())),
                    ("jurisdiction", bool((self.jurisdiction or "").strip())),
                    ("years_experience", self.years_experience is not None),
                    ("practice_areas", bool([a for a in self.practice_areas if a.strip()])),
                    ("bio", bool((self.bio or "").strip())),
                )
                if not present
            ]
            if missing:
                raise ValueError("Missing required lawyer fields: " + ", ".join(missing))
        return self


class LoginRequest(ORMModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AuthUser(ORMModel, Timestamped):
    id: int
    email: EmailStr
    username: str
    full_name: str | None
    role: str
    organization_name: str | None
    is_active: bool


class TokenResponse(ORMModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AuthUser


__all__ = [
    "PUBLIC_ROLES",
    "AuthUser",
    "LoginRequest",
    "PublicRole",
    "RegisterRequest",
    "TokenResponse",
]
