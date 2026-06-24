from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, List

class NewProjectOption(BaseModel):
    name: str
    template_type: str

class AnalyzeRequest(BaseModel):
    source_text: str
    project_id: Optional[UUID] = None
    new_project: Optional[NewProjectOption] = None

class SuggestedAssignee(BaseModel):
    resource_id: Optional[str] = None
    name: str
    reason: str

class PlanNode(BaseModel):
    temp_id: str
    title: str
    description: str = ""
    node_type: str  # PHASE, FEATURE, SPRINT, STORY, TASK
    parent_temp_id: Optional[str] = None
    deliverable: str = ""
    estimated_hours: float = 0.0
    suggested_assignee: Optional[SuggestedAssignee] = None
    dependencies: List[str] = []
    confidence: float
    required_skill: Optional[str] = None

class StaffingRecommendation(BaseModel):
    skill: str
    type: str  # NO_HOLDER, CAPACITY_SHORTAGE
    detail: str

class PreventiveTask(BaseModel):
    title: str
    reason: str

class AnalyzeResponse(BaseModel):
    summary: str
    nodes: List[PlanNode]
    staffing_recommendations: List[StaffingRecommendation]
    clarifying_questions: List[str]
    preventive_tasks: List[PreventiveTask]

class ApplyNode(BaseModel):
    temp_id: str
    title: str
    description: str = ""
    node_type: str
    parent_temp_id: Optional[str] = None
    estimated_hours: float = 0.0
    assignee_name: Optional[str] = None
    assignee_type: Optional[str] = "HUMAN"
    dependencies: List[str] = []
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None

class ApplyRequest(BaseModel):
    project_id: Optional[UUID] = None
    new_project: Optional[NewProjectOption] = None
    nodes: List[ApplyNode]
