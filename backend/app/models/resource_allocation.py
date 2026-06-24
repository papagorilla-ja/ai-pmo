import uuid
from sqlalchemy import String, Integer, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class ResourceAllocation(Base):
    __tablename__ = "resource_allocations"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("resources.id", ondelete="SET NULL"), nullable=True)
    resource_name: Mapped[str] = mapped_column(String(255), nullable=False)
    skill_tags: Mapped[list] = mapped_column(JSON, default=list) # e.g. ["Vue3", "FastAPI"]
    allocation_percent: Mapped[int] = mapped_column(Integer, default=100) # 0 to 100%
    is_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    project: Mapped["Project"] = relationship(back_populates="allocations")
    resource: Mapped["Resource"] = relationship(lazy="select")
