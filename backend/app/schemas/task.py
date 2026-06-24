from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, List
from app.schemas.subtask import SubTaskResponse
from app.schemas.plan import PlanResponse

class TaskBase(BaseModel):
    title: str
    description: str = ""
    status: str = "TODO"  # TODO, IN_PROGRESS, REVIEW, DONE
    priority: str = "MEDIUM"  # HIGH, MEDIUM, LOW
    assignee_type: str = "HUMAN"  # HUMAN, AI
    assignee_name: str = ""
    planned_start: datetime
    planned_end: datetime
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    progress: int = 0
    delay_days: int = 0
    plan_b_start: Optional[datetime] = None
    plan_b_end: Optional[datetime] = None
    project_id: Optional[UUID] = None
    parent_id: Optional[UUID] = None
    node_type: str = "TASK"
    sort_order: int = 0
    estimated_hours: float = 0.0
    actual_hours: float = 0.0

class TaskCreate(TaskBase):
    dependency_ids: List[UUID] = []

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee_type: Optional[str] = None
    assignee_name: Optional[str] = None
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    progress: Optional[int] = None
    delay_days: Optional[int] = None
    plan_b_start: Optional[datetime] = None
    plan_b_end: Optional[datetime] = None
    dependency_ids: Optional[List[UUID]] = None
    project_id: Optional[UUID] = None
    parent_id: Optional[UUID] = None
    node_type: Optional[str] = None
    sort_order: Optional[int] = None
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None

# Simple task response to avoid recursion inside dependencies
class TaskSimpleResponse(TaskBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)

class TaskResponse(TaskBase):
    id: UUID
    is_summary: bool = False
    subtasks: List[SubTaskResponse] = []
    plan: Optional[PlanResponse] = None
    dependencies: List[TaskSimpleResponse] = []

    model_config = ConfigDict(from_attributes=True)

class TaskTreeNode(BaseModel):
    id: UUID
    title: str
    description: str
    status: str
    priority: str
    assignee_type: str
    assignee_name: str
    planned_start: datetime
    planned_end: datetime
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    progress: int
    delay_days: int
    project_id: Optional[UUID]
    parent_id: Optional[UUID]
    node_type: str
    sort_order: int
    estimated_hours: float
    actual_hours: float
    is_summary: bool
    children: List["TaskTreeNode"] = []

    model_config = ConfigDict(from_attributes=True)

# Rebuild model for self-referential list forward reference
TaskTreeNode.model_rebuild()
