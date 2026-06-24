import re
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.task import Task
from app.models.message import Message

logger = logging.getLogger(__name__)

class RiskEngineService:
    def parse_remaining_hours(self, input_text: str) -> float:
        """
        Parses text input (e.g. '5時間', '3人日', '2 days', '8h') into numerical hours.
        """
        text = input_text.lower()
        
        # Check for days / 人日
        day_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:日|人日|day|d)', text)
        if day_match:
            return float(day_match.group(1)) * 8.0  # 1 day = 8 hours
            
        # Check for hours / 時間
        hour_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:時間|h|hour)', text)
        if hour_match:
            return float(hour_match.group(1))
            
        # Try raw number
        number_match = re.search(r'(\d+(?:\.\d+)?)', text)
        if number_match:
            return float(number_match.group(1))
            
        return 8.0  # default to 1 person-day if unparseable

    async def calculate_plan_b(self, db: AsyncSession, delayed_task_id: str, remaining_hours: float) -> Dict[str, Any]:
        """
        Calculates Plan B schedule.
        1. Estimates delay for the specific task based on remaining hours.
        2. Adjusts plan_b_start/end dates for the task.
        3. Cascades the delay through WBS dependency tree.
        4. If milestones are missed, demotes/postpones 'LOW' priority tasks to keep key deadlines.
        """
        logger.info(f"Calculating Plan B for task {delayed_task_id} with remaining hours: {remaining_hours}")
        
        # Load all tasks, their dependencies, and children
        result = await db.execute(
            select(Task).options(
                selectinload(Task.dependencies),
                selectinload(Task.children)
            )
        )
        tasks = result.scalars().all()
        if not tasks:
            return {"success": False, "detail": "No tasks"}
            
        task_map = {t.id: t for t in tasks}
        
        from uuid import UUID
        target_task = task_map.get(UUID(delayed_task_id))
        if not target_task:
            return {"success": False, "detail": "Task not found"}
            
        # Initialize Plan B dates if not set
        for t in tasks:
            t.plan_b_start = t.planned_start
            t.plan_b_end = t.planned_end
            
        # Calculate task delay.
        now = datetime.now(target_task.planned_end.tzinfo)
        remaining_time = target_task.planned_end - now
        remaining_time_hours = max(0.0, remaining_time.total_seconds() / 3600.0)
        
        # If remaining effort > remaining calendar hours, we have a delay
        deficit_hours = remaining_hours - remaining_time_hours
        
        if deficit_hours > 0:
            # Assuming 8 hours of work per calendar day, push the end date
            added_days = int(deficit_hours / 8) + 1
            target_task.plan_b_end = target_task.planned_end + timedelta(days=added_days)
            target_task.delay_days = added_days
            logger.info(f"Task {target_task.title} pushed by {added_days} days in Plan B.")
        else:
            target_task.delay_days = 0
            
        # Cascade changes through dependencies (leaf tasks only, summary nodes rolled up)
        changed = True
        cascade_loops = 0
        leaf_tasks = [t for t in tasks if len(t.children) == 0]
        summary_tasks = [t for t in tasks if len(t.children) > 0]
        
        # Helper to roll up summary nodes
        def rollup_summary_nodes():
            updated = False
            for s in summary_tasks:
                active_children = [c for c in s.children if c.id in task_map]
                if not active_children:
                    continue
                min_start = min(c.plan_b_start for c in active_children if c.plan_b_start)
                max_end = max(c.plan_b_end for c in active_children if c.plan_b_end)
                delay_days = max(c.delay_days for c in active_children)
                if s.plan_b_start != min_start or s.plan_b_end != max_end or s.delay_days != delay_days:
                    s.plan_b_start = min_start
                    s.plan_b_end = max_end
                    s.delay_days = delay_days
                    updated = True
            return updated

        # First rollup
        rollup_summary_nodes()
        
        while changed and cascade_loops < 50:
            changed = False
            cascade_loops += 1
            for t in leaf_tasks:
                for dep in t.dependencies:
                    dep_end = dep.plan_b_end or dep.planned_end
                    t_start = t.plan_b_start or t.planned_start
                    if dep_end > t_start:
                        duration = t.planned_end - t.planned_start
                        new_start = dep_end + timedelta(days=1)  # start day after dependency ends
                        new_end = new_start + duration
                        
                        t.plan_b_start = new_start
                        t.plan_b_end = new_end
                        changed = True
            
            if rollup_summary_nodes():
                changed = True
                        
        # Plan B Scope adjustment: If overall timeline pushes beyond a key release threshold
        # (e.g. final deadline pushed, let's say after a certain date), we postpone low-priority tasks.
        postponed_tasks = []
        for t in tasks:
            if t.priority == "LOW" and t.delay_days > 0:
                # Postpone to next phase (e.g. move planned date by 30 days and clear delay)
                t.plan_b_start = t.planned_start + timedelta(days=30)
                t.plan_b_end = t.planned_end + timedelta(days=30)
                postponed_tasks.append(t.title)
                
        await db.commit()
        
        return {
            "success": True,
            "target_task": target_task.title,
            "delay_days": target_task.delay_days,
            "postponed_low_priority_tasks": postponed_tasks,
            "tasks": [
                {
                    "id": str(t.id),
                    "title": t.title,
                    "planned_start": t.planned_start.isoformat(),
                    "planned_end": t.planned_end.isoformat(),
                    "plan_b_start": t.plan_b_start.isoformat() if t.plan_b_start else None,
                    "plan_b_end": t.plan_b_end.isoformat() if t.plan_b_end else None,
                    "delay_days": t.delay_days
                } for t in tasks
            ]
        }

    async def apply_plan_b_schedule(self, db: AsyncSession) -> int:
        """
        Applies Plan B schedule dates as the official planned schedule.
        Returns the number of adjusted tasks.
        """
        result = await db.execute(select(Task))
        tasks = result.scalars().all()
        
        applied_count = 0
        for t in tasks:
            if t.plan_b_start and t.plan_b_end:
                t.planned_start = t.plan_b_start
                t.planned_end = t.plan_b_end
                t.delay_days = 0  # reset delay alert after applying the plan
                applied_count += 1
                
        await db.commit()
        return applied_count

risk_engine_service = RiskEngineService()
