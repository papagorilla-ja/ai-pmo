from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.models.resource import Resource
from app.core.security import verify_password, create_access_token
from app.core.deps import get_current_user
from app.schemas.resource import ResourceResponse

router = APIRouter()

class LoginRequest(BaseModel):
    email: str
    password: str

class UserInfo(BaseModel):
    id: str
    name: str
    email: str
    system_role: str
    role: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserInfo

@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    # Search user by email
    query = select(Resource).where(Resource.email == payload.email)
    result = await db.execute(query)
    user = result.scalars().first()
    
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="メールアドレスまたはパスワードが正しくありません。"
        )
        
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="このアカウントは無効化されています。"
        )
        
    # Generate access token
    access_token = create_access_token(subject=str(user.id), system_role=user.system_role)
    
    # Update last login timestamp
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "system_role": user.system_role,
            "role": user.role
        }
    }

@router.get("/me", response_model=UserInfo)
async def get_me(current_user: Resource = Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "name": current_user.name,
        "email": current_user.email,
        "system_role": current_user.system_role,
        "role": current_user.role
    }
