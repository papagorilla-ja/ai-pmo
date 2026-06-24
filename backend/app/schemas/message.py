from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional

class MessageBase(BaseModel):
    sender_type: str = "USER"  # USER, AI_PMO, AI_WORKER
    sender_name: str = "System"
    content: str
    task_id: Optional[UUID] = None

class MessageCreate(MessageBase):
    pass

class MessageResponse(MessageBase):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
