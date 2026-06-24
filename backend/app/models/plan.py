import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class Plan(Base):
    __tablename__ = "plans"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), unique=True, nullable=False)
    approach_summary: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="DRAFT")  # DRAFT, APPROVED, REJECTED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    task: Mapped["Task"] = relationship(back_populates="plan")
