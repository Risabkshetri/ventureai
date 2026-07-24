from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MeetingRequestCreate(BaseModel):
    startup_id: UUID
    scheduled_at: datetime
    agenda: str | None = None


class MeetingResponseUpdate(BaseModel):
    status: str
