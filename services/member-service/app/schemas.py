from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    role: str
    status: str
    created_at: datetime


class MemberUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class StatusUpdate(BaseModel):
    status: Literal["ACTIVE", "SUSPENDED"]


class MemberStatusOut(BaseModel):
    id: int
    status: str
    role: str


class StatsOut(BaseModel):
    total: int
    by_role: dict[str, int]
    by_status: dict[str, int]
