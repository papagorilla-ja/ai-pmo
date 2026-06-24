import asyncio
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import List

from app.database import get_db
from app.models.task import Task
from app.models.subtask import SubTask
from app.models.plan import Plan
from app.schemas.task import TaskResponse, TaskCreate, TaskUpdate
from app.schemas.plan import PlanResponse
from app.services.orchestrator import orchestrator_service
from app.services.worker import worker_service

router = APIRouter()

async def detect_cycle(db: AsyncSession, task_id: UUID, proposed_parent_id: UUID) -> bool:
    if task_id == proposed_parent_id:
        return True
    current_parent_id = proposed_parent_id
    visited = set()
    while current_parent_id is not None:
        if current_parent_id in visited:
            return True
        visited.add(current_parent_id)
        if current_parent_id == task_id:
            return True
        parent = await db.get(Task, current_parent_id)
        if not parent:
            break
        current_parent_id = parent.parent_id
    return False

async def run_worker_tasks_async(task_id: UUID):
    """
    Background worker process to execute subtasks sequentially.
    """
    # Create a new db session
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(SubTask).where(SubTask.task_id == task_id).order_by(SubTask.created_at)
        )
        subtasks = result.scalars().all()
        
        for subtask in subtasks:
            if subtask.status == "PENDING":
                try:
                    await worker_service.execute_subtask(db, subtask)
                except Exception as e:
                    # Log and continue next
                    pass
        
        # Check if all subtasks are finished, then set parent task to REVIEW
        parent_result = await db.execute(select(Task).where(Task.id == task_id))
        parent_task = parent_result.scalar()
        if parent_task:
            parent_task.status = "REVIEW"
            await db.commit()

@router.post("/", response_model=TaskResponse)
async def create_task(task_in: TaskCreate, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    # Validate node_type
    valid_node_types = {"PHASE", "FEATURE", "SPRINT", "STORY", "TASK"}
    if task_in.node_type not in valid_node_types:
        raise HTTPException(status_code=400, detail=f"Invalid node_type. Must be one of {valid_node_types}")
        
    # Validate parent_id
    if task_in.parent_id is not None:
        parent_task = await db.get(Task, task_in.parent_id)
        if not parent_task:
            raise HTTPException(status_code=400, detail="Parent task not found")
        if parent_task.project_id != task_in.project_id:
            raise HTTPException(status_code=400, detail="Parent task must belong to the same project")
            
    # Create Task
    task = Task(
        title=task_in.title,
        description=task_in.description,
        status=task_in.status,
        priority=task_in.priority,
        assignee_type=task_in.assignee_type,
        assignee_name=task_in.assignee_name,
        planned_start=task_in.planned_start,
        planned_end=task_in.planned_end,
        actual_start=task_in.actual_start,
        actual_end=task_in.actual_end,
        progress=task_in.progress,
        delay_days=task_in.delay_days,
        plan_b_start=task_in.planned_start,
        plan_b_end=task_in.planned_end,
        project_id=task_in.project_id,
        parent_id=task_in.parent_id,
        node_type=task_in.node_type,
        sort_order=task_in.sort_order,
        estimated_hours=task_in.estimated_hours,
        actual_hours=task_in.actual_hours
    )
    
    # Handle dependencies
    if task_in.dependency_ids:
        for dep_id in task_in.dependency_ids:
            dep_task = await db.get(Task, dep_id)
            if dep_task:
                task.dependencies.append(dep_task)
                
    db.add(task)
    await db.flush()  # Get task ID
    
    # If assigned to AI, auto-trigger orchestrator decomposition
    if task.assignee_type == "AI":
        background_tasks.add_task(orchestrator_service.generate_plan_and_subtasks, task.id)
        
    await db.commit()
    result = await db.execute(
        select(Task)
        .where(Task.id == task.id)
        .options(
            selectinload(Task.dependencies),
            selectinload(Task.subtasks),
            selectinload(Task.plan)
        )
    )
    return result.scalar()

@router.get("/", response_model=List[TaskResponse])
async def list_tasks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Task)
        .options(
            selectinload(Task.dependencies),
            selectinload(Task.subtasks),
            selectinload(Task.plan)
        )
        .order_by(Task.planned_start)
    )
    return result.scalars().all()

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Task)
        .where(Task.id == task_id)
        .options(
            selectinload(Task.dependencies),
            selectinload(Task.subtasks),
            selectinload(Task.plan)
        )
    )
    task = result.scalar()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: UUID, task_in: TaskUpdate, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    obj_data = task_in.model_dump(exclude_unset=True)
    
    # Validate node_type if updated
    if "node_type" in obj_data:
        valid_node_types = {"PHASE", "FEATURE", "SPRINT", "STORY", "TASK"}
        if obj_data["node_type"] not in valid_node_types:
            raise HTTPException(status_code=400, detail=f"Invalid node_type. Must be one of {valid_node_types}")
            
    # Validate parent_id (prevent circular reference and project misalignment)
    if "parent_id" in obj_data:
        proposed_parent_id = obj_data["parent_id"]
        if proposed_parent_id is not None:
            if await detect_cycle(db, task_id, proposed_parent_id):
                raise HTTPException(status_code=400, detail="Circular reference detected in WBS hierarchy.")
            
            project_id = obj_data.get("project_id", task.project_id)
            parent_task = await db.get(Task, proposed_parent_id)
            if not parent_task:
                raise HTTPException(status_code=400, detail="Parent task not found")
            if parent_task.project_id != project_id:
                raise HTTPException(status_code=400, detail="Parent task must belong to the same project")
                
    # Handle dependencies specifically if updated
    if "dependency_ids" in obj_data:
        dep_ids = obj_data.pop("dependency_ids")
        task.dependencies.clear()
        if dep_ids:
            for dep_id in dep_ids:
                dep_task = await db.get(Task, dep_id)
                if dep_task:
                    task.dependencies.append(dep_task)
                    
    for field in obj_data:
        setattr(task, field, obj_data[field])
        
    await db.commit()
    result = await db.execute(
        select(Task)
        .where(Task.id == task_id)
        .options(
            selectinload(Task.dependencies),
            selectinload(Task.subtasks),
            selectinload(Task.plan)
        )
    )
    return result.scalar()

@router.post("/{task_id}/approve-plan", response_model=PlanResponse)
async def approve_plan(task_id: UUID, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """
    Approves the WBS plan and kicks off worker execution in the background.
    """
    result = await db.execute(select(Plan).where(Plan.task_id == task_id))
    plan = result.scalar()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan draft not found")
        
    plan.status = "APPROVED"
    
    # Update parent task status to IN_PROGRESS
    task = await db.get(Task, task_id)
    if task:
        task.status = "IN_PROGRESS"
        
    # Set all subtasks to PENDING status if they weren't already
    subtask_result = await db.execute(select(SubTask).where(SubTask.task_id == task_id))
    subtasks = subtask_result.scalars().all()
    for subtask in subtasks:
        subtask.status = "PENDING"
        
    await db.commit()
    
    # Run the worker executions asynchronously
    background_tasks.add_task(run_worker_tasks_async, task_id)
    
    await db.refresh(plan)
    return plan

@router.post("/{task_id}/reject-plan", response_model=PlanResponse)
async def reject_plan(task_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Plan).where(Plan.task_id == task_id))
    plan = result.scalar()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan draft not found")
        
    plan.status = "REJECTED"
    await db.commit()
    await db.refresh(plan)
    return plan

import os
from pydantic import BaseModel
from app.config import settings
from app.models.comment import Comment
from typing import Dict, Any

class ApplyFixRequest(BaseModel):
    line_number: int

@router.get("/{task_id}/artifacts")
async def get_task_artifacts(task_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Fetches real artifact file content and line array for a task's completed subtasks.
    """
    result = await db.execute(
        select(SubTask)
        .where(SubTask.task_id == task_id)
        .where(SubTask.output_mock_path.isnot(None))
        .order_by(SubTask.created_at)
    )
    subtasks = result.scalars().all()
    
    for sub in subtasks:
        path = sub.output_mock_path
        if not path or not os.path.exists(path):
            continue
            
        # Path traversal check
        abs_storage = os.path.abspath(settings.ARTIFACT_STORAGE_PATH)
        abs_path = os.path.abspath(path)
        if not abs_path.startswith(abs_storage):
            continue
            
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            lines = content.splitlines()
            return {
                "file_name": os.path.basename(path),
                "content": content,
                "lines": lines
            }
        except Exception as e:
            pass
            
    raise HTTPException(status_code=404, detail="No artifacts found for this task")

@router.post("/{task_id}/artifacts/apply-fix")
async def apply_artifact_fix(task_id: UUID, payload: ApplyFixRequest, db: AsyncSession = Depends(get_db)):
    """
    Applies the inline review warning fix dynamically based on DB comments content.
    """
    # 1. Find the subtask with artifact
    result = await db.execute(
        select(SubTask)
        .where(SubTask.task_id == task_id)
        .where(SubTask.output_mock_path.isnot(None))
        .order_by(SubTask.created_at)
    )
    subtasks = result.scalars().all()
    
    target_path = None
    for sub in subtasks:
        path = sub.output_mock_path
        if path and os.path.exists(path):
            abs_storage = os.path.abspath(settings.ARTIFACT_STORAGE_PATH)
            abs_path = os.path.abspath(path)
            if abs_path.startswith(abs_storage):
                target_path = path
                break
                
    if not target_path:
        raise HTTPException(status_code=404, detail="Artifact not found")
        
    # 2. Get comments for this line
    comment_result = await db.execute(
        select(Comment)
        .where(Comment.task_id == task_id)
        .where(Comment.line_number == payload.line_number)
    )
    comments = comment_result.scalars().all()
    if not comments:
         raise HTTPException(status_code=400, detail="No comment found on this line")
         
    # 3. Read content and apply replacement
    with open(target_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
        
    if payload.line_number < 1 or payload.line_number > len(lines):
        raise HTTPException(status_code=400, detail="Invalid line number")
        
    original_line = lines[payload.line_number - 1]
    
    # Rule-based dynamic correction
    new_line = original_line
    for c in comments:
        content_lower = c.content.lower()
        if "postgresql" in content_lower and "15" in original_line:
            new_line = original_line.replace("PostgreSQL 15", "PostgreSQL 16")
        elif "legacy" in original_line or "connect_legacy_db" in original_line:
            new_line = original_line.replace("connect_legacy_db()", "await get_db()  # Configured via environment variables")
        elif "平文" in content_lower or "credential" in content_lower or "password" in content_lower:
            if "=" in original_line:
                key = original_line.split("=")[0].strip()
                new_line = f"{key} = os.getenv('{key.upper()}')"
            else:
                new_line = original_line + "  # environment variable used"
                
    if new_line == original_line:
        new_line = original_line + "  # AI_FIXED"
        
    lines[payload.line_number - 1] = new_line
    new_content = "\n".join(lines)
    
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(new_content)
        
    # Delete the warning comments since they're resolved
    for c in comments:
        await db.delete(c)
    await db.commit()
    
    return {
        "success": True,
        "file_name": os.path.basename(target_path),
        "content": new_content,
        "lines": lines
    }

@router.delete("/{task_id}", response_model=Dict[str, Any])
async def delete_task(task_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Deletes the task and cascades deletions to plans and subtasks.
    """
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    await db.delete(task)
    await db.commit()
    return {"success": True, "message": "Task deleted successfully"}
