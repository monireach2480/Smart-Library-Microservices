from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CopyStatus = Literal["AVAILABLE", "BORROWED", "LOST", "MAINTENANCE"]


class CopyCreate(BaseModel):
    book_id: int = Field(gt=0)
    barcode: str = Field(min_length=3, max_length=64)
    shelf_location: str | None = Field(default=None, max_length=64)


class CopyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    book_id: int
    barcode: str
    shelf_location: str | None
    status: str
    created_at: datetime


class StatusUpdate(BaseModel):
    status: CopyStatus


class AvailabilityOut(BaseModel):
    book_id: int
    total_copies: int
    available_copies: int


class CheckoutRequest(BaseModel):
    book_id: int


class ReturnRequest(BaseModel):
    copy_id: int
