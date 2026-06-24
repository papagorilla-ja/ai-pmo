from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from uuid import UUID
from typing import Dict, Any

from app.database import get_db
from app.services.risk_engine import risk_engine_service
from app.models.task import Task
from app.models.message import Message

router = APIRouter()

class HearingResponse(BaseModel):
    remaining_text: str  # e.g., "あと5時間", "2人日"

class RecalculateRequest(BaseModel):
    task_id: UUID
    remaining_hours: float

@router.post("/hearing/{task_id}", response_model=Dict[str, Any])
async def submit_hearing_response(task_id: UUID, payload: HearingResponse, db: AsyncSession = Depends(get_db)):
    """
    Submits user response to delay hearing, parses remaining hours,
    recalculates Plan B dates, and posts messages to the internal chat thread.
    """
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    # 1. Parse hours
    remaining_hours = risk_engine_service.parse_remaining_hours(payload.remaining_text)
    
    # 2. Add user response to messages
    user_msg = Message(
        sender_type="USER",
        sender_name="Manager",
        content=f"【ヒアリング回答】残工数は約 {payload.remaining_text}（{remaining_hours} 時間相当）です。",
        task_id=task_id
    )
    db.add(user_msg)
    
    # 3. Recalculate WBS schedule
    plan_b_results = await risk_engine_service.calculate_plan_b(db, str(task_id), remaining_hours)
    
    # 4. Generate AI feedback response message
    postponed_msg = ""
    if plan_b_results.get("postponed_low_priority_tasks"):
        postponed_msg = f" 調整のため、低優先度タスク ({', '.join(plan_b_results['postponed_low_priority_tasks'])}) の日程を次フェーズへ遅延調整しました。"
        
    ai_feedback = Message(
        sender_type="AI_PMO",
        sender_name="AI_PMO",
        content=(
            f"かしこまりました。残工数 {remaining_hours} 時間をベースに、スケジュール再計算（プランB）を実行しました。"
            f"このタスクは完了予定が約 {task.delay_days} 日遅れる見込みです。{postponed_msg}\n"
            "ガントチャート画面にて半透明（ゴースト表示）で再編スケジュールをご確認いただき、よろしければ適用（Approve Plan B）してください。"
        ),
        task_id=task_id
    )
    db.add(ai_feedback)
    await db.commit()
    
    return {
        "success": True,
        "parsed_hours": remaining_hours,
        "delay_days": task.delay_days,
        "plan_b_results": plan_b_results
    }

@router.post("/recalculate", response_model=Dict[str, Any])
async def recalculate_schedule(payload: RecalculateRequest, db: AsyncSession = Depends(get_db)):
    """
    Direct endpoint to trigger Plan B calculations.
    """
    return await risk_engine_service.calculate_plan_b(db, str(payload.task_id), payload.remaining_hours)

@router.post("/apply-plan-b", response_model=Dict[str, Any])
async def apply_plan_b(db: AsyncSession = Depends(get_db)):
    """
    Applies Plan B schedule dates as the official planned schedule.
    """
    applied_count = await risk_engine_service.apply_plan_b_schedule(db)
    return {"success": True, "applied_count": applied_count}
