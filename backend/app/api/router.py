from fastapi import APIRouter, Depends
from app.api.v1.endpoints import tasks, standup, plan_b, messages, comments, knowledge, command, pmo, calendar, resources, auth, projects, planning
from app.api.v1.endpoints import gitea, gitea_webhook
from app.core.deps import get_current_user

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"], dependencies=[Depends(get_current_user)])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"], dependencies=[Depends(get_current_user)])
api_router.include_router(standup.router, prefix="/standup", tags=["standup"], dependencies=[Depends(get_current_user)])
api_router.include_router(plan_b.router, prefix="/plan-b", tags=["plan-b"], dependencies=[Depends(get_current_user)])
api_router.include_router(messages.router, prefix="/messages", tags=["messages"], dependencies=[Depends(get_current_user)])
api_router.include_router(comments.router, prefix="/comments", tags=["comments"], dependencies=[Depends(get_current_user)])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"], dependencies=[Depends(get_current_user)])
api_router.include_router(command.router, prefix="/command", tags=["command"], dependencies=[Depends(get_current_user)])
api_router.include_router(pmo.router, prefix="/pmo", tags=["pmo"], dependencies=[Depends(get_current_user)])
api_router.include_router(calendar.router, prefix="/calendar", tags=["calendar"], dependencies=[Depends(get_current_user)])
api_router.include_router(resources.router, prefix="/resources", tags=["resources"], dependencies=[Depends(get_current_user)])
api_router.include_router(planning.router, prefix="/planning", tags=["planning"], dependencies=[Depends(get_current_user)])

# Gitea webhook（認証なし・HMAC署名検証）
api_router.include_router(gitea_webhook.router, tags=["gitea-webhook"])
# Gitea その他（JWT認証必須）
api_router.include_router(gitea.router, prefix="/gitea", tags=["gitea"], dependencies=[Depends(get_current_user)])


