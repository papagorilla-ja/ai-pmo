import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import List, Dict, Any
from uuid import UUID

from app.database import get_db
from app.config import settings
from app.models.project import Project
from app.models.task import Task
from app.models.resource import Resource
from app.models.resource_allocation import ResourceAllocation
from app.models.comment import Comment
from app.schemas.project import ProjectResponse
from app.services.portfolio_service import portfolio_service
from app.services.llm import llm_service
from app.services.rag import rag_service
from app.core.deps import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

class AuditRequest(BaseModel):
    task_id: UUID
    content: str

class ShiftRequest(BaseModel):
    delayed_project_id: UUID
    donor_project_id: UUID
    resource_name: str
    shift_percent: int

class LessonSearchRequest(BaseModel):
    title: str
    description: str

@router.get("/portfolio", response_model=List[ProjectResponse])
async def list_portfolio(
    current_user: Resource = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns all projects, tasks and resource allocations in the portfolio.
    """
    result = await db.execute(
        select(Project).options(
            selectinload(Project.allocations),
            selectinload(Project.tasks).selectinload(Task.dependencies),
            selectinload(Project.tasks).selectinload(Task.subtasks),
            selectinload(Project.tasks).selectinload(Task.plan)
        )
    )
    return result.scalars().all()

@router.post("/portfolio/audit-conflict", response_model=List[Dict[str, Any]])
async def audit_portfolio_conflicts(
    current_user: Resource = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Audits for resource bottlenecks and generates AI shifts proposals.
    """
    return await portfolio_service.audit_conflicts(db)

@router.post("/portfolio/apply-allocation-shift")
async def apply_allocation_shift(
    payload: ShiftRequest,
    current_user: Resource = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Applies the resource reallocation shift and backfills with AI.
    """
    # Check if target resource is Admin (which is blocked from assignments)
    res_query = select(Resource).where(Resource.name == payload.resource_name)
    res_result = await db.execute(res_query)
    target_res = res_result.scalars().first()
    if target_res and target_res.system_role == "管理者":
        raise HTTPException(status_code=400, detail="システム管理者はリソースとしてアサインできません。")
        
    success = await portfolio_service.apply_allocation_shift(
        db, 
        str(payload.delayed_project_id), 
        str(payload.donor_project_id), 
        payload.resource_name, 
        payload.shift_percent
    )
    if not success:
        raise HTTPException(status_code=400, detail="Failed to apply resource shift. Allocation not found.")
    return {"success": True, "detail": "Resource allocation shift applied successfully."}

@router.post("/governance/audit-document", response_model=List[Dict[str, Any]])
async def audit_document(
    payload: AuditRequest,
    current_user: Resource = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Audits a project deliverable against governance guidelines in Qdrant,
    generates line-specific audits, and persists them as Comments.
    """
    # 1. Query governance_rules collection (dedicated security/coding standards)
    search_hits = await rag_service.search(
        payload.content[:500],  # 先頭500文字をクエリに使用（長文対策）
        limit=5,
        collection_name=settings.QDRANT_GOVERNANCE_COLLECTION_NAME
    )
    rules_context = ""
    if search_hits:
        rules_context = "\n---\n".join([
            f"[{hit['metadata'].get('severity','?')}] {hit['content']}"
            for hit in search_hits
        ])
    else:
        # Fallback rules if vector search is empty (Qdrant unavailable)
        rules_context = (
            "社内セキュリティ規約 第3条: 個人情報および認証情報は暗号化して保管すること。接続文字列をコード内に平文で記載してはならない。\n"
            "コーディング標準 第5条: 本番環境のデータベースは必ず PostgreSQL 16 以上のコネクションプールを使用すること。接続数制限に配慮せよ。\n"
            "セキュリティ規約 第7条: ユーザー入力は必ずパラメータ化クエリを使用すること。SQLインジェクション対策を徹底すること。"
        )
        
    system_prompt = (
        "You are the Lead PMO Governance Auditor. Your job is to check project specs/code against "
        "organization guidelines and security rules.\n"
        "Audit the provided document. If you find violations or consideration omissions, specify "
        "the EXACT line number (1-indexed) and a warning explanation.\n"
        "You MUST respond ONLY with a raw JSON array of objects. Do not write explanations outside the JSON.\n"
        "Format:\n"
        "[\n"
        "  {\n"
        "    \"line_number\": 7,\n"
        "    \"content\": \"【セキュリティ警告】認証文字列の平文記述を検知しました。環境変数から読み込むように変更してください。\"\n"
        "  }\n"
        "]"
    )
    
    user_prompt = (
        f"Organization Guidelines:\n{rules_context}\n\n"
        f"Document Content to Audit:\n{payload.content}\n\n"
        f"Please audit and return JSON:"
    )
    
    try:
        raw_res = await llm_service.get_response(system_prompt, user_prompt, temperature=0.2)
        # Clean potential markdown wrappers
        cleaned = raw_res.strip()
        start = cleaned.find('[')
        end = cleaned.rfind(']')
        if start != -1 and end != -1:
            cleaned = cleaned[start:end+1]
            
        audit_results = json.loads(cleaned)
        
        # Persist as Comments in the database
        comments_created = []
        for audit in audit_results:
            comment = Comment(
                task_id=payload.task_id,
                line_number=audit.get("line_number"),
                content=f"【ガバナンス警告】{audit.get('content')}",
                author="AI_PMO"
            )
            db.add(comment)
            comments_created.append(audit)
            
        await db.commit()
        return comments_created
        
    except Exception as e:
        logger.error(f"Governance audit failed: {str(e)}")
        # Fallback mock warning if LLM fails
        mock_audit = [{
            "line_number": 7,
            "content": "【ガバナンス警告】ガイドライン監査実行中にエラーが発生しました。接続構成が暗号化されているか確認してください。"
        }]
        comment = Comment(
            task_id=payload.task_id,
            line_number=7,
            content="【ガバナンス警告】ガイドライン監査実行中にエラーが発生しました。接続構成が暗号化されているか確認してください。",
            author="AI_PMO"
        )
        db.add(comment)
        await db.commit()
        return mock_audit

@router.get("/executive-report/summary", response_model=Dict[str, Any])
async def get_executive_summary(
    current_user: Resource = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Assembles portfolio metrics (EVM) and translates technical status into business terms.
    Enhanced: project-level breakdown, detailed delay data, RAG lessons, evidence-driven LLM prompt.
    """
    result = await db.execute(
        select(Project).options(
            selectinload(Project.tasks).selectinload(Task.children)
        )
    )
    projects = result.scalars().all()

    # Fetch resource rates from DB
    res_result = await db.execute(select(Resource))
    resources = res_result.scalars().all()
    resource_rates = {r.name: r.hourly_cost_jpy for r in resources}

    # EVM aggregates (leaf tasks only)
    total_pv = 0.0
    total_ev = 0.0
    total_ac = 0.0

    unmapped_assignees = set()
    delayed_tasks_detail = []
    project_breakdown = []

    for proj in projects:
        proj_pv = 0.0
        proj_ev = 0.0
        proj_ac = 0.0

        for t in proj.tasks:
            if len(t.children) == 0:
                name = t.assignee_name.strip() if t.assignee_name else ""
                if name in resource_rates:
                    rate = resource_rates[name]
                else:
                    rate = 0
                    if name:
                        unmapped_assignees.add(name)
                    else:
                        unmapped_assignees.add("未アサイン")

                task_pv = t.estimated_hours * rate
                task_ev = (t.progress / 100.0) * task_pv
                task_ac = t.actual_hours * rate

                total_pv += task_pv
                total_ev += task_ev
                total_ac += task_ac
                proj_pv += task_pv
                proj_ev += task_ev
                proj_ac += task_ac

            if t.delay_days > 0:
                over_hours = round(t.actual_hours - t.estimated_hours, 1)
                delayed_tasks_detail.append({
                    "project": proj.name,
                    "task": t.title,
                    "delay_days": t.delay_days,
                    "assignee": t.assignee_name or "未アサイン",
                    "progress_pct": t.progress,
                    "estimated_hours": t.estimated_hours,
                    "actual_hours": t.actual_hours,
                    "over_hours": over_hours,
                })

        proj_spi = proj_ev / proj_pv if proj_pv > 0 else 1.0
        proj_cpi = proj_ev / proj_ac if proj_ac > 0 else 1.0
        delayed_in_proj = sum(1 for d in delayed_tasks_detail if d["project"] == proj.name)
        project_breakdown.append({
            "project": proj.name,
            "status": proj.status,
            "pv_jpy": round(proj_pv),
            "ev_jpy": round(proj_ev),
            "ac_jpy": round(proj_ac),
            "spi": round(proj_spi, 2),
            "cpi": round(proj_cpi, 2),
            "delayed_task_count": delayed_in_proj,
        })

    # Portfolio SPI / CPI
    spi = total_ev / total_pv if total_pv > 0 else 1.0
    cpi = total_ev / total_ac if total_ac > 0 else 1.0

    # RAG: lessons_learned で遅延タスク名から過去教訓を検索
    past_lessons_text = ""
    if delayed_tasks_detail:
        delay_query = " ".join([d["task"] for d in delayed_tasks_detail[:3]])
        try:
            lesson_hits = await rag_service.search(
                delay_query,
                limit=3,
                collection_name=settings.QDRANT_LESSONS_COLLECTION_NAME
            )
            if lesson_hits:
                past_lessons_text = "\n".join([
                    f"- 教訓: {hit['content']} → 推奨対策: {hit['metadata'].get('mitigation_task', '不明')}"
                    for hit in lesson_hits
                ])
        except Exception:
            pass

    # LLM に渡す遅延タスク詳細テキスト
    if delayed_tasks_detail:
        delayed_detail_text = "\n".join([
            f"  ・[{d['project']}] {d['task']}: {d['delay_days']}日遅延 / "
            f"担当: {d['assignee']} / 進捗: {d['progress_pct']}% / "
            f"見積: {d['estimated_hours']}h 実績: {d['actual_hours']}h "
            f"({'超過 ' + str(abs(d['over_hours'])) + 'h' if d['over_hours'] > 0 else '余裕あり'})"
            for d in delayed_tasks_detail
        ])
    else:
        delayed_detail_text = "  (現在遅延タスクなし)"

    # LLM に渡すプロジェクト別内訳テキスト
    project_breakdown_text = "\n".join([
        f"  ・{p['project']}: SPI={p['spi']} / CPI={p['cpi']} / "
        f"PV={p['pv_jpy']:,}円 EV={p['ev_jpy']:,}円 AC={p['ac_jpy']:,}円 / "
        f"遅延タスク数: {p['delayed_task_count']}"
        for p in project_breakdown
    ])

    system_prompt = (
        "You are the Chief PMO Officer reporting directly to the Board of Directors and CFO.\n"
        "Translate technical issues (Git errors, database configs, minor bugs) into high-level business impacts "
        "concerning cost, delivery, ROI timing, and DX benefits release.\n"
        "Write a concise, professional report in Japanese.\n"
        "CRITICAL REQUIREMENT: Every claim MUST be backed by specific numbers from the data provided. "
        "Always cite actual figures (SPI, CPI, JPY amounts, hours, delay days, task names). "
        "Never make vague statements — if you cannot cite a number, do not make the claim.\n"
        "Structure:\n"
        "1. 【総合ステータス評価】(SPI/CPIと円換算PV/EV/ACを引用して総評)\n"
        "2. 【納期・DX効果発現への影響】(具体的な遅延日数・タスク名・担当者を引用)\n"
        "3. 【コストおよびリソース効率】(AC vs EV 差額・超過工数・プロジェクト別CPIを引用)\n"
        "4. 【過去事例との比較と教訓】(過去教訓が提供された場合は必ず言及)\n"
        "5. 【PMO推奨アクション】(数値根拠に基づく具体的かつ実行可能な推奨アクション)"
    )

    ev_pv_diff = round(total_ev - total_pv)
    ac_ev_diff = round(total_ac - total_ev)
    user_prompt = (
        f"=== ポートフォリオEVM指標 ===\n"
        f"- SPI (スケジュール効率指数): {spi:.2f}\n"
        f"- CPI (コスト効率指数): {cpi:.2f}\n"
        f"- PV (計画価値合計): {round(total_pv):,}円\n"
        f"- EV (出来高合計): {round(total_ev):,}円\n"
        f"- AC (実績コスト合計): {round(total_ac):,}円\n"
        f"- EV-PV差異: {ev_pv_diff:,}円 ({'スケジュール遅れ' if ev_pv_diff < 0 else 'スケジュール前倒し'})\n"
        f"- AC-EV差異: {ac_ev_diff:,}円 ({'コスト超過' if ac_ev_diff > 0 else 'コスト節約'})\n\n"
        f"=== プロジェクト別内訳 ===\n{project_breakdown_text}\n\n"
        f"=== 遅延タスク詳細 ===\n{delayed_detail_text}\n\n"
        + (f"=== 過去の類似トラブル教訓 ===\n{past_lessons_text}\n\n" if past_lessons_text else "")
        + "上記データの数値を必ず引用しながら経営報告書を作成してください:"
    )

    try:
        report_text = await llm_service.get_response(system_prompt, user_prompt, temperature=0.4)
    except Exception as e:
        logger.error(f"Executive summary LLM failed: {str(e)}")
        report_text = (
            f"【総合ステータス評価】ポートフォリオ全体のSPI={spi:.2f}、CPI={cpi:.2f}。"
            f"計画価値(PV){round(total_pv):,}円に対し出来高(EV){round(total_ev):,}円（差異:{ev_pv_diff:,}円）。\n"
            f"【納期・DX効果発現への影響】遅延タスク{len(delayed_tasks_detail)}件を確認。"
            f"DX成果発現タイミングへの影響リスクが生じています。\n"
            f"【コストおよびリソース効率】実績コスト(AC){round(total_ac):,}円 vs 出来高(EV){round(total_ev):,}円"
            f"（{'コスト超過' if ac_ev_diff > 0 else 'コスト節約'} {abs(ac_ev_diff):,}円）。\n"
            f"【過去事例との比較と教訓】過去教訓DBとの照合を推奨します。\n"
            f"【PMO推奨アクション】遅延プロジェクトへの優先リソース再配分と週次EVM進捗レビューの実施を推奨します。"
        )

    return {
        "spi": round(spi, 2),
        "cpi": round(cpi, 2),
        "cpi_status": "UNDER_BUDGET" if cpi >= 1.0 else "OVER_RUN",
        "spi_status": "ON_SCHEDULE" if spi >= 1.0 else "DELAY",
        "total_pv_jpy": round(total_pv),
        "total_ev_jpy": round(total_ev),
        "total_ac_jpy": round(total_ac),
        "project_breakdown": project_breakdown,
        "delayed_tasks": delayed_tasks_detail,
        "summary_report": report_text,
        "unmapped_assignees": list(unmapped_assignees)
    }


@router.post("/lessons/search-lesson", response_model=List[Dict[str, Any]])
async def search_lessons(
    payload: LessonSearchRequest,
    current_user: Resource = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Searches Qdrant for lessons learned and returns preventive WBS subtask proposals.
    """
    lessons = []

    # Search dedicated lessons_learned collection
    search_hits = await rag_service.search(
        f"{payload.title} {payload.description}",
        limit=3,
        collection_name=settings.QDRANT_LESSONS_COLLECTION_NAME
    )
    for hit in search_hits:
        mitigation = hit["metadata"].get("mitigation_task", "類似トラブルの事前確認と対策立案")
        lessons.append({
            "title": hit["metadata"].get("title", "過去のトラブル事例"),
            "content": hit["content"],
            "mitigation_task": mitigation
        })

    return lessons
