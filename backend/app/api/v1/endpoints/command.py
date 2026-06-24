from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Dict, Any, List
from sqlalchemy import select

from app.database import get_db
from app.models.task import Task
from app.models.message import Message
from app.services.llm import llm_service
from app.services.rag import rag_service
from app.services.risk_engine import risk_engine_service

router = APIRouter()

class CommandRequest(BaseModel):
    command: str

@router.post("/execute", response_model=Dict[str, Any])
async def execute_command(payload: CommandRequest, db: AsyncSession = Depends(get_db)):
    """
    Executes a command from the Cmd+K palette.
    Matches commands:
    1. Hearing triggers: '@AI hearing <task_id>' or '@AI #<id> ヒアリング'
    2. Crawler triggers: '@AI crawl' or '@AI クロール'
    3. RAG/General chat: Ask anything, search vector DB, and answer using LM Studio.
    """
    cmd_text = payload.command.strip()
    
    # 1. Trigger Hearing Command
    # Let's check if there's a task title or ID or general task mention
    if "ヒアリング" in cmd_text or "hearing" in cmd_text:
        # Try to find a task mentioned
        result = await db.execute(select(Task))
        tasks = result.scalars().all()
        target_task = None
        for t in tasks:
            # Match by UUID or title substring
            if str(t.id) in cmd_text or t.title in cmd_text:
                target_task = t
                break
        if not target_task and tasks:
            # Fallback to the first task that is TODO or IN_PROGRESS
            target_task = tasks[0]
            
        if target_task:
            # Create AI hearing message
            ai_msg = Message(
                sender_type="AI_PMO",
                sender_name="AI_PMO",
                content=(
                    f"【アラートヒアリング】タスク「{target_task.title}」についてヒアリングを開始します。\n"
                    f"現在、予定期間から進捗遅れが懸念されています。完了までの『リアルな残工数（例: あと3時間、1.5人日）』をお答えください。"
                ),
                task_id=target_task.id
            )
            db.add(ai_msg)
            await db.commit()
            return {
                "success": True,
                "action": "TRIGGER_HEARING",
                "target_task_id": str(target_task.id),
                "message": f"タスク「{target_task.title}」への残工数ヒアリングを開始しました。"
            }
            
    # 2. Nightly Crawl Command
    if "crawl" in cmd_text.lower() or "クロール" in cmd_text:
        crawl_results = await rag_service.run_nightly_crawl(db)
        return {
            "success": True,
            "action": "NIGHTLY_CRAWL",
            "message": "夜間クローリングバッチを手動起動し、ベクトルDBを同期しました。",
            "details": crawl_results
        }
        
    # 3. Apply Plan B Command
    if "apply plan b" in cmd_text.lower() or "プランb適用" in cmd_text:
        # Apply Plan B dates
        applied = await risk_engine_service.apply_plan_b_schedule(db)
        return {
            "success": True,
            "action": "APPLY_PLAN_B",
            "message": f"プランBスケジュールを適用しました（調整タスク数: {applied} 件）。"
        }

    # 4. Fallback: RAG + LLM Query
    # Search Qdrant for context
    rag_context = ""
    search_hits = await rag_service.search(cmd_text, limit=3)
    if search_hits:
        context_chunks = [hit["content"] for hit in search_hits]
        rag_context = "\n---\n".join(context_chunks)
        
    system_prompt = (
        "You are the AI-PMO Project Management Advisor. You have access to the project knowledge base "
        "indexed via semantic search.\n"
        "Please answer the user's query clearly and concisely using the provided context if relevant.\n"
        "Answer in Japanese."
    )
    
    user_prompt = (
        f"Context from project records:\n{rag_context}\n\n"
        f"User Query: {cmd_text}\n"
        f"Answer:"
    )
    
    try:
        response_text = await llm_service.get_response(system_prompt, user_prompt, temperature=0.5)
        # Register the transaction in general messages
        user_msg = Message(sender_type="USER", sender_name="User", content=cmd_text)
        ai_msg = Message(sender_type="AI_PMO", sender_name="AI_PMO", content=response_text)
        db.add(user_msg)
        db.add(ai_msg)
        await db.commit()
        
        return {
            "success": True,
            "action": "LLM_QUERY",
            "message": response_text
        }
    except Exception as e:
        return {
            "success": False,
            "action": "LLM_QUERY",
            "message": f"AI応答の生成中にエラーが発生しました: {str(e)}"
        }
