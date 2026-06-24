from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any

from app.database import get_db
from app.core.deps import get_current_user
from app.models.resource import Resource
from app.schemas.planning import AnalyzeRequest, AnalyzeResponse, ApplyRequest
from app.services.planning_service import planning_service

router = APIRouter()

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_plan(
    req: AnalyzeRequest,
    current_user: Resource = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Analyzes raw text to extract a proposed WBS structure, recommending matching resources,
    clarifying questions, and preventive tasks.
    """
    return await planning_service.analyze(db, req)

@router.post("/apply")
async def apply_plan(
    req: ApplyRequest,
    background_tasks: BackgroundTasks,
    current_user: Resource = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Creates project structure and tasks based on staging nodes.
    """
    return await planning_service.apply(db, req, background_tasks)
