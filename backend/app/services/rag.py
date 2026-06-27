import uuid
import logging
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from app.config import settings

logger = logging.getLogger(__name__)

class RAGService:
    def __init__(self):
        self.client = None
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self.init_qdrant()

    def init_qdrant(self):
        try:
            self.client = QdrantClient(url=settings.QDRANT_URL)
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant: {str(e)}. RAG queries will run in mocked mode.")
            self.client = None

    async def add_documents(self, documents: List[str], metadatas: List[Dict[str, Any]], ids: Optional[List[str]] = None, collection_name: Optional[str] = None) -> List[str]:
        if not self.client:
            logger.warning("Qdrant client not initialized. Skipping document indexing.")
            return []

        col = collection_name or self.collection_name
        doc_ids = ids if ids else [str(uuid.uuid4()) for _ in documents]
        try:
            self.client.add(
                collection_name=col,
                documents=documents,
                metadata=metadatas,
                ids=doc_ids
            )
            return doc_ids
        except Exception as e:
            logger.error(f"Error adding documents to Qdrant ({col}): {str(e)}")
            return []

    async def search(self, query: str, limit: int = 5, collection_name: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self.client:
            logger.warning("Qdrant client not initialized. Returning empty search results.")
            return []

        col = collection_name or self.collection_name
        try:
            results = self.client.query(
                collection_name=col,
                query_text=query,
                limit=limit
            )

            hits = []
            for hit in results:
                hits.append({
                    "id": hit.id,
                    "content": hit.document,
                    "metadata": hit.metadata,
                    "score": hit.score
                })
            return hits
        except Exception as e:
            logger.error(f"Error searching Qdrant ({col}): {str(e)}")
            return []

    def count_documents(self, collection_name: Optional[str] = None) -> int:
        col = collection_name or self.collection_name
        if not self.client:
            return 0
        try:
            result = self.client.count(collection_name=col)
            return result.count
        except Exception:
            return 0

    async def delete_document(self, doc_id: str):
        if not self.client:
            return
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=qmodels.PointIdsList(
                    points=[doc_id]
                )
            )
        except Exception as e:
            logger.error(f"Error deleting document from Qdrant: {str(e)}")

    async def run_nightly_crawl(self, db_session) -> Dict[str, Any]:
        """
        Simulates the nightly crawling batch.
        Gathers internal data:
        1. Task and subtask descriptions
        2. Internal messages (hearings/chat)
        3. Local artifact documentation files
        And indexes them in Qdrant.
        """
        from app.models.task import Task
        from app.models.message import Message
        from app.models.knowledge import Knowledge
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        
        logger.info("Starting nightly RAG crawl and knowledge generation...")
        
        # 1. Fetch WBS Tasks
        result = await db_session.execute(select(Task).options(selectinload(Task.subtasks)))
        tasks = result.scalars().all()
        
        # 2. Fetch Messages
        result_msg = await db_session.execute(select(Message))
        messages = result_msg.scalars().all()
        
        documents = []
        metadatas = []
        
        for task in tasks:
            text = f"WBS Task: {task.title}\nDescription: {task.description}\nStatus: {task.status}\nAssignee: {task.assignee_name}"
            documents.append(text)
            metadatas.append({
                "source": f"task_{task.id}",
                "type": "task",
                "title": task.title,
                "confidence_score": 1.0
            })
            
            for subtask in task.subtasks:
                sub_text = f"Microtask for {task.title}: {subtask.title}\nDescription: {subtask.description}\nStatus: {subtask.status}"
                documents.append(sub_text)
                metadatas.append({
                    "source": f"subtask_{subtask.id}",
                    "type": "subtask",
                    "title": subtask.title,
                    "confidence_score": 0.95
                })

        for msg in messages:
            # Check if message is low confidence (e.g. speculative language)
            content = msg.content
            is_speculative = any(w in content for w in ["〜だと思う", "かもしれない", "おそらく", "maybe", "think", "probably"])
            confidence = 0.65 if is_speculative else 0.9
            
            text = f"Project Discussion - Sender: {msg.sender_name} ({msg.sender_type})\nContent: {content}"
            documents.append(text)
            metadatas.append({
                "source": f"message_{msg.id}",
                "type": "message",
                "title": f"Chat message from {msg.sender_name}",
                "confidence_score": confidence
            })
            
        # Add to Qdrant
        if documents:
            ids = [str(uuid.uuid5(uuid.NAMESPACE_DNS, meta["source"])) for meta in metadatas]
            registered_ids = await self.add_documents(documents, metadatas, ids)
            
            # Synchronize into SQL DB so we can view them in the cleansing UI
            for i, doc_id in enumerate(registered_ids):
                # Check if it already exists in Postgres
                existing_res = await db_session.execute(
                    select(Knowledge).where(Knowledge.qdrant_id == doc_id)
                )
                existing = existing_res.scalar()
                status = "FLAGGED" if metadatas[i]["confidence_score"] < 0.7 else "ACTIVE"
                if not existing:
                    kn = Knowledge(
                        qdrant_id=doc_id,
                        content=documents[i],
                        source=metadatas[i]["type"],
                        confidence_score=metadatas[i]["confidence_score"],
                        status=status
                    )
                    db_session.add(kn)
                else:
                    existing.content = documents[i]
                    existing.source = metadatas[i]["type"]
                    existing.confidence_score = metadatas[i]["confidence_score"]
                    existing.status = status
            
            await db_session.commit()
            
        return {
            "crawled_tasks_count": len(tasks),
            "crawled_messages_count": len(messages),
            "indexed_chunks_count": len(documents)
        }

rag_service = RAGService()
