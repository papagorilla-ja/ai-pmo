from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional

class SubTaskBase(BaseModel):
    title: str
    description: str = ""
    status: str = "PENDING"
    agent_id: str = "AI_WORKER"

class SubTaskCreate(SubTaskBase):
    task_id: UUID

class SubTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    output_mock_path: Optional[str] = None

class SubTaskResponse(SubTaskBase):
    id: UUID
    task_id: UUID
    output_mock_path: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
