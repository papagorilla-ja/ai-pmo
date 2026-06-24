from pydantic import BaseModel, ConfigDict
from uuid import UUID
from typing import List, Optional

class ResourceAllocationBase(BaseModel):
    resource_name: str
    skill_tags: List[str] = []
    allocation_percent: int = 100
    is_ai: bool = False

class ResourceAllocationCreate(ResourceAllocationBase):
    project_id: UUID

class ResourceAllocationResponse(ResourceAllocationBase):
    id: UUID
    project_id: UUID

    model_config = ConfigDict(from_attributes=True)
