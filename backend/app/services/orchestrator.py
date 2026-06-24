import json
import logging
from typing import Dict, Any, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.llm import llm_service
from app.models.task import Task
from app.models.plan import Plan
from app.models.subtask import SubTask
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

class OrchestratorService:
    async def generate_plan_and_subtasks(self, task_id: UUID) -> Dict[str, Any]:
        """
        Uses LM Studio to analyze a WBS task, formulate a plan, and split it into microtasks.
        """
        system_prompt = (
            "You are the Lead Project Orchestrator Agent. Your task is to analyze a project task and "
            "decompose it into a series of actionable, isolated microtasks (1-2 hours each) that an AI Worker Agent can execute.\n"
            "You MUST respond ONLY with a raw JSON object. Do not write any greetings or explanations outside the JSON.\n"
            "Format:\n"
            "{\n"
            "  \"approach_summary\": \"Detailed technical plan and approach for this task...\",\n"
            "  \"subtasks\": [\n"
            "    {\n"
            "      \"title\": \"Microtask Title\",\n"
            "      \"description\": \"Detailed description of what the worker must achieve.\"\n"
            "    }\n"
            "  ]\n"
            "}"
        )
        
        async with AsyncSessionLocal() as db:
            task = await db.get(Task, task_id)
            if not task:
                logger.error(f"Task with ID {task_id} not found for WBS plan generation")
                return {"error": f"Task {task_id} not found"}

            user_prompt = (
                f"Please decompose the following task:\n"
                f"Title: {task.title}\n"
                f"Description: {task.description}\n"
                f"Priority: {task.priority}\n"
                f"Target Timeline: {task.planned_start} to {task.planned_end}"
            )
            
            logger.info(f"Generating plan for Task: {task.id} - {task.title}")
            try:
                raw_response = await llm_service.get_response(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.2  # Low temperature for deterministic JSON output
                )
                
                # Clean response from potential markdown code blocks
                cleaned = self._clean_json_string(raw_response)
                data = json.loads(cleaned)
                
                approach_summary = data.get("approach_summary", f"Approach for executing: {task.title}")
                subtasks_data = data.get("subtasks", [])
                
                # Save Plan to Database
                plan = Plan(
                    task_id=task.id,
                    approach_summary=approach_summary,
                    status="DRAFT"
                )
                db.add(plan)
                
                # Save SubTasks to Database (Pending approval)
                created_subtasks = []
                for sub_data in subtasks_data:
                    subtask = SubTask(
                        task_id=task.id,
                        title=sub_data.get("title", "Untitled Subtask"),
                        description=sub_data.get("description", ""),
                        status="PENDING",
                        agent_id="AI_WORKER"
                    )
                    db.add(subtask)
                    created_subtasks.append(subtask)
                    
                await db.commit()
                
                return {
                    "approach_summary": approach_summary,
                    "subtasks_count": len(created_subtasks)
                }
                
            except Exception as e:
                logger.error(f"Orchestrator plan generation failed: {str(e)}")
                # Fallback draft if LLM fails or is disconnected
                approach_summary = (
                    f"【自動作成】LM Studio からプランを生成できませんでした。手動で構成してください。\n"
                    f"エラー詳細: {str(e)}"
                )
                plan = Plan(
                    task_id=task.id,
                    approach_summary=approach_summary,
                    status="DRAFT"
                )
                db.add(plan)
                
                # Fallback subtasks
                fallback_subtask = SubTask(
                    task_id=task.id,
                    title="タスク初期調査と設計方針の確定",
                    description="LM Studioへの接続に失敗したため、初期調査タスクを生成しました。LLM の接続設定を確認してください。",
                    status="PENDING",
                    agent_id="AI_WORKER"
                )
                db.add(fallback_subtask)
                await db.commit()
                
                return {
                    "approach_summary": approach_summary,
                    "subtasks_count": 1,
                    "error": str(e)
                }

    def _clean_json_string(self, text: str) -> str:
        text = text.strip()
        # Find first '{' and last '}'
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            return text[start:end+1]
        return text

orchestrator_service = OrchestratorService()
