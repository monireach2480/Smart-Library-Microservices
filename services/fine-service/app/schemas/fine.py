from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    loan_id: int | None
    amount: float
    reason: str
    status: str
    created_at: datetime
    paid_at: datetime | None


class ManualFine(BaseModel):
    user_id: int = Field(gt=0)
    amount: float = Field(gt=0, le=10000)
    reason: str = Field(min_length=3, max_length=255)
    loan_id: int | None = None


class AssessRequest(BaseModel):
    loan_id: int
    user_id: int
    days_overdue: int = Field(gt=0)


class FineSummary(BaseModel):
    unpaid_count: int
    unpaid_total: float
    paid_total: float


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    fine_id: int
    amount: float
    paid_by: int
    paid_at: datetime


class FineDetail(FineOut):
    payments: list[PaymentOut] = []
