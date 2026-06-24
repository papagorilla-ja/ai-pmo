from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Any

from app.database import get_db
from app.models.task import Task
from app.models.subtask import SubTask
from app.models.plan import Plan

router = APIRouter()

@router.get("/summary", response_model=Dict[str, Any])
async def get_daily_standup_summary(db: AsyncSession = Depends(get_db)):
    """
    Returns daily summary:
    1. AI activities completed last night (Subtasks completed recently)
    2. Top 3 actions requiring human decision
    """
    # 1. AI completed activities (completed_at is not null)
    subtask_result = await db.execute(
        select(SubTask).where(SubTask.status.in_(["REVIEW", "DONE"])).order_by(SubTask.completed_at.desc()).limit(5)
    )
    completed_subtasks = subtask_result.scalars().all()
    
    # Bulk fetch tasks to avoid N+1 queries
    subtask_task_ids = {sub.task_id for sub in completed_subtasks if sub.task_id}
    subtask_tasks = {}
    if subtask_task_ids:
        tasks_res = await db.execute(select(Task).where(Task.id.in_(subtask_task_ids)))
        subtask_tasks = {task.id: task for task in tasks_res.scalars().all()}
        
    ai_completed = []
    for sub in completed_subtasks:
        task = subtask_tasks.get(sub.task_id)
        task_title = task.title if task else "Unknown Task"
        ai_completed.append({
            "subtask_id": str(sub.id),
            "subtask_title": sub.title,
            "parent_task_title": task_title,
            "status": sub.status,
            "completed_at": sub.completed_at.isoformat() if sub.completed_at else None
        })
        
    # 2. Top 3 Actions needing human approval
    # We prioritize:
    # A. Plan-First drafts waiting for approval (Plan.status == 'DRAFT')
    # B. Tasks in REVIEW status
    # C. Delayed tasks (delay_days > 0)
    actions = []
    
    # A. Plans in Draft
    plan_result = await db.execute(
        select(Plan).where(Plan.status == "DRAFT").order_by(Plan.created_at).limit(3)
    )
    draft_plans = plan_result.scalars().all()
    
    # Bulk fetch tasks to avoid N+1 queries
    plan_task_ids = {plan.task_id for plan in draft_plans if plan.task_id}
    plan_tasks = {}
    if plan_task_ids:
        plan_tasks_res = await db.execute(select(Task).where(Task.id.in_(plan_task_ids)))
        plan_tasks = {task.id: task for task in plan_tasks_res.scalars().all()}

    for plan in draft_plans:
        task = plan_tasks.get(plan.task_id)
        if task and len(actions) < 3:
            actions.append({
                "type": "APPROVE_PLAN",
                "target_id": str(task.id),
                "title": f"【方針承認】{task.title}",
                "description": f"AIエージェントが作成した「{task.title}」の作業方針とマイクロタスクをご確認ください。"
            })
            
    # B. Tasks in REVIEW
    task_review_result = await db.execute(
        select(Task).where(Task.status == "REVIEW").limit(3)
    )
    review_tasks = task_review_result.scalars().all()
    for task in review_tasks:
        if len(actions) < 3:
            actions.append({
                "type": "REVIEW_TASK",
                "target_id": str(task.id),
                "title": f"【成果物レビュー】{task.title}",
                "description": f"AIワーカーがすべてのマイクロタスクを完了しました。最終成果物をご確認ください。"
            })
            
    # C. Delayed tasks
    delayed_result = await db.execute(
        select(Task).where(Task.delay_days > 0).limit(3)
    )
    delayed_tasks = delayed_result.scalars().all()
    for task in delayed_tasks:
        if len(actions) < 3:
            actions.append({
                "type": "HEARING_LATE",
                "target_id": str(task.id),
                "title": f"【遅延アラート】{task.title}",
                "description": f"現在スケジュールから遅延しています。AIからの残工数ヒアリングにご回答ください。"
            })
            
    return {
        "ai_completed_summary": ai_completed,
        "top_actions": actions
    }
