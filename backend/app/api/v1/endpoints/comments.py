from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import List, Optional

from app.database import get_db
from app.models.comment import Comment
from app.schemas.comment import CommentResponse, CommentCreate

router = APIRouter()

@router.post("/", response_model=CommentResponse)
async def create_comment(comment_in: CommentCreate, db: AsyncSession = Depends(get_db)):
    comment = Comment(
        task_id=comment_in.task_id,
        line_number=comment_in.line_number,
        content=comment_in.content,
        author=comment_in.author
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment

@router.get("/", response_model=List[CommentResponse])
async def list_comments(task_id: Optional[UUID] = None, db: AsyncSession = Depends(get_db)):
    query = select(Comment)
    if task_id:
        query = query.where(Comment.task_id == task_id)
    query = query.order_by(Comment.created_at.asc())
    
    result = await db.execute(query)
    return result.scalars().all()
