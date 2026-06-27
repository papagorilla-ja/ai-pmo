import logging
import re
import json
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.models.project import Project
from app.models.task import Task
from app.models.resource_allocation import ResourceAllocation
from app.services.llm import llm_service

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
                                "delay_info": f"{dt.delay_days}日遅延中",
                                "description": (
                                    f"プロジェクト「{other_proj.name}」の進捗には現在余裕があるため、"
                                    f"同等スキルを持つ【{alloc.resource_name}】の稼働を 20% シフトし、"
                                    f"遅延している「{dt.title}」を補強します。また、「{other_proj.name}」側の"
                                    f"定型業務の穴埋めとして AIワーカー（{needed_skill} 補填）を追加します。"
                                )
                            })
                            
        # LLM でより豊かな説明文を再生成（失敗時はテンプレート文を維持）
        if proposals:
            context_lines = [
                f"- 案{i+1}: {p['delayed_project_name']}のタスク「{p['delayed_task_title']}」が{p['delay_info']}。"
                f"{p['donor_project_name']}の{p['resource_name']}（{p['skill']}スキル）を{p['shift_percent']}%シフト提案。"
                for i, p in enumerate(proposals)
            ]
            system_prompt = (
                "あなたはPMOのリソース調停アナリストです。"
                "以下のリソース競合・遅延状況を分析し、各調停案を経営層向けに端的な日本語で説明してください。"
                "出力は JSON 配列のみ。各要素は提示された案の番号（1始まり）に対応させること。"
                '形式: [{"index": 1, "description": "50字以内の説明文"}]'
                "解説不要。JSONのみ出力。"
            )
            try:
                raw = await llm_service.get_response(system_prompt, "\n".join(context_lines), temperature=0.3)
                cleaned = re.sub(r'^```(?:json)?\s*', '', raw.strip(), flags=re.MULTILINE)
                cleaned = re.sub(r'\s*```$', '', cleaned.strip(), flags=re.MULTILINE)
                llm_results = json.loads(cleaned.strip())
                for item in llm_results:
                    idx = item.get("index", 0) - 1
                    desc = item.get("description", "")
                    if 0 <= idx < len(proposals) and desc:
                        proposals[idx]["description"] = desc
            except Exception as e:
                logger.warning(f"LLM conflict description generation failed (using template): {e}")

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
