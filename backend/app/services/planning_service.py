import json
import logging
from uuid import UUID
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.project import Project
from app.models.task import Task, task_dependency
from app.models.resource import Resource
from app.api.v1.endpoints.resources import is_assignable
from app.services.llm import llm_service
from app.services.rag import rag_service
from app.services.wbs_service import wbs_service
from app.services.orchestrator import orchestrator_service
from app.schemas.planning import (
    AnalyzeRequest,
    AnalyzeResponse,
    PlanNode,
    SuggestedAssignee,
    StaffingRecommendation,
    PreventiveTask,
    ApplyRequest
)

logger = logging.getLogger(__name__)

class PlanningService:
    def _clean_json_string(self, text: str) -> str:
        text = text.strip()
        # Find first '{' and last '}'
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            return text[start:end+1]
        return text

    async def analyze(self, db: AsyncSession, req: AnalyzeRequest) -> AnalyzeResponse:
        """
        Gathers project WBS, resources, and lessons learned. Calls LLM to analyze the source text,
        then evaluates skill matches, capacities, and lesson-learned preventive tasks on the server.
        """
        # 1. Gather assignable resources
        result = await db.execute(select(Resource))
        all_resources = result.scalars().all()
        assignable_resources = [r for r in all_resources if is_assignable(r)]

        resources_context = []
        for r in assignable_resources:
            resources_context.append({
                "id": str(r.id),
                "name": r.name,
                "role": r.role,
                "skills_phase": r.skills_phase,
                "skills_domain": r.skills_domain,
                "skills_free": r.skills_free,
                "daily_working_hours": r.daily_working_hours,
                "allocation_limit": r.allocation_limit,
                "working_days": r.working_days,
                "available_from": r.available_from,
                "available_to": r.available_to
            })

        # 2. Gather existing WBS if project_id is provided
        existing_wbs_context = ""
        template_type = "FLAT"
        if req.project_id:
            project = await db.get(Project, req.project_id)
            if project:
                template_type = project.template_type
                tree = await wbs_service.get_project_wbs_tree(db, req.project_id)
                
                # Format WBS tree structure into text
                def format_node(node, depth=0):
                    lines = [f"{'  ' * depth}- [{node.node_type}] Title: {node.title}, ID: {node.id}, Estimated: {node.estimated_hours}h, Assignee: {node.assignee_name}"]
                    for child in getattr(node, "children", []):
                        lines.append(format_node(child, depth + 1))
                    return "\n".join(lines)
                
                existing_wbs_context = "\n".join(format_node(root) for root in tree)
        elif req.new_project:
            template_type = req.new_project.template_type

        # 3. Search RAG for lessons learned
        lessons = await rag_service.search(req.source_text, limit=5)
        clean_lessons = []
        if lessons:
            for hit in lessons:
                meta = hit.get("metadata") or {}
                h_type = meta.get("type")
                h_conf = meta.get("confidence_score", 1.0)
                if h_type in ["message", "task", "subtask"]:
                    continue
                if h_conf < 0.7:
                    continue
                clean_lessons.append(hit)

        lessons_context = ""
        if clean_lessons:
            lessons_context = "\n".join(
                f"- Title: {hit['metadata'].get('title', 'Trouble Warning')}\n  Content: {hit['content']}"
                for hit in clean_lessons
            )

        # 4. LLM Prompt Formulation
        system_prompt = (
            "あなたはPMOのプランニングAIです。会議の議事録やメモ等のテキストから、適切な WBS（フェーズ、機能、タスク）を抽出し、JSON形式で下案を返します。\n"
            "WBSは階層構造（PHASE/FEATURE/TASK）を持ち、各タスクには最適な担当者を候補リソースから割り当ててください。\n"
            "また、提示された「過去の教訓/知識」を踏まえ、本プロジェクトで先回りすべき予防タスクを最大3件、title（具体的な対策アクション）とreason（根拠）で提案してください。該当が無ければ空配列とします。\n"
            "出力は一切の挨拶や説明を省き、指定されたフォーマットの生JSONオブジェクトのみを出力してください。\n\n"
            "【出力フォーマット】\n"
            "{\n"
            "  \"summary\": \"WBS全体の方針やアプローチのサマリー\",\n"
            "  \"nodes\": [\n"
            "    {\n"
            "      \"temp_id\": \"n1\",\n"
            "      \"title\": \"ノードのタイトル\",\n"
            "      \"description\": \"ノードの詳細な説明\",\n"
            "      \"node_type\": \"PHASE|FEATURE|TASK\",\n"
            "      \"parent_temp_id\": null,\n"
            "      \"deliverable\": \"成果物（任意）\",\n"
            "      \"estimated_hours\": 16.0,\n"
            "      \"suggested_assignee\": {\n"
            "        \"resource_id\": \"候補のresource_id（またはnull）\",\n"
            "        \"name\": \"候補の名前\",\n"
            "        \"reason\": \"アサインした理由\"\n"
            "      },\n"
            "      \"dependencies\": [\"依存するノードのtemp_id\"],\n"
            "      \"confidence\": 0.85,\n"
            "      \"required_skill\": \"アサインでマッチさせるためのスキルタグ（例: Vue3, 決済API, 要件定義 等）\"\n"
            "    }\n"
            "  ],\n"
            "  \"clarifying_questions\": [\n"
            "    \"曖昧な点に対する逆質問（必要であれば）\"\n"
            "  ],\n"
            "  \"preventive_tasks\": [\n"
            "    {\n"
            "      \"title\": \"予防タスク名（例: 〇〇申請、〇〇テスト環境準備 等の具体的な対策アクション）\",\n"
            "      \"reason\": \"なぜそれが必要なのかの根拠（過去の教訓/知識に基づくもの）\"\n"
            "    }\n"
            "  ]\n"
            "}"
        )

        user_prompt = (
            f"プロジェクトのテンプレートタイプ: {template_type}\n\n"
            f"【入力テキスト】\n{req.source_text}\n\n"
            f"【候補リソース一覧】\n{json.dumps(resources_context, ensure_ascii=False, indent=2)}\n\n"
        )
        if existing_wbs_context:
            user_prompt += f"【既存のWBS構造】\n{existing_wbs_context}\n\n"
        if lessons_context:
            user_prompt += f"【過去の教訓/知識】\n{lessons_context}\n\n"

        user_prompt += "指定されたJSONフォーマットに従って、WBS下案を生成してください。"

        logger.info("Calling LLM for WBS plan extraction...")
        def get_fallback_response():
            fallback_nodes = [
                {
                    "temp_id": "fallback_phase_1",
                    "title": "要件定義・初期調査",
                    "description": "システム構成・連携要件の調査フェーズ",
                    "node_type": "PHASE",
                    "parent_temp_id": None,
                    "deliverable": "要件定義書",
                    "estimated_hours": 0.0,
                    "suggested_assignee": None,
                    "dependencies": [],
                    "confidence": 1.0,
                    "required_skill": "General"
                },
                {
                    "temp_id": "fallback_task_1",
                    "title": "初期調査タスク",
                    "description": "LM Studioへの接続に失敗したため、フォールバックの初期調査タスクを生成しました。LLM の接続設定を確認してください。",
                    "node_type": "TASK",
                    "parent_temp_id": "fallback_phase_1",
                    "deliverable": "調査報告書",
                    "estimated_hours": 8.0,
                    "suggested_assignee": None,
                    "dependencies": [],
                    "confidence": 1.0,
                    "required_skill": "General"
                }
            ]
            return AnalyzeResponse(
                summary="【フォールバック】LLM接続不可のため、デフォルトのフェーズ雛形および初期調査タスクを提示しています。",
                nodes=[PlanNode(**n) for n in fallback_nodes],
                staffing_recommendations=[],
                clarifying_questions=["LLM（LM Studio等）との接続を確認してください。"],
                preventive_tasks=[]
            )

        raw_response = ""
        data = {}
        try:
            raw_response = await llm_service.get_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.2
            )
            cleaned = self._clean_json_string(raw_response)
            data = json.loads(cleaned)
        except Exception as e:
            logger.error(f"Failed to generate WBS from LLM: {str(e)}")
            return get_fallback_response()

        # If data is parsed but nodes list is empty, retry once with temperature 0.3
        nodes_list = data.get("nodes", []) if isinstance(data, dict) else []
        if not nodes_list:
            logger.warning("LLM returned empty WBS nodes list. Retrying with temperature 0.3...")
            try:
                raw_response = await llm_service.get_response(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.3
                )
                cleaned = self._clean_json_string(raw_response)
                data = json.loads(cleaned)
                nodes_list = data.get("nodes", []) if isinstance(data, dict) else []
            except Exception as retry_err:
                logger.error(f"LLM retry failed: {str(retry_err)}")

        # If still empty, return the fallback response
        if not nodes_list:
            logger.error("LLM returned empty nodes list after retry. Returning fallback response.")
            return get_fallback_response()

        # 5. Server-side calculations
        # a) Staffing Recommendations
        staffing_recs = []
        
        # Gather all required skills from task nodes
        skills_to_check = set()
        for node in nodes_list:
            if isinstance(node, dict) and node.get("node_type") == "TASK" and node.get("required_skill"):
                skills_to_check.add(node.get("required_skill"))

        for skill in skills_to_check:
            skill_lower = skill.lower()
            matching_res = []
            for r in assignable_resources:
                has_skill = False
                if any(skill_lower in str(s).lower() for s in r.skills_phase):
                    has_skill = True
                elif any(skill_lower in str(s).lower() for s in r.skills_domain):
                    has_skill = True
                elif r.skills_free and skill_lower in r.skills_free.lower():
                    has_skill = True
                if has_skill:
                    matching_res.append(r)

            if not matching_res:
                staffing_recs.append(StaffingRecommendation(
                    skill=skill,
                    type="NO_HOLDER",
                    detail=f"該当スキル「{skill}」の保持者が0名。要員採用/オンボードを推奨"
                ))
            else:
                # Calculate capacity (daily_working_hours * ratio of working days * allocation limit % * 10 days)
                total_capacity = 0.0
                for r in matching_res:
                    days_ratio = len(r.working_days) / 5.0 if r.working_days else 1.0
                    limit_ratio = r.allocation_limit / 100.0
                    capacity_10d = r.daily_working_hours * days_ratio * limit_ratio * 10
                    total_capacity += capacity_10d

                total_estimated = sum(
                    float(node.get("estimated_hours", 0.0))
                    for node in nodes_list
                    if isinstance(node, dict) and node.get("node_type") == "TASK" and node.get("required_skill") == skill
                )

                if total_estimated > total_capacity:
                    shortage = total_estimated - total_capacity
                    staffing_recs.append(StaffingRecommendation(
                        skill=skill,
                        type="CAPACITY_SHORTAGE",
                        detail=f"保持者の工数が約{int(shortage)}h不足。+1名 または 期間延長を推奨"
                    ))

        # b) Preventive tasks from LLM output (with deduplication by title, and limit to max 3)
        preventive_tasks = []
        seen_titles = set()
        llm_preventive = data.get("preventive_tasks") or []
        for pt in llm_preventive:
            if isinstance(pt, dict):
                title = pt.get("title", "").strip()
                reason = pt.get("reason", "").strip()
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    preventive_tasks.append(PreventiveTask(title=title, reason=reason))
                    if len(preventive_tasks) >= 3:
                        break

        # Map to final schema
        nodes = []
        for i, node in enumerate(nodes_list):
            if not isinstance(node, dict):
                continue
            
            # A) ノード構築のNull耐性・自動採番
            temp_id = (node.get("temp_id") or f"auto_{i}")
            title = (node.get("title") or "未命名タスク")
            description = (node.get("description") or "")
            node_type = (node.get("node_type") or "TASK")
            deliverable = (node.get("deliverable") or "")
            parent_temp_id = node.get("parent_temp_id") or None
            
            suggested = None
            if node.get("suggested_assignee"):
                sa = node["suggested_assignee"]
                if isinstance(sa, dict):
                    sa_name = sa.get("name") or ""
                    sa_rid = sa.get("resource_id")
                    if sa_name or sa_rid:
                        suggested = SuggestedAssignee(
                            resource_id=sa_rid or None,
                            name=sa_name,
                            reason=sa.get("reason") or ""
                        )
            
            deps = node.get("dependencies")
            if not isinstance(deps, list):
                deps = []
            else:
                deps = [str(d) for d in deps if d is not None]
                
            try:
                est_hours = float(node.get("estimated_hours") or 0.0)
            except (ValueError, TypeError):
                est_hours = 0.0
                
            try:
                conf = float(node.get("confidence") or 0.8)
            except (ValueError, TypeError):
                conf = 0.8
                
            try:
                pn = PlanNode(
                    temp_id=temp_id,
                    title=title,
                    description=description,
                    node_type=node_type,
                    parent_temp_id=parent_temp_id,
                    deliverable=deliverable,
                    estimated_hours=est_hours,
                    suggested_assignee=suggested,
                    dependencies=deps,
                    confidence=conf,
                    required_skill=node.get("required_skill")
                )
                nodes.append(pn)
            except Exception as node_err:
                logger.warning(f"Failed to build PlanNode for index {i}: {str(node_err)} - Node: {node}")
                
        # C) parent_temp_id の健全化
        valid_temp_ids = {n.temp_id for n in nodes}
        for n in nodes:
            if n.parent_temp_id and n.parent_temp_id not in valid_temp_ids:
                n.parent_temp_id = None

        if not nodes:
            logger.error("No valid nodes could be created from LLM response. Returning fallback response.")
            return get_fallback_response()

        return AnalyzeResponse(
            summary=data.get("summary", ""),
            nodes=nodes,
            staffing_recommendations=staffing_recs,
            clarifying_questions=data.get("clarifying_questions") or [],
            preventive_tasks=preventive_tasks
        )

    async def apply(self, db: AsyncSession, req: ApplyRequest, background_tasks: Optional[BackgroundTasks] = None) -> Dict[str, Any]:
        """
        Creates or links project, validates assignees are not admins,
        creates WBS tree in parent-first order, maps dependency temp_ids to real database IDs,
        and triggers orchestrator tasks if assigned to AI.
        """
        # 1. Project Creation or Fetching
        if not req.project_id:
            if not req.new_project:
                raise HTTPException(status_code=400, detail="project_id または new_project のどちらかを指定してください。")
            project = Project(
                name=req.new_project.name,
                template_type=req.new_project.template_type,
                organization_id=UUID("00000000-0000-0000-0000-000000000000")
            )
            db.add(project)
            await db.flush()
            project_id = project.id
        else:
            project_id = req.project_id
            project = await db.get(Project, project_id)
            if not project:
                raise HTTPException(status_code=404, detail="プロジェクトが見つかりません。")

        # 2. Assignee validation (check if assignee is an admin/管理者)
        for node in req.nodes:
            if node.assignee_name:
                res_query = await db.execute(
                    select(Resource).where(Resource.name == node.assignee_name)
                )
                resource = res_query.scalar_one_or_none()
                if resource and resource.system_role == "管理者":
                    raise HTTPException(
                        status_code=400,
                        detail="システム管理者はリソースとしてアサインできません"
                    )

        # 3. Create WBS nodes in parent-first order
        temp_id_to_real_id: Dict[str, UUID] = {}
        uncreated_nodes = list(req.nodes)
        
        now = datetime.now(timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0)
        
        loop_limit = len(uncreated_nodes) * 2
        loops = 0
        
        created_tasks: List[tuple] = []
        
        while uncreated_nodes and loops < loop_limit:
            loops += 1
            to_remove = []
            for node in uncreated_nodes:
                parent_id = None
                if node.parent_temp_id:
                    if node.parent_temp_id in temp_id_to_real_id:
                        parent_id = temp_id_to_real_id[node.parent_temp_id]
                    else:
                        # Parent node hasn't been created yet, wait for next loop
                        continue
                
                # Default start/end dates
                p_start = node.planned_start or now
                p_end = node.planned_end or (p_start + timedelta(days=1))
                
                task = Task(
                    title=node.title,
                    description=node.description,
                    status="TODO",
                    priority="MEDIUM",
                    assignee_type=node.assignee_type or "HUMAN",
                    assignee_name=node.assignee_name or "",
                    planned_start=p_start,
                    planned_end=p_end,
                    project_id=project_id,
                    parent_id=parent_id,
                    node_type=node.node_type or "TASK",
                    estimated_hours=node.estimated_hours,
                    actual_hours=0.0
                )
                db.add(task)
                await db.flush()
                
                temp_id_to_real_id[node.temp_id] = task.id
                created_tasks.append((task, node.dependencies))
                to_remove.append(node)
                
            for node in to_remove:
                uncreated_nodes.remove(node)

        # Resolve any remaining cyclical nodes
        for node in uncreated_nodes:
            p_start = node.planned_start or now
            p_end = node.planned_end or (p_start + timedelta(days=1))
            task = Task(
                title=node.title,
                description=node.description,
                status="TODO",
                priority="MEDIUM",
                assignee_type=node.assignee_type or "HUMAN",
                assignee_name=node.assignee_name or "",
                planned_start=p_start,
                planned_end=p_end,
                project_id=project_id,
                parent_id=None,
                node_type=node.node_type or "TASK",
                estimated_hours=node.estimated_hours,
                actual_hours=0.0
            )
            db.add(task)
            await db.flush()
            
            temp_id_to_real_id[node.temp_id] = task.id
            created_tasks.append((task, node.dependencies))

        # 4. Resolve dependencies
        for task, dep_temps in created_tasks:
            if dep_temps:
                for dep_temp in dep_temps:
                    if dep_temp in temp_id_to_real_id:
                        dep_id = temp_id_to_real_id[dep_temp]
                        await db.execute(
                            task_dependency.insert().values(
                                task_id=task.id,
                                depends_on_id=dep_id
                            )
                        )

        await db.commit()

        # 5. Background task orchestrator for AI tasks
        if background_tasks:
            for task, _ in created_tasks:
                if task.assignee_type == "AI":
                    background_tasks.add_task(orchestrator_service.generate_plan_and_subtasks, task.id)

        return {
            "success": True,
            "project_id": project_id,
            "created_count": len(created_tasks)
        }

planning_service = PlanningService()
