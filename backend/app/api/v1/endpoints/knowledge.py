from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import List, Dict, Any

from app.database import get_db
from app.models.knowledge import Knowledge
from app.schemas.knowledge import KnowledgeResponse, KnowledgeUpdate
from app.services.rag import rag_service

router = APIRouter()

@router.get("/", response_model=List[KnowledgeResponse])
async def list_knowledge(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Knowledge).order_by(Knowledge.created_at.desc()))
    return result.scalars().all()

@router.put("/{knowledge_id}", response_model=KnowledgeResponse)
async def update_knowledge(knowledge_id: UUID, payload: KnowledgeUpdate, db: AsyncSession = Depends(get_db)):
    knowledge = await db.get(Knowledge, knowledge_id)
    if not knowledge:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
        
    obj_data = payload.model_dump(exclude_unset=True)
    for field in obj_data:
        setattr(knowledge, field, obj_data[field])
        
    await db.commit()
    await db.refresh(knowledge)
    return knowledge

@router.delete("/{knowledge_id}", response_model=Dict[str, Any])
async def delete_knowledge(knowledge_id: UUID, db: AsyncSession = Depends(get_db)):
    knowledge = await db.get(Knowledge, knowledge_id)
    if not knowledge:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
        
    # 1. Delete from Qdrant if qdrant_id is set
    if knowledge.qdrant_id:
        await rag_service.delete_document(knowledge.qdrant_id)
        
    # 2. Delete from Postgres
    await db.delete(knowledge)
    await db.commit()
    
    return {"success": True, "detail": f"Knowledge entry {knowledge_id} successfully deleted from databases."}

@router.post("/nightly-crawl", response_model=Dict[str, Any])
async def trigger_nightly_crawl(db: AsyncSession = Depends(get_db)):
    """
    Manually triggers the Nightly Crawling Batch simulation.
    """
    results = await rag_service.run_nightly_crawl(db)
    return {
        "success": True,
        "detail": "Nightly vector database synchronization finished.",
        "results": results
    }
