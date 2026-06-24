from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, List
from app.schemas.resource_allocation import ResourceAllocationResponse
from app.schemas.task import TaskResponse

class ProjectBase(BaseModel):
    name: str
    status: str = "ACTIVE"
    template_type: str = "FLAT"

class ProjectCreate(ProjectBase):
    organization_id: Optional[UUID] = None

class ProjectResponse(ProjectBase):
    id: UUID
    organization_id: UUID
    created_at: datetime
    allocations: List[ResourceAllocationResponse] = []
    tasks: List[TaskResponse] = []

    model_config = ConfigDict(from_attributes=True)

