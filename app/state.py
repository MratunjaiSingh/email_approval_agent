from typing import Literal
from pydantic import BaseModel, Field


class MailState(BaseModel):
    # inputs
    query: str = ""
    sender_name: str = ""
    recipient_name: str = ""
    to_email: str = ""
    start_date: str = ""   # ISO "YYYY-MM-DD" (optional)
    end_date: str = ""     # ISO "YYYY-MM-DD" (optional)

    # working state
    draft: str = ""
    issues: list[str] = Field(default_factory=list)
    attempts: int = 0
    human_feedback: str = ""
    approved: bool = False

    # outputs
    status: Literal["drafting", "sent", "blocked", "failed"] = "drafting"
    final_response: str = ""
