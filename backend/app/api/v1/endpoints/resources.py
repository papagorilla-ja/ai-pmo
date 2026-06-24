import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.resource import Resource
from app.schemas.resource import ResourceCreate, ResourceUpdate, ResourceResponse
from app.services.llm import llm_service
from app.core.deps import get_current_user
from app.core.security import hash_password

logger = logging.getLogger(__name__)
router = APIRouter()

def is_assignable(resource: Resource) -> bool:
    """
    Checks if a resource is assignable to tasks (non-admins and active).
    """
    return resource.system_role != "管理者" and resource.is_active

def mask_resource_cost(resource: Resource, current_user_role: str) -> ResourceResponse:
    """
    Masks the hourly cost of a resource if the current user is a Member.
    """
    res_schema = ResourceResponse.model_validate(resource)
    if current_user_role not in ["管理者", "マネージャ"]:
        res_schema.hourly_cost_jpy = 0
    return res_schema

@router.get("/", response_model=List[ResourceResponse])
async def get_resources(
    current_user: Resource = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Resource).order_by(Resource.created_at))
    resources = result.scalars().all()
    return [mask_resource_cost(r, current_user.system_role) for r in resources]

@router.get("/search")
async def search_resources_nlp(
    query: str,
    current_user: Resource = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not query:
        raise HTTPException(status_code=400, detail="検索クエリが空です。")
        
    # Fetch all resources
    result = await db.execute(select(Resource))
    all_resources = result.scalars().all()
    
    # Filter only assignable resources (admins are excluded from search input/results)
    resources = [r for r in all_resources if is_assignable(r)]
    
    if not resources:
        return []
        
    # Serialize resources list for LLM context
    serialized_resources = []
    for r in resources:
        serialized_resources.append({
            "id": str(r.id),
            "name": r.name,
            "role": r.role,
            "system_role": r.system_role,
            "skills_phase": r.skills_phase,
            "skills_domain": r.skills_domain,
            "skills_free": r.skills_free,
            "department": r.department
        })
        
    system_prompt = (
        "You are an expert resource allocation AI. Based on the user's natural language request, "
        "find the most relevant team members from the provided list of candidates. "
        "For each match, return a JSON object with 'id' (matching candidate ID) and "
        "'reason' (a concise 1-2 sentence explanation in Japanese stating why this person is suitable based on their role and skills). "
        "Return ONLY a raw JSON array of these objects. Do not include conversational text or markdown blocks."
    )
    user_prompt = (
        f"Search query: {query}\n\n"
        f"Available resource candidates:\n"
        f"{json.dumps(serialized_resources, ensure_ascii=False)}"
    )
    
    try:
        response_text = await llm_service.get_response(system_prompt, user_prompt, temperature=0.2)
        cleaned_text = response_text.strip()
        if cleaned_text.startswith("```"):
            lines = cleaned_text.split("\n")
            if lines[0].startswith("```json") or lines[0].startswith("```"):
                lines = lines[1:-1]
            cleaned_text = "\n".join(lines).strip()
            
        matches = json.loads(cleaned_text)
        if not isinstance(matches, list):
            raise ValueError("Expected list output from LLM")
            
        # Create a mapping of id -> reason
        match_map = {m.get("id"): m.get("reason") for m in matches if m.get("id")}
        
        # Load matched resources from DB and attach reasons
        matched_resources = []
        for r in resources:
            r_id_str = str(r.id)
            if r_id_str in match_map:
                res_schema = mask_resource_cost(r, current_user.system_role)
                res_dict = res_schema.model_dump()
                res_dict["matching_reason"] = match_map[r_id_str]
                matched_resources.append(res_dict)
                
        return matched_resources
        
    except Exception as e:
        logger.error(f"Failed to search resources semantically: {str(e)}")
        # Fallback to simple title/skills matching if LLM fails
        logger.info("Falling back to manual keyword matching for resource search...")
        matched_resources = []
        query_lower = query.lower()
        for r in resources:
            skills_concat = (r.role + " " + r.skills_free + " " + " ".join(r.skills_phase) + " " + " ".join(r.skills_domain)).lower()
            if any(word in skills_concat for word in query_lower.split()):
                res_schema = mask_resource_cost(r, current_user.system_role)
                res_dict = res_schema.model_dump()
                res_dict["matching_reason"] = "キーワード一致による自動選定"
                matched_resources.append(res_dict)
        return matched_resources

@router.get("/{resource_id}", response_model=ResourceResponse)
async def get_resource(
    resource_id: str,
    current_user: Resource = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Resource).where(Resource.id == resource_id))
    resource = result.scalars().first()
    if not resource:
        raise HTTPException(status_code=404, detail="リソースが見つかりません。")
    return mask_resource_cost(resource, current_user.system_role)

@router.post("/", response_model=ResourceResponse, status_code=status.HTTP_201_CREATED)
async def create_resource(
    resource_in: ResourceCreate,
    current_user: Resource = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Only Administrators can create new resources
    if current_user.system_role != "管理者":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="リソースマスタの登録権限がありません。(管理者権限が必要です)"
        )
        
    existing = await db.execute(select(Resource).where(Resource.name == resource_in.name))
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="同名のメンバーが既に登録されています。"
        )
        
    # Exclude password, hash it and store
    plain_password = resource_in.password or "password"
    db_resource = Resource(**resource_in.model_dump(exclude={"password"}))
    db_resource.password_hash = hash_password(plain_password)
    
    db.add(db_resource)
    await db.commit()
    await db.refresh(db_resource)
    return db_resource

@router.put("/{resource_id}", response_model=ResourceResponse)
async def update_resource(
    resource_id: str,
    resource_in: ResourceUpdate,
    current_user: Resource = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Resource).where(Resource.id == resource_id))
    db_resource = result.scalars().first()
    if not db_resource:
        raise HTTPException(status_code=404, detail="リソースが見つかりません。")
        
    role = current_user.system_role
    is_self = str(current_user.id) == resource_id
    
    # 1. Member constraints
    if role == "メンバー" and not is_self:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="他のユーザーの情報を更新する権限がありません。"
        )
    if role == "メンバー" and is_self:
        # Members can only update their own password
        if not resource_in.password:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="メンバーは自身のパスワードのみ変更可能です。"
            )
        db_resource.password_hash = hash_password(resource_in.password)
        await db.commit()
        await db.refresh(db_resource)
        return mask_resource_cost(db_resource, role)
        
    # 2. Manager and Admin role checks
    if role not in ["管理者", "マネージャ"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="リソースマスタの更新権限がありません。"
        )
        
    update_data = resource_in.model_dump(exclude_unset=True)
    
    # Manager restrictions: cannot change system_role, is_active, or passwords of other users
    if role == "マネージャ":
        if "system_role" in update_data:
            del update_data["system_role"]
        if "is_active" in update_data:
            del update_data["is_active"]
        if "password" in update_data and not is_self:
            del update_data["password"]
            
    # Handle password hashing (allowed for self, or Admin on others)
    if "password" in update_data:
        if not is_self and role != "管理者":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="他人のパスワードを設定する権限がありません。(管理者権限が必要です)"
            )
        if update_data["password"]:
            db_resource.password_hash = hash_password(update_data["password"])
        del update_data["password"]
        
    for key, val in update_data.items():
        setattr(db_resource, key, val)
        
    await db.commit()
    await db.refresh(db_resource)
    return mask_resource_cost(db_resource, role)

@router.delete("/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resource(
    resource_id: str,
    current_user: Resource = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.system_role != "管理者":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="リソースマスタの削除権限がありません。(管理者権限が必要です)"
        )
        
    result = await db.execute(select(Resource).where(Resource.id == resource_id))
    db_resource = result.scalars().first()
    if not db_resource:
        raise HTTPException(status_code=404, detail="リソースが見つかりません。")
        
    await db.delete(db_resource)
    await db.commit()
    return None
