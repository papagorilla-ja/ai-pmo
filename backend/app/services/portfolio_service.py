import logging
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.models.project import Project
from app.models.task import Task
from app.models.resource_allocation import ResourceAllocation

logger = logging.getLogger(__name__)

class PortfolioService:
    async def audit_conflicts(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """
        Scans all projects to check for delay risks and resource bottlenecks.
        Proposes reallocation of resources from healthy projects.
        """
        # Load projects with relations
        result = await db.execute(
            select(Project).options(
                selectinload(Project.tasks),
                selectinload(Project.allocations)
            )
        )
        projects = result.scalars().all()
        project_map = {p.id: p for p in projects}
        
        proposals = []
        
        # 1. Identify delayed projects/tasks
        for proj in projects:
            delayed_tasks = [t for t in proj.tasks if t.delay_days > 0]
            if not delayed_tasks:
                continue
                
            for dt in delayed_tasks:
                # We need skills for this task. Let's assume based on title
                needed_skill = "Vue3" if "フロント" in dt.title or "UI" in dt.title else "FastAPI"
                
                # 2. Find matching resources in other projects that are healthy
                for other_proj in projects:
                    if other_proj.id == proj.id:
                        continue
                        
                    # Check if other project has delay
                    other_delayed = [t for t in other_proj.tasks if t.delay_days > 0]
                    if other_delayed:
                        continue # Skip projects that are also delayed
                        
                    # Search for resources with matching skills in this healthy project
                    for alloc in other_proj.allocations:
                        if needed_skill in alloc.skill_tags and alloc.allocation_percent >= 50 and not alloc.is_ai:
                            # We found a potential donor! Propose shifting 20% allocation.
                            proposals.append({
                                "id": f"shift_{alloc.id}_{dt.id}",
                                "delayed_project_id": str(proj.id),
                                "delayed_project_name": proj.name,
                                "delayed_task_id": str(dt.id),
                                "delayed_task_title": dt.title,
                                "donor_project_id": str(other_proj.id),
                                "donor_project_name": other_proj.name,
                                "resource_name": alloc.resource_name,
                                "skill": needed_skill,
                                "shift_percent": 20,
                                "substitute_ai_name": "AI_WORKER_BACKFILL",
                                "description": (
                                    f"プロジェクト「{other_proj.name}」の進捗には現在余裕があるため、"
                                    f"同等スキルを持つ【{alloc.resource_name}】の稼働を 20% シフトし、"
                                    f"遅延している「{dt.title}」を補強します。また、「{other_proj.name}」側の"
                                    f"定型業務の穴埋めとして AIワーカー（{needed_skill} 補填）を追加します。"
                                )
                            })
                            
        return proposals

    async def apply_allocation_shift(self, db: AsyncSession, delayed_project_id: str, donor_project_id: str, resource_name: str, shift_percent: int) -> bool:
        """
        Performs the resource shift and backfills with an AI worker.
        """
        dp_id = UUID(delayed_project_id)
        sp_id = UUID(donor_project_id)
        
        # 1. Load allocations
        result = await db.execute(
            select(ResourceAllocation).where(
                ResourceAllocation.project_id == sp_id,
                ResourceAllocation.resource_name == resource_name
            )
        )
        donor_alloc = result.scalars().first()
        if not donor_alloc:
            return False
            
        # Reduce donor allocation
        donor_alloc.allocation_percent = max(0, donor_alloc.allocation_percent - shift_percent)
        
        # 2. Add resource allocation to delayed project
        target_result = await db.execute(
            select(ResourceAllocation).where(
                ResourceAllocation.project_id == dp_id,
                ResourceAllocation.resource_name == resource_name
            )
        )
        target_alloc = target_result.scalars().first()
        if target_alloc:
            target_alloc.allocation_percent += shift_percent
        else:
            new_alloc = ResourceAllocation(
                project_id=dp_id,
                resource_name=resource_name,
                skill_tags=donor_alloc.skill_tags,
                allocation_percent=shift_percent,
                is_ai=False
            )
            db.add(new_alloc)
            
        # 3. Add AI worker backfill on donor project
        ai_backfill = ResourceAllocation(
            project_id=sp_id,
            resource_name="AI_WORKER_BACKFILL",
            skill_tags=donor_alloc.skill_tags,
            allocation_percent=shift_percent,
            is_ai=True
        )
        db.add(ai_backfill)
        
        # 4. Push plan B timeline dates for delayed tasks
        # (Since we reinforced it, we reduce the delay days!)
        result_tasks = await db.execute(
            select(Task).where(Task.project_id == dp_id, Task.delay_days > 0)
        )
        delayed_tasks = result_tasks.scalars().all()
        for dt in delayed_tasks:
            # Shift dates closer (reduce delay by 1 day as buffer recovery)
            from datetime import timedelta
            if dt.plan_b_end:
                dt.plan_b_end = dt.plan_b_end - timedelta(days=1)
                dt.delay_days = max(0, dt.delay_days - 1)
                
        await db.commit()
        return True

portfolio_service = PortfolioService()
