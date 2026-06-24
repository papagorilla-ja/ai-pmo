import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Integer, DateTime, ForeignKey, Table, Column, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

# Association table for task dependencies (many-to-many)
task_dependency = Table(
    "task_dependency",
    Base.metadata,
    Column("task_id", ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("depends_on_id", ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
)

class Task(Base):
    __tablename__ = "tasks"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String(50), default="TODO")  # TODO, IN_PROGRESS, REVIEW, DONE
    priority: Mapped[str] = mapped_column(String(50), default="MEDIUM")  # HIGH, MEDIUM, LOW
    assignee_type: Mapped[str] = mapped_column(String(50), default="HUMAN")  # HUMAN, AI
    assignee_name: Mapped[str] = mapped_column(String(255), default="")
    
    planned_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planned_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    progress: Mapped[int] = mapped_column(Integer, default=0)
    delay_days: Mapped[int] = mapped_column(Integer, default=0)
    
    # Project Link
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    
    # Plan B (Ghost Timeline)
    plan_b_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    plan_b_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # WBS Tree structure
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True)
    node_type: Mapped[str] = mapped_column(String(20), default="TASK", server_default="TASK")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    estimated_hours: Mapped[float] = mapped_column(Float, default=0.0, server_default="0.0")
    actual_hours: Mapped[float] = mapped_column(Float, default=0.0, server_default="0.0")
    
    # Gitea Integration
    gitea_repo: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    gitea_issue_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Relationships
    project: Mapped[Optional["Project"]] = relationship(back_populates="tasks", lazy="select")
    subtasks: Mapped[List["SubTask"]] = relationship(back_populates="task", cascade="all, delete-orphan", lazy="select")
    plan: Mapped[Optional["Plan"]] = relationship(back_populates="task", cascade="all, delete-orphan", uselist=False, lazy="select")
    comments: Mapped[List["Comment"]] = relationship(back_populates="task", cascade="all, delete-orphan", lazy="select")
    messages: Mapped[List["Message"]] = relationship(back_populates="task", lazy="select")
    
    # Hierarchical WBS tree relationships
    children: Mapped[List["Task"]] = relationship(
        "Task",
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="Task.sort_order",
        lazy="select"
    )
    parent: Mapped[Optional["Task"]] = relationship(
        "Task",
        back_populates="children",
        remote_side="Task.id",
        lazy="select"
    )
    
    dependencies: Mapped[List["Task"]] = relationship(
        "Task",
        secondary=task_dependency,
        primaryjoin="Task.id==task_dependency.c.task_id",
        secondaryjoin="Task.id==task_dependency.c.depends_on_id",
        backref="dependent_tasks",
        lazy="select"
    )

    @property
    def is_summary(self) -> bool:
        if "children" in self.__dict__:
            return len(self.children) > 0
        return False
