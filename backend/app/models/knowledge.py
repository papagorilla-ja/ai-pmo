import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Knowledge(Base):
    __tablename__ = "knowledges"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    qdrant_id: Mapped[str] = mapped_column(String(100), nullable=True) # ID mapping to Qdrant vector
    content: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String(255), default="unknown")
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0)
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE") # ACTIVE, FLAGGED, ARCHIVED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
