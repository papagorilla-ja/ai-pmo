from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import uuid, re
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from sqlalchemy import select

from app.database import get_db
from app.models.task import Task
from app.models.message import Message
from app.services.llm import llm_service
from app.services.rag import rag_service
from app.services.risk_engine import risk_engine_service
from app.services.gitea_service import gitea_service

router = APIRouter()

class CommandRequest(BaseModel):
    command: str
    screen_context: Optional[Dict[str, Any]] = None

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
    if "ヒアリング" in cmd_text or "hearing" in cmd_text:
        ctx = payload.screen_context or {}
        ctx_task_id = ctx.get("task_id")
        ctx_project_id = ctx.get("project_id")

        target_task = None

        # Priority 1: use task_id from screen context (user had a task selected)
        if ctx_task_id:
            try:
                res = await db.execute(select(Task).where(Task.id == uuid.UUID(ctx_task_id)))
                target_task = res.scalars().first()
            except Exception:
                pass

        # Priority 2: search by name mention in command text, filtered by project if available
        if not target_task:
            query = select(Task)
            if ctx_project_id:
                try:
                    query = query.where(Task.project_id == uuid.UUID(ctx_project_id))
                except Exception:
                    pass
            result = await db.execute(query)
            tasks = result.scalars().all()
            for t in tasks:
                if str(t.id) in cmd_text or t.title in cmd_text:
                    target_task = t
                    break
            # Fallback: first TODO/IN_PROGRESS task in project scope
            if not target_task and tasks:
                target_task = next(
                    (t for t in tasks if t.status in ("TODO", "IN_PROGRESS")),
                    tasks[0]
                )

        if target_task:
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
            
    # 2-A. Gitea Repository Crawl Command
    if "giteaクロール" in cmd_text.lower() or "gitea crawl" in cmd_text.lower():
        # リポジトリ名が含まれていれば即クロール: "owner/repo" パターンで検出
        repo_match = re.search(r'([a-zA-Z0-9_\-\.]+/[a-zA-Z0-9_\-\.]+)', cmd_text)
        if repo_match:
            repo = repo_match.group(1)
            result = await gitea_service.crawl_repository(repo, db)
            crawled = result.get("crawled", 0)
            return {
                "success": True,
                "action": "GITEA_CRAWL",
                "message": f"リポジトリ「{repo}」のクロール完了: {crawled}件のドキュメントをナレッジベースに登録しました。"
            }
        else:
            # リポジトリ名なし → 一覧を返してフロントに選択させる
            repos_data = await gitea_service.list_repos()
            repos = repos_data.get("repos", [])
            if not repos:
                return {
                    "success": False,
                    "action": "GITEA_CRAWL",
                    "message": "Giteaに接続できないか、リポジトリが存在しません。GITEA_ADMIN_TOKENの設定を確認してください。"
                }
            return {
                "success": True,
                "action": "SELECT_REPO",
                "repos": repos,
                "message": "クロールするリポジトリを選択してください:"
            }

    # 2. Nightly Crawl Command (internal tasks & messages)
    if "crawl" in cmd_text.lower() or "クロール" in cmd_text:
        crawl_results = await rag_service.run_nightly_crawl(db)
        tasks_count = crawl_results.get("crawled_tasks_count", 0)
        msg_count = crawl_results.get("crawled_messages_count", 0)
        chunks = crawl_results.get("indexed_chunks_count", 0)
        return {
            "success": True,
            "action": "NIGHTLY_CRAWL",
            "message": f"内部クロール完了: タスク{tasks_count}件・メッセージ{msg_count}件、計{chunks}チャンクをナレッジベースに登録しました。",
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
        
    # Build screen context string for LLM
    screen_ctx_parts = []
    if payload.screen_context:
        ctx = payload.screen_context
        label = ctx.get("screen_label") or ctx.get("screen") or "不明"
        screen_ctx_parts.append(f"現在の画面: {label}")
        if ctx.get("project_name"):
            screen_ctx_parts.append(f"参照中プロジェクト: {ctx['project_name']}")
        if ctx.get("task_title"):
            screen_ctx_parts.append(f"選択中タスク: {ctx['task_title']}")
    screen_ctx_text = " / ".join(screen_ctx_parts)

    system_prompt = (
        "You are the AI-PMO Project Management Advisor. You have access to the project knowledge base "
        "indexed via semantic search.\n"
        + (f"User's current screen context — {screen_ctx_text}\n" if screen_ctx_text else "")
        + "Use the screen context to give a focused, relevant answer about what the user is currently looking at.\n"
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
