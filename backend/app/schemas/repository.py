from pydantic import BaseModel, ConfigDict
from uuid import UUID
from typing import Optional, Dict, Any

class RepositoryBase(BaseModel):
    name: str
    type: str = "LOCAL"  # LOCAL, GITHUB
    path: str
    config: Dict[str, Any] = {}

class RepositoryCreate(RepositoryBase):
    pass

class RepositoryResponse(RepositoryBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)
