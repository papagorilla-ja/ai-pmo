from pydantic import BaseModel, ConfigDict
from uuid import UUID
from typing import Optional

class CalendarHolidayBase(BaseModel):
    date: str  # "YYYY-MM-DD"
    name: str
    is_company_holiday: bool = False
    year: int

class CalendarHolidayCreate(CalendarHolidayBase):
    pass

class CalendarHolidayUpdate(BaseModel):
    date: Optional[str] = None
    name: Optional[str] = None
    is_company_holiday: Optional[bool] = None
    year: Optional[int] = None

class CalendarHolidayResponse(CalendarHolidayBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)

class CalendarHolidaySyncRequest(BaseModel):
    year: int
