import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class Comment(Base):
    __tablename__ = "comments"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=True)  # Null if not targeting a specific line
    content: Mapped[str] = mapped_column(String, nullable=False)
    author: Mapped[str] = mapped_column(String(100), default="AI_PMO")  # USER, AI_PMO
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    task: Mapped["Task"] = relationship(back_populates="comments")
