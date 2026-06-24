from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, List

class ResourceBase(BaseModel):
    name: str
    email: str
    role: str = ""
    start_time: str = "09:00"
    end_time: str = "18:00"
    break_hours: float = 1.0
    daily_working_hours: float = 8.0
    hourly_cost_jpy: int = 0
    system_role: str = "メンバー"
    is_active: bool = True
    skills_phase: List[str] = []
    skills_domain: List[str] = []
    skills_free: str = ""
    allocation_limit: int = 100
    department: str = ""
    available_from: str = ""
    available_to: str = ""
    working_days: List[str] = ["Mon", "Tue", "Wed", "Thu", "Fri"]

class ResourceCreate(ResourceBase):
    password: Optional[str] = None

class ResourceUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    break_hours: Optional[float] = None
    daily_working_hours: Optional[float] = None
    hourly_cost_jpy: Optional[int] = None
    system_role: Optional[str] = None
    is_active: Optional[bool] = None
    skills_phase: Optional[List[str]] = None
    skills_domain: Optional[List[str]] = None
    skills_free: Optional[str] = None
    allocation_limit: Optional[int] = None
    department: Optional[str] = None
    available_from: Optional[str] = None
    available_to: Optional[str] = None
    working_days: Optional[List[str]] = None
    password: Optional[str] = None

class ResourceResponse(ResourceBase):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
