import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class Message(Base):
    __tablename__ = "messages"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sender_type: Mapped[str] = mapped_column(String(50), default="USER")  # USER, AI_PMO, AI_WORKER
    sender_name: Mapped[str] = mapped_column(String(255), default="System")
    content: Mapped[str] = mapped_column(String, nullable=False)
    task_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    task: Mapped[Optional["Task"]] = relationship(back_populates="messages")
