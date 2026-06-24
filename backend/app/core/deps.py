import jwt
from fastapi import Depends, HTTPException, Header, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from app.database import get_db
from app.models.resource import Resource
from app.core.security import decode_access_token

async def get_current_user(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
) -> Resource:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証情報が不足しているか、無効です。",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = authorization.split(" ")[1]
    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="無効なトークンです。",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="トークンの検証に失敗したか、期限切れです。",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # Load user from DB
    try:
        # Try parsing as UUID
        uuid_val = UUID(user_id)
        query = select(Resource).where(Resource.id == uuid_val)
    except ValueError:
        # Fallback to email or name
        query = select(Resource).where((Resource.email == user_id) | (Resource.name == user_id))
        
    result = await db.execute(query)
    user = result.scalars().first()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ユーザーが存在しません。",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="このアカウントは無効化されています。",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

def require_roles(*roles: str):
    def role_dependency(current_user: Resource = Depends(get_current_user)):
        if current_user.system_role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="この操作を実行する権限がありません。"
            )
        return current_user
    return role_dependency
