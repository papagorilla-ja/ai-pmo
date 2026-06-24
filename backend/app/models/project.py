import uuid
from datetime import datetime, timezone
from typing import List
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class Project(Base):
    __tablename__ = "projects"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE") # ACTIVE, COMPLETED, SUSPENDED
    template_type: Mapped[str] = mapped_column(String(20), default="FLAT", server_default="FLAT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    tasks: Mapped[List["Task"]] = relationship(back_populates="project", cascade="all, delete-orphan", lazy="select")
    allocations: Mapped[List["ResourceAllocation"]] = relationship(back_populates="project", cascade="all, delete-orphan", lazy="select")
