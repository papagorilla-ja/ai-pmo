from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import List, Optional

from app.database import get_db
from app.models.message import Message
from app.schemas.message import MessageResponse, MessageCreate

router = APIRouter()

@router.post("/", response_model=MessageResponse)
async def create_message(msg_in: MessageCreate, db: AsyncSession = Depends(get_db)):
    msg = Message(
        sender_type=msg_in.sender_type,
        sender_name=msg_in.sender_name,
        content=msg_in.content,
        task_id=msg_in.task_id
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg

@router.get("/", response_model=List[MessageResponse])
async def list_messages(task_id: Optional[UUID] = None, db: AsyncSession = Depends(get_db)):
    query = select(Message)
    if task_id:
        query = query.where(Message.task_id == task_id)
    query = query.order_by(Message.created_at.asc())
    
    result = await db.execute(query)
    return result.scalars().all()
