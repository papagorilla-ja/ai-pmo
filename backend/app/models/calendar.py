import uuid
from sqlalchemy import String, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class CalendarHoliday(Base):
    __tablename__ = "calendar_holidays"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    date: Mapped[str] = mapped_column(String(10), unique=True, index=True, nullable=False)  # "YYYY-MM-DD"
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_company_holiday: Mapped[bool] = mapped_column(Boolean, default=False)
    year: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
