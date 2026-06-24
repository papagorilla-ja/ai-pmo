from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.task import Task
from app.services.gitea_service import gitea_service

router = APIRouter()

@router.get("/repos")
async def list_gitea_repos():
    return await gitea_service.list_repos()

class CrawlRequest(BaseModel):
    repo: str  # "{owner}/{repo}"

@router.post("/crawl")
async def crawl_repo(payload: CrawlRequest, db: AsyncSession = Depends(get_db)):
    return await gitea_service.crawl_repository(payload.repo, db)

class GiteaLinkRequest(BaseModel):
    gitea_repo: Optional[str] = None
    gitea_issue_number: Optional[int] = None

@router.patch("/{task_id}/gitea-link")
async def link_task_gitea(
    task_id: UUID,
    payload: GiteaLinkRequest,
    db: AsyncSession = Depends(get_db)
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.gitea_repo = payload.gitea_repo
    task.gitea_issue_number = payload.gitea_issue_number
    await db.commit()
    return {
        "success": True,
        "task_id": str(task.id),
        "gitea_repo": task.gitea_repo,
        "gitea_issue_number": task.gitea_issue_number
    }
