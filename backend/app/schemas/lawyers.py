from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, Timestamped


class LawyerProfileUpdate(ORMModel):
    full_name: str | None = Field(default=None, max_length=255)
    bar_registration_number: str | None = Field(default=None, max_length=128)
    jurisdiction: str | None = Field(default=None, max_length=128)
    years_experience: int | None = Field(default=None, ge=0, le=80)
    practice_areas: list[str] | None = None
    languages: list[str] | None = None
    location: str | None = Field(default=None, max_length=128)
    bio: str | None = Field(default=None, max_length=4000)
    consultation_modes: list[str] | None = None
    fee_structure: str | None = Field(default=None, max_length=255)
    photo_url: str | None = Field(default=None, max_length=512)
    availability: str | None = Field(default=None, max_length=255)


class LawyerProfileRead(ORMModel, Timestamped):
    id: int
    user_id: int
    full_name: str | None = None
    bar_registration_number: str | None = None
    jurisdiction: str | None = None
    years_experience: int | None = None
    practice_areas: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    location: str | None = None
    bio: str | None = None
    consultation_modes: list[str] = Field(default_factory=list)
    fee_structure: str | None = None
    photo_url: str | None = None
    availability: str | None = None
    verification_status: str
    verification_notes: str | None = None
    # Derived server-side from the fields above; not stored.
    profile_complete: bool = False


class LawyerDirectoryEntry(BaseModel):
    """Public-facing lawyer summary shown in the client-facing directory.

    Only fields a client needs to choose counsel are exposed; private profile
    internals and the user's own account data are not included.
    """

    user_id: int
    full_name: str | None = None
    jurisdiction: str | None = None
    years_experience: int | None = None
    practice_areas: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    location: str | None = None
    bio: str | None = None
    consultation_modes: list[str] = Field(default_factory=list)
    fee_structure: str | None = None
    availability: str | None = None
    photo_url: str | None = None
    verification_status: str
    profile_complete: bool = False


class LawyerDirectoryResponse(BaseModel):
    items: list[LawyerDirectoryEntry] = Field(default_factory=list)
    total: int = 0
