import json, logging
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.gitea_service import gitea_service

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/webhooks/gitea")
async def receive_gitea_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    body = await request.body()
    signature = request.headers.get("X-Gitea-Signature", "")
    event = request.headers.get("X-Gitea-Event", "")

    if not gitea_service.verify_signature(body, signature):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    background_tasks.add_task(gitea_service.handle_webhook, event, payload, db)
    return {"received": True}
