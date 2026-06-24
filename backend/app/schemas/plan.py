from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class PlanBase(BaseModel):
    approach_summary: str
    status: str = "DRAFT"

class PlanCreate(PlanBase):
    task_id: UUID

class PlanResponse(PlanBase):
    id: UUID
    task_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
