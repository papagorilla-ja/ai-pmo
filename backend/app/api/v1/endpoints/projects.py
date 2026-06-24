from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime, timezone, timedelta
from typing import List

from app.database import get_db
from app.models.project import Project
from app.models.task import Task
from app.schemas.project import ProjectCreate, ProjectResponse
from app.schemas.task import TaskTreeNode
from app.services.wbs_service import wbs_service

router = APIRouter()

@router.post("/", response_model=ProjectResponse)
async def create_project(project_in: ProjectCreate, db: AsyncSession = Depends(get_db)):
    project = Project(
        name=project_in.name,
        status=project_in.status,
        template_type=project_in.template_type,
        organization_id=project_in.organization_id or UUID("00000000-0000-0000-0000-000000000000")
    )
    db.add(project)
    await db.flush()
    
    # Generate skeleton tasks
    now = datetime.now(timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0)
    
    if project_in.template_type == "PHASE_BASED":
        phases = ["要件定義", "設計", "開発", "テスト", "リリース"]
        for idx, phase_name in enumerate(phases):
            p_start = now + timedelta(days=idx * 7)
            p_end = p_start + timedelta(days=6)
            task = Task(
                title=phase_name,
                description=f"{phase_name}フェーズの管理サマリー",
                status="TODO",
                priority="MEDIUM",
                assignee_type="HUMAN",
                assignee_name="",
                planned_start=p_start,
                planned_end=p_end,
                project_id=project.id,
                parent_id=None,
                node_type="PHASE",
                sort_order=idx,
                estimated_hours=0.0,
                actual_hours=0.0
            )
            db.add(task)
            
    elif project_in.template_type == "FEATURE_BASED":
        feature_task = Task(
            title="主要機能A",
            description="主要機能Aの開発・リリース管理サマリー",
            status="TODO",
            priority="MEDIUM",
            assignee_type="HUMAN",
            assignee_name="",
            planned_start=now,
            planned_end=now + timedelta(days=20),
            project_id=project.id,
            parent_id=None,
            node_type="FEATURE",
            sort_order=0,
            estimated_hours=0.0,
            actual_hours=0.0
        )
        db.add(feature_task)
        await db.flush()
        
        phases = ["要件定義・設計", "開発・テスト", "リリース"]
        for idx, phase_name in enumerate(phases):
            p_start = now + timedelta(days=idx * 7)
            p_end = p_start + timedelta(days=6)
            child_task = Task(
                title=phase_name,
                description=f"{phase_name}タスク",
                status="TODO",
                priority="MEDIUM",
                assignee_type="HUMAN",
                assignee_name="",
                planned_start=p_start,
                planned_end=p_end,
                project_id=project.id,
                parent_id=feature_task.id,
                node_type="PHASE",
                sort_order=idx,
                estimated_hours=0.0,
                actual_hours=0.0
            )
            db.add(child_task)
            
    await db.commit()
    
    # Reload project with relationships preloaded to prevent response serialization lazy load error
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Project)
        .where(Project.id == project.id)
        .options(
            selectinload(Project.allocations),
            selectinload(Project.tasks).selectinload(Task.dependencies),
            selectinload(Project.tasks).selectinload(Task.subtasks),
            selectinload(Project.tasks).selectinload(Task.plan)
        )
    )
    return result.scalar()

@router.get("/{project_id}/tree", response_model=List[TaskTreeNode])
async def get_project_wbs(project_id: UUID, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    return await wbs_service.get_project_wbs_tree(db, project_id)
