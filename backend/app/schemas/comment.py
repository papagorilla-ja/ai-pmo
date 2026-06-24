from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional

class CommentBase(BaseModel):
    content: str
    author: str = "AI_PMO"
    line_number: Optional[int] = None

class CommentCreate(CommentBase):
    task_id: UUID

class CommentResponse(CommentBase):
    id: UUID
    task_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
