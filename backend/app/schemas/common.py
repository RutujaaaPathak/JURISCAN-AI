from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])
    app: str
    environment: str


class StatusResponse(BaseModel):
    status: str
    app: str
    environment: str
    database: str
    database_details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Any | None = None


class Timestamped(BaseModel):
    created_at: datetime
    updated_at: datetime