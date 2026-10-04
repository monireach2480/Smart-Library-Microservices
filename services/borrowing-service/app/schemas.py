from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BorrowRequest(BaseModel):
    book_id: int = Field(gt=0)


class LoanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    book_id: int
    copy_id: int
    status: str
    borrowed_at: datetime
    due_at: datetime
    returned_at: datetime | None
    fine_amount: float
