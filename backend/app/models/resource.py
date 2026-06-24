import uuid
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, Integer, Float, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Resource(Base):
    __tablename__ = "resources"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    role: Mapped[str] = mapped_column(String(255), default="")  # PG, SE, PM, SV, etc.
    
    # Working hours settings
    start_time: Mapped[str] = mapped_column(String(5), default="09:00")  # "HH:MM"
    end_time: Mapped[str] = mapped_column(String(5), default="18:00")    # "HH:MM"
    break_hours: Mapped[float] = mapped_column(Float, default=1.0)
    daily_working_hours: Mapped[float] = mapped_column(Float, default=8.0)
    
    # Financials (Manager / Admin restricted)
    hourly_cost_jpy: Mapped[int] = mapped_column(Integer, default=0)
    
    # Permissions and status
    system_role: Mapped[str] = mapped_column(String(50), default="メンバー")  # 管理者, マネージャ, メンバー
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # Toggle user account
    
    # Skills Checkboxes + tags
    skills_phase: Mapped[list] = mapped_column(JSON, default=list)  # ["企画", "実装"]
    skills_domain: Mapped[list] = mapped_column(JSON, default=list)  # ["アプリ領域"]
    skills_free: Mapped[str] = mapped_column(String, default="")  # Free text skills/tags
    
    # Proposed extra fields
    allocation_limit: Mapped[int] = mapped_column(Integer, default=100)  # standard maxアサイン
    department: Mapped[str] = mapped_column(String(255), default="")
    available_from: Mapped[str] = mapped_column(String(10), default="")  # "YYYY-MM-DD"
    available_to: Mapped[str] = mapped_column(String(10), default="")    # "YYYY-MM-DD"
    working_days: Mapped[list] = mapped_column(JSON, default=lambda: ["Mon", "Tue", "Wed", "Thu", "Fri"])
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
