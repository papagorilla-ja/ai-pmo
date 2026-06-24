from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional

class KnowledgeBase(BaseModel):
    content: str
    source: str = "unknown"
    confidence_score: float = 1.0
    status: str = "ACTIVE"

class KnowledgeCreate(KnowledgeBase):
    qdrant_id: Optional[str] = None

class KnowledgeUpdate(BaseModel):
    content: Optional[str] = None
    source: Optional[str] = None
    confidence_score: Optional[float] = None
    status: Optional[str] = None

class KnowledgeResponse(KnowledgeBase):
    id: UUID
    qdrant_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
